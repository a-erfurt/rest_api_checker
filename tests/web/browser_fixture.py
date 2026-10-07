"""Fabricated in-memory UI records; no SQL writes, HTTP or inference.

For visual inspection only: uvicorn --app-dir tests/web browser_fixture:app.
Every experiment and output is explicitly marked FABRICATED / TEST DATA.
"""
from contextlib import contextmanager
from copy import deepcopy
import json

from rest_api_checker.evaluation import evaluate
from rest_api_checker.experiment.request import MODELS
from rest_api_checker.experiment.schedule import comparison_schedule
from rest_api_checker.web.app import create_app
from rest_api_checker.web.queries import NotFound


HOSTILE = '<script>alert("MODEL OUTPUT")</script><img src=x onerror=alert(1)>'
HASH = 'a' * 64
LONG_CONTENT = HOSTILE + '\n' + '\n'.join(f'Fabricated evidence line {i}: ' + 'sample ' * 12 for i in range(200))


def authoritative_report():
    """Use the existing pure evaluator on fabricated inputs, never provider calls."""
    runs = [dict(id=s.run_order, case=s.case, prompt=s.prompt, model=s.model,
                 repetition=s.repetition, seed=s.seed, run_order=s.run_order,
                 result='valid', reference=dict(c1='PASS', c2='FAIL', c3='NOT_APPLICABLE'),
                 prediction=dict(c1='PASS', c2='FAIL', c3='NOT_APPLICABLE'))
            for s in comparison_schedule()]
    for row in [r for r in runs if r['prompt'] == 'P1'][:2]:
        row.update(result='parser_failure', prediction=None)
    report = evaluate(dict(fabricated=True, prompt_lengths={'P1':4325,'P2':4996,'P3':5835}, runs=runs))
    report.update(experiment_id=2, input_sha256=HASH, evaluator_sha256=HASH, runs=runs)
    return report


FABRICATED_REPORT = authoritative_report()


def experiment(identifier, *, completed=False, started=True):
    return dict(id=identifier, name=f'FABRICATED / TEST DATA {identifier}', kind='comparison',
                dataset_id=1, dataset_name='Fabricated development cases', dataset_version='v1',
                dataset_purpose='development',
                started_at='2026-09-26T10:00:00+00:00' if started else None,
                finished_at='2026-09-26T11:00:00+00:00' if completed else None,
                planned=324, completed=324 if completed else 217 if started else 0,
                pending=0 if completed else 107 if started else 324,
                valid=322 if completed else 214 if started else 0,
                parser_failure=1 if completed else 2 if started else 0, technical_failure=1 if started else 0,
                state='completed' if completed else 'running' if started else 'planned',
                fabricated=True)


def run(identifier, result='valid'):
    return dict(id=identifier, experiment_id=1, case=f'FAB-{identifier:03}',
                service='edx', method='post', path='/items', operation='POST /items',
                case_id=identifier, model=MODELS[(identifier - 1) % 3], model_id=(identifier - 1) % 3 + 1,
                prompt=f'P{(identifier - 1) % 3 + 1}', prompt_id=(identifier - 1) % 3 + 1,
                repetition=(identifier - 1) % 3 + 1, seed=(101,202,303)[(identifier - 1) % 3],
                result=result, status=result, run_order=identifier,
                started_at='2026-09-26T10:00:00+00:00',
                finished_at='2026-09-26T10:00:04+00:00' if result else None,
                duration_seconds=4 if result else None, duration=4 if result else None,
                duration_ms=4000 if result else None,prepared_at='2026-09-26T10:00:00+00:00',
                attempt=2 if result=='technical_failure' else 1,
                reference_c1='PASS',reference_c2='FAIL',reference_c3='NOT_APPLICABLE',
                prediction_c1='PASS' if result=='valid' else None,
                prediction_c2='PASS' if result=='valid' else None,
                prediction_c3='NOT_APPLICABLE' if result=='valid' else None,
                attempts=2 if result == 'technical_failure' else 1,
                attempt_count=2 if result == 'technical_failure' else 1)


