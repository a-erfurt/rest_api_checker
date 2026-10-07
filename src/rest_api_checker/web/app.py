"""Server-rendered inspection of persisted evidence; all application routes read only."""
import argparse
from contextlib import contextmanager
from datetime import datetime
import os
from pathlib import Path
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pyodbc

from ..persistence.database import connect, read_settings
from .queries import DataUnavailable, NotFound, ReportUnavailable, WebQueries
from .presentation import (context_name, evaluation_view, format_ratio, is_interactive,
                           model_name, run_detail_view, run_summary)

ROOT = Path(__file__).parent
SECTIONS = ('datasets', 'cases', 'references', 'artifacts')
ARTIFACT_KINDS = ('models', 'prompts', 'configs', 'contracts', 'experiments', 'reports', 'files')
RUN_TABS = ('reasons', 'response', 'openapi', 'raw', 'attempts')
Positive = Annotated[int, Query(ge=1, le=9223372036854775807)]


@contextmanager
def database_queries():
    """Lazy, request-owned connection. No startup migration or implicit commit."""
    path = os.environ.get('RAC_WEB_ENV_FILE')
    if not path:
        raise DataUnavailable('Database is not configured.')
    cn = None
    try:
        settings = read_settings(path)
        cn = connect(settings, os.environ.get('RAC_WEB_DATABASE', 'rest_api_checker'))
        cn.timeout = 10
        yield WebQueries(cn)
    except (pyodbc.Error, OSError, ValueError) as exc:
        if isinstance(exc, (NotFound, DataUnavailable)):
            raise
        raise DataUnavailable('Database unavailable. Check local connection and schema configuration.') from exc
    finally:
        if cn is not None:
            try:
                cn.rollback()
            finally:
                cn.close()


def status_text(value):
    return {
        'PASS': '✓ PASS', 'FAIL': '✕ FAIL', 'NOT_APPLICABLE': '– NOT_APPLICABLE',
        'valid': '✓ VALID', 'parser_failure': '! PARSER FAILURE',
        'technical_failure': '⚠ TECHNICAL FAILURE', None: '– Pending',
    }.get(value, str(value).replace('_', ' '))


def select_experiment(experiments, identifier):
    if identifier is not None:
        selected = next((e for e in experiments if e['id'] == identifier), None)
        if selected is None:
            raise NotFound('Experiment not found.')
        return selected
    experiments = [e for e in experiments if not is_interactive(e)]
    active = [e for e in experiments if e.get('started_at') and not e.get('finished_at')]
    completed = [e for e in experiments if e.get('finished_at')]
    if active:
        return max(active, key=lambda e: (datetime.fromisoformat(e['started_at']), e['id']))
    if completed:
        return max(completed, key=lambda e: (datetime.fromisoformat(e['finished_at']), e['id']))
    return max(experiments, key=lambda e: e['id']) if experiments else None


def complete(experiment):
    return bool(experiment and experiment.get('finished_at') and experiment.get('planned', 0) > 0
                and experiment.get('pending') == 0)


def optional_id(value, maximum=9223372036854775807):
    if value in (None, ''):
        return None
    try:
        number = int(value)
    except ValueError:
        raise HTTPException(422, 'Invalid numeric filter') from None
    if not 1 <= number <= maximum:
        raise HTTPException(422, 'Numeric filter outside supported range')
    return number



def evidence_view(artifact):
    """Metadata is a display projection; raw model/response evidence stays exact."""
    import json
    import re
    projected = dict(artifact)
    if isinstance(artifact.get('content'), str) and artifact['content'].startswith('Non-UTF-8 bytes; exact base64:'):
        projected.update(content=None, notice='Binary artifact. Stored metadata is shown; the bytes are unchanged.')
        return projected
    if artifact.get('label') != 'Reference / explanation' or not artifact.get('content'):
        return projected
    try:
        value = json.loads(artifact['content'])
    except (ValueError, TypeError):
        return projected
    changed = False

    def visible(item):
        nonlocal changed
        if isinstance(item, dict):
            result = {}
            for key, val in item.items():
                if re.search(r'(?i)(password|credential|authorization|api[_-]?key|access[_-]?token|secret)', key):
                    result[key] = '[private metadata omitted]'
                    changed = True
                else:
                    result[key] = visible(val)
            return result
        if isinstance(item, list):
            return [visible(entry) for entry in item]
        if isinstance(item, str) and re.search(r'(?:/Users/|/home/|/private/|[A-Za-z]:\\)', item):
            changed = True
            return '[local path omitted]'
        return item

    filtered = visible(value)
    if changed:
        projected['content'] = json.dumps(filtered, ensure_ascii=False, indent=2)
        projected['notice'] = 'Metadata view: private fields and local paths are omitted. Stored evidence is unchanged.'
    return projected

