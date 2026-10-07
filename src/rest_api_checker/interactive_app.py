"""Guided application over the existing demo runner and read-only Web queries."""
from contextlib import closing, contextmanager
import json
import re

from rich.syntax import Syntax
import subprocess
import webbrowser
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import pyodbc

from . import cli, live_demo_cli, live_result, terminal
from .interactive_menu import Back, choose
from .live_presenter import model_label
from .operator_config import credentials
from .persistence.database import connect
from .web.queries import DataUnavailable, NotFound, WebQueries


@contextmanager
def queries(config):
    """Browsing cannot reach a repository write API, including for final results."""
    with closing(connect(credentials(config), config.database)) as cn:
        try:
            yield WebQueries(cn)
        finally:
            cn.rollback()


def ui_url(config, run_id=None):
    host = '[::1]' if config.host=='::1' else config.host
    return f'http://{host}:{config.port}'+(f'/runs/{run_id}' if run_id is not None else '')


def _web_ui_url_allowed(original, target):
    if original == target:
        return True
    source, destination = urlsplit(original), urlsplit(target)
    return (source.path == '/runs/latest'
            and (source.scheme, source.netloc) == (destination.scheme, destination.netloc)
            and not destination.query and not destination.fragment
            and (destination.path == '/runs' or
                 (destination.path.startswith('/runs/') and destination.path[6:].isdecimal())))


def _existing_web_ui(url):
    """Only reopen a marked local UI; latest redirects stay on approved run pages."""
    class RunRedirect(HTTPRedirectHandler):
        def redirect_request(self, request, response, code, message, headers, newurl):
            if not _web_ui_url_allowed(url, newurl):
                raise URLError('Unexpected Web UI redirect')
            return super().redirect_request(request, response, code, message, headers, newurl)
    try:
        with build_opener(RunRedirect()).open(Request(url, method='GET'), timeout=2) as response:
            return (_web_ui_url_allowed(url, response.geturl())
                    and response.headers.get('X-RestApiChecker-UI') == 'read-only')
    except (OSError, URLError):
        return False


def open_web(config, console, run_id=None):
    from .operator import web, OperatorError
    latest = run_id is None
    deferred_latest = False
    if latest:
        try:
            with queries(config) as query:
                stored = query.latest_interactive_run()
            run_id = stored['id'] if stored else None
        except (DataUnavailable, pyodbc.Error):
            # Existing web startup can bring the configured local DB online.
            # Resolve afterwards through the read-only latest route.
            deferred_latest = True
    path = '/runs/latest' if deferred_latest else (f'/runs/{run_id}' if run_id is not None else '')
    url = ui_url(config)+path
    confirmation = 'Web UI opened: '+('latest run' if latest and (run_id is not None or deferred_latest) else
                                     'stored run' if run_id is not None else 'overview')
    try:
        web(config, console, open_browser=True, open_path=path, opened_message=confirmation)
    except OperatorError as exc:
        if 'address already in use' not in str(exc):
            raise
        if _existing_web_ui(url):
            try:
                opened = webbrowser.open(url)
            except webbrowser.Error:
                opened = False
            if opened:
                console.print(confirmation, style='dim')
            else:
                console.print('Open the Web UI: '+url)
        else:
            console.print('This port is already in use. No process was stopped.')
            console.print('If your RestApiChecker UI is already running, open: '+url)
    except KeyboardInterrupt:
        console.print('Web server stopped; returning to the menu.')


def detail_projection(value):
    run = value['run']
    return dict(value, case=run['case'], model=run['model'], prompt=run['prompt'],
                correctness={c: value['prediction'][c]==value['reference'][c]
                             if value.get('prediction') and value.get('reference') else None
                             for c in live_result.CATEGORIES})


def stored_detail(config, run_id, tab='reasons'):
    with queries(config) as query:
        return detail_projection(query.run_detail(run_id, tab))


def show_raw(console, value):
    console.print('\nRaw model response', style='bold cyan')
    entries = [entry for entry in value.get('evidence', [])
               if entry.get('content') is not None and 'request' not in entry.get('title', '').lower()]
    if not entries:
        console.print('No stored provider output is available.', style='dim')
    for entry in entries:
        console.print(terminal.clean(entry['title']), style='bold')
        raw = entry['content']
        try:
            json.loads(raw)
            lexer = 'json'
        except (ValueError, TypeError):
            lexer = 'text'
        from contextlib import nullcontext
        with console.pager(styles=True) if console.is_terminal else nullcontext():
            console.print(Syntax(terminal.clean(raw), lexer, word_wrap=True, background_color='default'))