def page(items, number=1, size=50):
    return dict(items=items[(number - 1) * size:number * size], total=len(items),
                page=number, page_size=size, pages=max(1, (len(items) + size - 1) // size))


class FabricatedQueries:
    """Small fake matching the SELECT-only query API; records every read call."""

    def __init__(self, mode='running'):
        self.mode = mode
        self.calls = []
        self.saved_report = deepcopy(FABRICATED_REPORT)
        self.run_rows = [run(i) for i in range(1, 124)]
        self.run_rows[1] = run(2, 'parser_failure')
        self.run_rows[2] = run(3, 'technical_failure')
        self.run_rows[3] = run(4, None)

    def experiments(self):
        self.calls.append(('experiments', {}))
        if self.mode == 'empty':
            return []
        if self.mode in ('completed', 'no_report'):
            return [experiment(2, completed=True)]
        if self.mode == 'not_started':
            return [experiment(1, started=False)]
        return [experiment(1), experiment(2, completed=True)]

    def overview(self, experiment_id):
        self.calls.append(('overview', dict(experiment_id=experiment_id)))
        selected = next((e for e in self.experiments() if e['id'] == experiment_id), None)
        if selected is None:
            raise NotFound('Experiment not found')
        return dict(experiment=selected, recent_runs=self.run_rows[:5])

    def latest_interactive_run(self):
        self.calls.append(('latest_interactive_run', {}))
        return None

    def adjacent_runs(self, identifier):
        self.calls.append(('adjacent_runs', dict(id=identifier)))
        previous = [r for r in self.run_rows if r['id'] < identifier]
        following = [r for r in self.run_rows if r['id'] > identifier]
        return dict(previous=max(previous, key=lambda r: r['id']) if previous else None,
                    next=min(following, key=lambda r: r['id']) if following else None)

    def runs(self, experiment_id=None, model_id=None, prompt_id=None, status=None,
             search='', page=1, page_size=50, repetition=None):
        parameters = dict(experiment_id=experiment_id, model_id=model_id, prompt_id=prompt_id,
                          status=status, search=search, page=page, page_size=page_size,
                          repetition=repetition)
        self.calls.append(('runs', parameters))
        items = self.run_rows
        for key, value in (('experiment_id',experiment_id), ('model_id',model_id), ('prompt_id',prompt_id),
                           ('repetition',repetition)):
            if value is not None:
                items = [r for r in items if r[key] == value]
        if status:
            items = [r for r in items if (r['result'] or 'pending') == status]
        if search:
            items = [r for r in items if search.lower() in r['case'].lower()]
        return globals()['page'](items, page, page_size)

    def filter_options(self, experiment_id=None):
        self.calls.append(('filter_options', dict(experiment_id=experiment_id)))
        return dict(models=[dict(id=i,name=m) for i,m in enumerate(MODELS,1)],
                    prompts=[dict(id=i,name=f'P{i}') for i in range(1,4)])

    def run_detail(self, identifier, tab='reasons'):
        self.calls.append(('run_detail', dict(id=identifier, tab=tab)))
        row = next((r for r in self.run_rows if r['id'] == identifier), None)
        if row is None:
            raise NotFound('Run not found')
        row = {**row, 'request_file_id':91, 'reference_id':1, 'run_config_id':1}
        reference = dict(c1='PASS',c2='FAIL',c3='NOT_APPLICABLE',version=1)
        prediction = dict(c1='PASS',c2='PASS',c3='NOT_APPLICABLE',
                          c1_reason='Fabricated reason: '+HOSTILE,
                          c2_reason='Fabricated model reason; not reference truth.',
                          c3_reason='Fabricated applicability reason.') if row['result']=='valid' else None
        attempts = [dict(id=identifier, attempt=1, result=row['result'],
                         prepared_at=row['prepared_at'],duration_ms=row['duration_ms'],
                         http_status=200 if row['result'] else None,error_kind=None,done_reason='stop',
                         started_at=row['started_at'],finished_at=row['finished_at'],
                         request_file_id=91,response_file_id=92,diagnostics_file_id=93)]
        evidence = [] if tab=='reasons' else [dict(title='Exact fabricated '+tab+' evidence',content=LONG_CONTENT)]
        if tab=='response':
            row['response']=dict(status_code=422,content_type='application/json',body_file_id=2,observed_at=None)
        if tab=='openapi':
            row['contract']=dict(id=1,openapi_version='3.1.0',file_id=3,http_method='post',path_template='/items')
        case = dict(service=row['service'], method=row['method'], path=row['path'],
                    status_code=422, content_type='application/json', reference=reference,
                    origin='synthetic_inconsistency', metadata={}, case_code=row['case'])
        files = [dict(label=label, content=content, archive_name='fabricated.json',
                      sha256=HASH, size_bytes=len(content.encode())) for label, content in (
            ('Observed response body', json.dumps({'fabricated': HOSTILE})),
            ('OpenAPI contract', json.dumps({'openapi': '3.1.0', 'info': {'title': HOSTILE}})),
            ('Original input file', 'FABRICATED input\n'+HOSTILE),
            ('Reference / explanation', json.dumps({'oracle': reference})),
            ('Case provenance', json.dumps({'local_path': '/Users/fabricated/private/input.json'})),
        )]
        return dict(run=row, reference=reference, prediction=prediction, attempts=attempts,
                    evidence=evidence, technical=dict(id=identifier, sha256=HASH),
                    case_details=case, files=files,
                    raw_model_response=HOSTILE+'\n  FABRICATED raw output\n' if row['result'] else None,
                    parser_error=dict(status='invalid', code='CATEGORY_FIELDS') if row['result']=='parser_failure' else None,
                    runtime_evidence=dict(model_digest=HASH, ollama_version='FABRICATED',
                        parser_diagnostics=dict(status='invalid', code='CATEGORY_FIELDS')
                        if row['result']=='parser_failure' else None))

    def report(self, experiment_id):
        self.calls.append(('report', dict(experiment_id=experiment_id)))
        if self.mode == 'no_report':
            return None
        return deepcopy(self.saved_report) if experiment_id==2 else None

    def data_list(self, section, page=1, page_size=50, kind='models'):
        self.calls.append(('data_list', dict(section=section,page=page,page_size=page_size,kind=kind)))
        rows = {
            'datasets':[dict(id=1,name='Fabricated development cases',version='v1',purpose='development',
                             kind='development',case_count=12,cases=12)],
            'cases':[dict(id=1,case='FAB-001',native_case_id='FAB-001',api='Fabricated API',
                          family='Fabricated family',origin='natural_observation',method='post',path='/items',
                          operation='POST /items',
                          c1='PASS',c2='FAIL',c3='NOT_APPLICABLE')],
            'references':[dict(id=1,case='FAB-001',api='Fabricated API',c1='PASS',c2='FAIL',
                               c3='NOT_APPLICABLE',version=1)],
            'artifacts':[
                {
                    'models':dict(id=1,name='Fabricated model',family='fixture',parameters_b='27.000',
                                  quantization='Q4_K_M',context_length=32768),
                    'prompts':dict(id=1,name='Fabricated prompt',version='v1',strategy='direct'),
                    'configs':dict(id=1,temperature='0.100',top_p='0.900',top_k=40,num_ctx=32768,
                                   num_predict=4096,think=False),
                    'contracts':dict(id=1,name='Fabricated API',openapi_version='3.1.0',
                                     imported_at='2026-09-26T10:00:00+00:00'),
                    'files':dict(id=1,name='Fabricated evidence',size_bytes=1234),
                    'experiments':dict(id=1,name='Fabricated experiment',kind='comparison',
                                       started_at='2026-09-26T10:00:00+00:00',finished_at=None),
                    'reports':dict(id=1,name='Fabricated report',created_at='2026-09-26T11:00:00+00:00'),
                }[kind]
            ],
        }[section]
        return globals()['page'](rows,page,page_size)

    def data_detail(self, section, identifier, kind='models'):
        self.calls.append(('data_detail',dict(section=section,id=identifier,kind=kind)))
        if identifier!=1:
            raise NotFound('Record not found')
        return dict(title=f'Fabricated {section} record', metadata=dict(Name='Fabricated record',Version=1),
                    technical=dict(id=identifier,sha256=HASH),evidence=[dict(title='Content',content=HOSTILE)],
                    relationships=[])

    def schema_version(self):
        self.calls.append(('schema_version',{}))
        return 2


def query_factory(queries):
    @contextmanager
    def factory():
        yield queries
    return factory


queries = FabricatedQueries()
app = create_app(query_factory=query_factory(queries))