def create_app(query_factory=None):
    app = FastAPI(title='RestApiChecker', docs_url=None, redoc_url=None, openapi_url=None)
    factory = query_factory or database_queries
    templates = Jinja2Templates(directory=str(ROOT / 'templates'))
    templates.env.filters.update(ratio=format_ratio, model_name=model_name, status=status_text,
                                 context_name=context_name, is_interactive=is_interactive)
    templates.env.globals['is_interactive'] = is_interactive
    app.mount('/static', StaticFiles(directory=str(ROOT / 'static')), name='static')

    def render(request, template, *, code=200, **context):
        def scoped_url(path):
            identifier = context.get('selected_experiment')
            if identifier is None:
                return path
            parts = urlsplit(path)
            params = dict(parse_qsl(parts.query))
            params.setdefault('experiment', str(identifier))
            return urlunsplit(parts._replace(query=urlencode(params)))
        def query_url(**changes):
            params = dict(request.query_params)
            for key, value in changes.items():
                if value is None:
                    params.pop(key, None)
                else:
                    params[key] = str(value)
            return str(request.url.replace_query_params(**params).path) + (
                '?' + str(request.url.replace_query_params(**params).query) if params else '')
        return templates.TemplateResponse(request=request, name=template, status_code=code,
            context={'title': 'RestApiChecker', 'page': '', 'experiments': [], 'selected_experiment': None,
                     'query_url': query_url, 'scoped_url': scoped_url, 'interactive': False, 'latest_run': None, **context})

    @app.middleware('http')
    async def safety_headers(request, call_next):
        response = await call_next(request)
        response.headers.update({
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; "
                "frame-ancestors 'none'; form-action 'self'",
            'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
            'Cache-Control': 'no-store', 'X-RestApiChecker-UI': 'read-only',
        })
        return response

    @app.exception_handler(DataUnavailable)
    @app.exception_handler(pyodbc.Error)
    def unavailable(request, exc):
        if request.url.path.startswith('/fragments/'):
            return render(request, 'overview_fragment.html', code=503, unavailable=True,
                          experiment=None, recent_runs=[], report=None)
        return render(request, 'error.html', code=503, heading='Database unavailable',
                      message='The database or persisted evidence could not be read. Check the local database configuration and schema. No study data was changed.')

    @app.exception_handler(NotFound)
    def missing(request, exc):
        return render(request, 'error.html', code=404, heading='Record not found',
                      message='The requested record is not available in this database.')

    def selection(q, identifier):
        experiments = q.experiments()
        selected = select_experiment(experiments, identifier)
        return dict(experiments=experiments, experiment=selected,
                    selected_experiment=selected['id'] if selected else None, interactive=is_interactive(selected))

    def stored_report(q, experiment):
        if is_interactive(experiment):
            return None, 'Aggregate evaluation is intended for completed experiment batches. Inspect individual runs instead.'
        if not complete(experiment):
            return None, 'Evaluation becomes available after experiment completion.'
        try:
            report = q.report(experiment['id'])
            if report:
                evaluation_view(report)  # Validate supported display shape; never score runs.
        except ReportUnavailable:
            return None, 'Persisted evaluation unavailable: the report format or evidence binding could not be verified.'
        except (ValueError, KeyError, TypeError, AttributeError):
            return None, 'This persisted report format is unavailable in the current viewer.'
        return report, 'No persisted evaluation report is available. Report creation remains CLI-only.'

    @app.get('/')
    @app.get('/overview')
    def overview(request: Request, experiment: Positive | None = None):
        with factory() as q:
            context = selection(q, experiment)
            selected = context['experiment']
            context.update(q.overview(selected['id']) if selected else dict(recent_runs=[]))
            context['report'], context['report_unavailable_reason'] = stored_report(q, context['experiment'])
            latest = q.latest_interactive_run()
            context['latest_run'] = run_summary(latest) if latest else None
            context['recent_runs'] = [run_summary(row) for row in context.get('recent_runs', [])]
            context['schema_version'] = q.schema_version()
            context['history'] = sorted(context['experiments'], key=lambda e: e['id'], reverse=True)[:3]
            return render(request, 'overview.html', page='overview', **context)

    @app.get('/fragments/overview')
    def overview_fragment(request: Request, experiment: Positive):
        with factory() as q:
            context = q.overview(experiment)
            context['interactive'] = is_interactive(context['experiment'])
            context['recent_runs'] = [run_summary(row) for row in context.get('recent_runs', [])]
            context['report'], context['report_unavailable_reason'] = stored_report(q, context['experiment'])
            return render(request, 'overview_fragment.html', selected_experiment=experiment, **context)

    @app.get('/evaluation')
    def evaluation_page(request: Request, experiment: Positive | None = None,
                        prompt: str | None = None, view: str = 'models', metric: str = 'Correctness'):
        with factory() as q:
            context = selection(q, experiment)
            selected = context['experiment']
            report, presentation = None, None
            reason = 'No experiment data yet.' if selected is None else 'Evaluation becomes available after experiment completion.'
            if is_interactive(selected):
                reason = 'Aggregate evaluation is intended for completed experiment batches. Inspect individual runs instead.'
            elif complete(selected):
                report, reason = stored_report(q, selected)
                if report:
                    try:
                        presentation = evaluation_view(report, prompt=prompt, view=view, metric=metric)
                    except (ValueError, KeyError, TypeError, AttributeError):
                        reason = 'This persisted report format is unavailable in the current viewer.'
                        report = None
            return render(request, 'evaluation.html', page='evaluation', report=report,
                          evaluation=presentation, evaluation_unavailable_reason=reason, **context)

    @app.get('/runs')
    def runs(request: Request, experiment: str | None = None, model: str | None = None,
             prompt: str | None = None, status: str | None = None,
             search: Annotated[str, Query(max_length=128)] = '', page: Positive = 1,
             page_size: Annotated[int, Query(ge=1, le=100)] = 50,
             repetition: str | None = None):
        if status not in (None, '', 'valid', 'parser_failure', 'technical_failure', 'pending', 'attention'):
            raise HTTPException(422, 'Unknown run status')
        experiment = optional_id(experiment)
        model, prompt, repetition = optional_id(model), optional_id(prompt), optional_id(repetition, 32767)
        with factory() as q:
            context = selection(q, experiment)
            if experiment is None:
                context.update(experiment=None, selected_experiment=None, interactive=False)
            identifier = context['selected_experiment']
            result = q.runs(experiment_id=identifier, model_id=model, prompt_id=prompt,
                            status=status or None, search=search, page=page,
                            page_size=page_size, repetition=repetition)
            result['items'] = [run_summary(row) for row in result['items']]
            return render(request, 'runs.html', page='runs', result=result,
                          options=q.filter_options(identifier), filters=dict(model=model, prompt=prompt,
                          status=status, search=search, repetition=repetition), **context)

    @app.get('/runs/latest')
    def latest_run():
        with factory() as q:
            run = q.latest_interactive_run()
            return RedirectResponse(f"/runs/{run['id']}" if run else '/runs', status_code=307)

    @app.get('/runs/{run_id}/files/{file_index}')
    def run_file(request: Request, run_id: int, file_index: int):
        if run_id < 1 or file_index < 0:
            raise HTTPException(404)
        with factory() as q:
            detail = q.run_detail(run_id)
            files = detail.get('files', [])
            if file_index >= len(files) or files[file_index].get('label') == 'Case provenance':
                raise HTTPException(404)
            artifact = evidence_view(files[file_index])
            return render(request, 'evidence.html', page='runs', artifact=artifact, run_id=run_id,
                          selected_experiment=detail['run']['experiment_id'])

    @app.get('/runs/{run_id}')
    def run_detail(request: Request, run_id: int, tab: str = 'reasons'):
        if run_id < 1 or tab not in RUN_TABS:
            raise HTTPException(404)
        with factory() as q:
            detail = q.run_detail(run_id, tab=tab)
            # Legacy links remain readable without exposing transport/spool metadata.
            import json
            detail = dict(detail, evidence=[
                dict(item, content=json.dumps((detail.get('runtime_evidence') or {}).get('parser_diagnostics'),
                                              ensure_ascii=False, indent=2))
                if 'diagnostic' in item.get('title', '').lower() else item
                for item in detail.get('evidence', [])
                if 'request and rendered context' not in item.get('title', '').lower()])
            view = run_detail_view(detail, q.adjacent_runs(run_id))
            return render(request, 'run_detail.html', page='runs', detail=detail, detail_view=view,
                          selected_experiment=detail['run']['experiment_id'], tab=tab, tabs=RUN_TABS,
                          interactive=is_interactive(detail['run']))

    @app.get('/data')
    def data_root(experiment: Positive | None = None):
        return RedirectResponse('/data/datasets' + (f'?experiment={experiment}' if experiment else ''), status_code=307)

    @app.get('/data/{section}')
    def data_page(request: Request, section: str, page: Positive = 1, kind: str = 'models',
                  experiment: Positive | None = None):
        if section not in SECTIONS or kind not in ARTIFACT_KINDS:
            raise HTTPException(404)
        with factory() as q:
            return render(request, 'data.html', page='data', section=section, sections=SECTIONS,
                          selected_experiment=experiment, kind=kind, kinds=ARTIFACT_KINDS,
                          result=q.data_list(section, page=page, kind=kind))

    @app.get('/data/{section}/{identifier}')
    def data_detail(request: Request, section: str, identifier: int, kind: str = 'models',
                    experiment: Positive | None = None):
        if section not in SECTIONS or kind not in ARTIFACT_KINDS or identifier < 1:
            raise HTTPException(404)
        with factory() as q:
            return render(request, 'data_detail.html', page='data', section=section, sections=SECTIONS,
                          selected_experiment=experiment, kind=kind,
                          detail=q.data_detail(section, identifier, kind=kind))

    return app


def main():
    parser = argparse.ArgumentParser(description='Read-only local research web interface')
    parser.add_argument('--env-file', type=Path, help='Existing private SQL settings file (0600)')
    parser.add_argument('--database', default=os.environ.get('RAC_WEB_DATABASE', 'rest_api_checker'))
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    if args.env_file:
        os.environ['RAC_WEB_ENV_FILE'] = str(args.env_file)
    os.environ['RAC_WEB_DATABASE'] = args.database
    import uvicorn
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == '__main__':
    main()