def result_actions(config, console, details, read, *, browsing=False, context=None):
    while True:
        actions = ['View details', 'View raw model response', 'View case files', 'Open in Web UI',
                   'Back to run list' if browsing else 'Run another case', 'Main menu', 'Exit']
        try:
            action = choose(console, 'Next action', list(range(len(actions))), lambda i: actions[i], read)
            if action>=4:
                return ('back' if browsing else 'another', 'main', 'exit')[action-4]
            selected = details[0] if len(details)==1 else choose(console, 'Select a result', details,
                lambda d: f"{d.get('case') or d['run'].get('case')} · repetition {d['run']['repetition']}", read)
        except Back:
            return 'back' if browsing else 'main'
        run_id = selected['run']['id']
        if action==0:
            detail = stored_detail(config, run_id)
            if context:
                detail = dict(detail, spool=context.get('spool'))
            live_result.show_details(console, detail)
        elif action==1:
            show_raw(console, stored_detail(config, run_id, 'raw-output'))
        elif action==2:
            from .interactive_evidence import show_run_case_files
            with queries(config) as query:
                show_run_case_files(query, selected, console, read)
        else:
            open_web(config, console, run_id)


def context_label(context):
    name = context['name']
    if re.match(r'(?i)live[- /]?(?:adhoc|ad-hoc|demo)', name):
        name = 'Interactive run'
    timestamp = context.get('started_at') or context.get('finished_at')
    suffix = ' · '+str(timestamp)[:16] if timestamp else ''
    return f"{name}{suffix}\n{context['completed']}/{context['planned']} completed"


def browse(config, console, read):
    console.print('Previous results · read-only', style='dim')
    while True:
        with queries(config) as query:
            contexts = query.experiments()
        if not contexts:
            console.print('No stored run contexts are available.')
            return 'main'
        try:
            context = choose(console, 'Select run context', contexts, context_label, read)
            with queries(config) as query:
                first = query.runs(experiment_id=context['id'], page_size=200)
                records = list(first['items'])
                for page in range(2, first['pages']+1):
                    records.extend(query.runs(experiment_id=context['id'], page=page, page_size=200)['items'])
            if not records:
                console.print('This context has no stored runs.')
                continue
            while True:
                selected = choose(console, 'Select previous result', records,
                    lambda r: f"{r['case']} · {model_label({'name': r['model']})} · repetition {r['repetition']}\n"
                              f"{r.get('result') or 'pending'} · {r.get('finished_at') or 'not completed'}", read,
                    explanation='Search /case or /model.')
                detail = stored_detail(config, selected['id'])
                live_result.show(console, detail)
                action = result_actions(config, console, [detail], read, browsing=True)
                if action!='back':
                    return action
        except Back:
            return 'main'


def run_check(config, console, read):
    from .operator import cli_args
    while True:
        args = cli.arguments().parse_args(cli_args(config, ['demo', 'run'], plain=console.color_system is None))
        args.adhoc = True
        args.ui_url = ui_url(config)
        # Share selection/planning/execution with `rac demo run`, including errors.
        from .persistence.repository import Repository
        with closing(connect(credentials(config), config.database)) as cn:
            try:
                value, _ = live_demo_cli.run(Repository(cn), args, console, input_fn=read, interactive=True)
            finally:
                cn.rollback()
        if value['status']=='CANCELLED':
            console.print('Cancelled. No run created or model called.', style='dim')
            return 'main'
        details = value.get('results', [])
        shown = set(value.get('displayed_run_ids', []))
        if len(details) == 1 and details[0]['run']['id'] not in shown:
            live_result.show(console, details[0])
        live_result.repetitions(console, details)
        if not details:
            console.print('⚠ Run '+value['status'].lower()+'. No result is available.', style='yellow')
            try:
                action = choose(console, 'Next action', ['View details', 'Main menu'], str, read)
                if action == 'View details':
                    console.print(terminal.clean(value.get('message') or 'No additional information.'))
                    console.print(terminal.table('Run context', ('Field', 'Value'), [
                        (name, value[name]) for name in ('experiment_id', 'run_ids', 'spool') if value.get(name)]))
            except Back:
                pass
            return 'main'
        action = result_actions(config, console, details, read, context=value)
        if action!='another':
            return action


def launch(config, console, *, input_fn=None):
    from .operator import sql_error
    console.width = min(console.width, 96)
    read = input_fn or input
    labels = ['Run API response check', 'Browse previous results', 'Open Web UI', 'Exit']
    while True:
        try:
            action = choose(console, 'RestApiChecker', list(range(4)), lambda i: labels[i], read,
                explanation='Choose an action:')
            if action==3:
                return 0
            result = run_check(config, console, read) if action==0 else (
                browse(config, console, read) if action==1 else open_web(config, console))
            if result=='exit':
                return 0
        except (Back, EOFError, KeyboardInterrupt):
            return 0
        except (ValueError, OSError, pyodbc.Error, DataUnavailable, NotFound, subprocess.SubprocessError) as exc:
            message = sql_error(exc) if isinstance(exc, pyodbc.Error) else (
                'Local runtime check failed. Inspect the Ollama service and try again.'
                if isinstance(exc, subprocess.SubprocessError) else str(exc))
            console.print(terminal.clean(message), style='yellow')
        except (TypeError, KeyError, IndexError, AttributeError):
            console.print('Stored metadata is incomplete or incompatible. Inspect the dataset/runtime configuration.', style='yellow')
