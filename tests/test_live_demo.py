"""Live demo safety over fabricated SQL rows and native context evidence only."""
from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rest_api_checker import live_demo as demo
from rest_api_checker.experiment import batch, parser, renderer, request, request_v2
from rest_api_checker.experiment.encoding import digest, encode
from rest_api_checker.persistence import inspection
from rest_api_checker.persistence.database import require
from rest_api_checker.persistence.repository import D07

ROOT = Path(__file__).resolve().parents[1]
PROMPT = (ROOT.parent/'bachelor_rest_api_checker/03_research_design/prompt_candidates_v1/p2_structured_checklist_v1.txt').read_bytes()


class FabricatedRepo:
    def __init__(self):
        self.tables, self.files, self.writes = {}, {}, []
        self.cn = SimpleNamespace(commit=lambda: None, rollback=lambda: None)

    def add(self, table, **row):
        self.tables.setdefault(table, {})[row['id']] = row

    def _row(self, table, row_id):
        require(row_id in self.tables.get(table, {}), 'Missing '+table+' row')
        return deepcopy(self.tables[table][row_id])

    def file(self, file_id):
        return self.files[file_id]

    def require_d07(self, config_id, model):
        row = self._row('run_configs', config_id)
        require(all(row[k] == v for k, v in D07.items()), 'D07 configuration mismatch')
        require(row['think'] is (False if model == request.MODELS[0] else None), 'Thinking policy mismatch')

    def transaction(self):
        return nullcontext()

    def archive(self, name, raw):
        self.writes.append(('archive', name))
        file_id = max(self.files, default=0) + 1
        self.files[file_id] = raw
        return file_id

    def plan_experiment(self, **kwargs):
        self.writes.append(('experiment', deepcopy(kwargs)))
        experiment_id = 90001
        setup = {**kwargs['setup'], 'bindings': inspection.bindings(self, kwargs['dataset_id'], kwargs['schedule'])}
        setup_id = self.archive('experiment-setup.json', encode(setup))
        self.add('experiments', id=experiment_id, dataset_id=kwargs['dataset_id'], setup_file_id=setup_id,
                 schedule_seed=kwargs['schedule_seed'], kind=kwargs['kind'], name=kwargs['name'], finished_at=None)
        ids = []
        for slot in kwargs['schedule']:
            run_id = 91000 + slot['run_order']
            self.add('experiment_runs', id=run_id, experiment_id=experiment_id, dataset_id=kwargs['dataset_id'],
                     result=None, request_file_id=None, **slot)
            ids.append(run_id)
        return experiment_id, ids

    def source(self, file_id, pointer):
        return json.loads(self.file(file_id))

    def verify_closure(self, files):
        for item in files:
            require(digest(self.file(item['file_id'])) == item['sha256'], 'Source closure drift')

    def dispatch_owner(self):
        return nullcontext()

    def complete_experiment(self, experiment_id, **kwargs):
        self.tables['experiments'][experiment_id]['finished_at'] = kwargs['finished_at']

    def execution_inputs(self, run_id):
        run = self._row('experiment_runs', run_id)
        exp = self._row('experiments', run['experiment_id'])
        raw = self.file(exp['setup_file_id'])
        member = self._row('dataset_cases', run['dataset_case_id'])
        case = self._row('test_cases', member['case_id'])
        operation = self._row('api_operations', case['operation_id'])
        contract = self._row('api_contracts', operation['contract_id'])
        response = self._row('responses', case['response_id'])
        return dict(run=run, setup=json.loads(raw), setup_sha256=digest(raw),
            evidence=renderer.Evidence(self.file(contract['file_id']), operation['http_method'],
                operation['path_template'], response['status_code'], response['content_type'], self.file(response['body_file_id'])),
            contract_identity=f'files:{contract["file_id"]}', body_identity=f'files:{response["body_file_id"]}',
            prompt_name='P2', prompt=PROMPT, model=self._row('models', run['model_id']))


@pytest.fixture
def repository(monkeypatch):
    repo = FabricatedRepo()
    def read(repository, table, **filters):
        return [deepcopy(r) for _, r in sorted(repository.tables.get(table, {}).items())
                if all(r[k] == v for k, v in filters.items())]
    monkeypatch.setattr(demo, 'rows', read)
    monkeypatch.setattr(inspection, 'rows', read)
    monkeypatch.setattr(batch, 'rows', read)
    repo.files = {1: PROMPT, 2: encode({'openapi': '3.0.4', 'paths': {'/future/validate': {'post': {'responses': {
        '200': {'description': 'ok', 'content': {'application/json': {'schema': {'type': 'object'}}}}}}}}}),
        3: b'{}', 4: encode({'c1':'PASS', 'c2':'PASS', 'c3':'PASS'})}
    repo.add('apis', id=7, name='Future Service')
    repo.add('api_contracts', id=8, api_id=7, file_id=2)
    repo.add('api_operations', id=9, contract_id=8, http_method='post', path_template='/future/validate')
    repo.add('responses', id=10, status_code=200, content_type='application/json', body_file_id=3)
    for case_id in (11, 12, 13):
        repo.add('test_cases', id=case_id, operation_id=9, response_id=10, origin='natural_observation', source_file_id=4)
        repo.add('reference_results', id=case_id, case_id=case_id, version=1, source_file_id=4, source_pointer='',
                 c1='PASS', c2='PASS', c3='PASS')
    for dataset_id, purpose in ((1, 'development'), (3, 'development'), (4, 'evaluation')):
        repo.add('datasets', id=dataset_id, name=f'FABRICATED dataset {dataset_id}', version='v1', purpose=purpose)
    for row_id, dataset_id, case_id, position in ((21,1,11,1), (22,1,12,2), (23,3,13,1), (24,4,12,1)):
        repo.add('dataset_cases', id=row_id, dataset_id=dataset_id, case_id=case_id, reference_id=case_id,
                 case_code=f'CASE-{case_id}', position=position)
    for index, model in enumerate(request.MODELS, 1):
        repo.add('models', id=index, name=model, digest=str(index)*64, context_length=32768)
        repo.add('run_configs', id=index, think=False if index==1 else None, **D07)
    repo.add('models', id=99, name='unapproved:1b', digest='a'*64)
    repo.add('prompts', id=1, name='P2', file_id=1)
    repo.add('prompts', id=2, name='CUSTOM', file_id=3)
    return repo


def test_catalog_uses_generic_services_and_excludes_final_memberships(repository):
    before = deepcopy(repository.tables), dict(repository.files)
    value = demo.catalog(repository)
    assert [(c['id'], c['service'], c['path']) for c in value['cases']] == [(21, 'Future Service', '/future/validate')]
    assert {m['id'] for m in value['models']} == {1, 2, 3}
    assert [p['id'] for p in value['prompts']] == [1]
    assert (repository.tables, repository.files) == before
    assert repository.writes == []


def test_catalog_hides_missing_reference_and_drifted_prompt(repository):
    repository.tables['dataset_cases'][21]['reference_id'] = None
    repository.files[1] = b'changed P2'
    value = demo.catalog(repository)
    assert value['cases'] == [] and value['prompts'] == []
    assert repository.writes == []


@pytest.fixture
def prepared(repository, tmp_path):
    runtime_id = 'evaluation_v2_FABRICATED_TEST'
    directory = tmp_path / demo.runtime_evidence.DIRECTORY / runtime_id
    directory.mkdir(parents=True)
    models = []
    for index in (1, 2, 3):
        manifest = encode({'config': {'digest':str(index)*64, 'mediaType':'config', 'size':1},
                           'layers': [{'digest':str(index)*64, 'mediaType':'application/vnd.ollama.image.model', 'size':1}]})
        model = repository.tables['models'][index]
        model['digest'] = digest(manifest)
        identity = dict(name=model['name'], digest=model['digest'], runtime_identity=runtime_id,
            template_sha256=digest(b'FABRICATED template'), show=f'{runtime_id}/{index}-show.json',
            manifest=f'{runtime_id}/{index}-manifest.json', layers=[json.loads(manifest)['config'], *json.loads(manifest)['layers']])
        (directory/f'{index}-show.json').write_bytes(encode({'template':'FABRICATED template'}))
        (directory/f'{index}-manifest.json').write_bytes(manifest)
        models.append(identity)
    path = directory/'runtime-binding.json'
    path.write_bytes(encode(dict(runtime=dict(format='evaluation-v2-runtime-identity-v1', runtime_identity=runtime_id), models=models)))
    return repository, tmp_path, path


def make_plan(prepared, **overrides):
    repo, root, runtime = prepared
    return demo.plan(repo, case_id=21, model_ids=[1], repetitions=1, runtime_path=runtime, root=root, **overrides)


def native_transport(url, payload):
    if url.endswith('/api/chat'):
        assert payload['_debug_render_only'] is True and payload['truncate'] is False
        return encode({'_debug_info': {'rendered_template': '\n'.join(m['content'] for m in payload['messages'])}})
    assert url == 'http://127.0.0.1:19876/tokenize'
    assert payload['add_special'] is True and payload['parse_special'] is True
    return encode({'tokens': [1, 2, 3]})


def execute(prepared, plan, **overrides):
    repo, root, _ = prepared
    options = dict(root=root, spool=root/'spool', live_check=lambda *a: True,
                   transport=native_transport, runner=lambda i: ('FABRICATED runner', 'http://127.0.0.1:19876/tokenize'),
                   client=object())
    options.update(overrides)
    return demo.execute(repo, plan, **options)


def test_plan_is_read_only_exact_p2_and_one_default_run(prepared):
    repo, _, _ = prepared
    before = deepcopy(repo.tables), dict(repo.files)
    plan = make_plan(prepared)
    assert plan.summary['planned'] == 1 and plan.summary['scientific_evaluation'] is False
    assert plan.summary['dataset_id'] == 1 and plan.summary['run_config_ids'] == [1]
    assert plan.schedule[0]['seed'] == 101 and plan.schedule[0]['dataset_case_id'] == 21
    req = plan.requests[1]
    payload = json.loads(req.body)
    assert payload['format'] == 'json' and payload['options'] == {**request.OPTIONS, 'seed':101}
    assert payload['messages'][0]['content'].encode() == PROMPT
    assert 'CASE-11' not in payload['messages'][1]['content']
    assert 'Future Service' not in payload['messages'][1]['content']
    assert (repo.tables, repo.files) == before and repo.writes == []


def test_multiple_models_and_repetitions_use_existing_seeds(prepared):
    repo, root, runtime = prepared
    plan = demo.plan(repo, case_id=21, model_ids=[3, 1], repetitions=3, runtime_path=runtime, root=root)
    assert plan.summary['planned'] == 6
    assert [(s['model_id'], s['repetition'], s['seed']) for s in plan.schedule] == [
        (model, repetition, seed) for model in (3,1) for repetition,seed in request.SEEDS.items()]
    assert [s['run_order'] for s in plan.schedule] == list(range(1,7))


@pytest.mark.parametrize('case_id', [22, 23, 24, 10003, 99999])
def test_protected_or_absent_case_never_loads_runtime_or_writes(prepared, monkeypatch, case_id):
    repo, root, runtime = prepared
    monkeypatch.setattr(demo, 'load_runtime', lambda *a: pytest.fail('Runtime inspected for protected case'))
    with pytest.raises(ValueError, match='eligible'):
        demo.plan(repo, case_id=case_id, model_ids=[1], repetitions=1, runtime_path=runtime, root=root)
    assert repo.writes == []


@pytest.mark.parametrize('repetitions', [0, 4, True, '1'])
def test_invalid_repetitions_never_write(prepared, repetitions):
    repo, root, runtime = prepared
    with pytest.raises(ValueError, match='Repetitions'):
        demo.plan(repo, case_id=21, model_ids=[1], repetitions=repetitions, runtime_path=runtime, root=root)
    assert repo.writes == []


@pytest.mark.parametrize('models', [[], [1,1], [99], [444]])
def test_invalid_model_selection_never_writes(prepared, models):
    repo, root, runtime = prepared
    with pytest.raises(ValueError):
        demo.plan(repo, case_id=21, model_ids=models, repetitions=1, runtime_path=runtime, root=root)
    assert repo.writes == []


def test_missing_compatible_config_never_creates_config(prepared):
    repo, _, _ = prepared
    repo.tables['run_configs'][1]['num_predict'] = 999
    with pytest.raises(ValueError, match='D07'):
        make_plan(prepared)
    assert repo.writes == []


@pytest.mark.parametrize('field', ['template','manifest','path','runtime','digest'])
def test_runtime_binding_checks_native_metadata(prepared, field):
    repo, root, path = prepared
    value = json.loads(path.read_bytes())
    identity = value['models'][0]
    if field == 'template':
        (root/demo.runtime_evidence.DIRECTORY/identity['show']).write_bytes(encode({'template':'changed'}))
    elif field == 'manifest':
        (root/demo.runtime_evidence.DIRECTORY/identity['manifest']).write_bytes(b'{}')
    elif field == 'path':
        identity['show'] = '../outside.json'
    elif field == 'runtime':
        identity['runtime_identity'] = 'changed'
    else:
        identity['digest'] = '0'*64
    path.write_bytes(encode(value))
    with pytest.raises(ValueError):
        make_plan(prepared)
    assert repo.writes == []


@pytest.mark.parametrize('drift', ['reference', 'config', 'body', 'final_membership', 'runtime'])
def test_changed_selection_blocks_before_native_or_writes(prepared, drift):
    repo, _, runtime = prepared
    plan = make_plan(prepared)
    if drift == 'reference': repo.tables['reference_results'][11]['c3'] = 'FAIL'
    elif drift == 'config': repo.tables['run_configs'][1]['num_predict'] = 99
    elif drift == 'body': repo.files[3] = b'{"changed":true}'
    elif drift == 'final_membership': repo.tables['dataset_cases'][24]['case_id'] = 11
    else: runtime.write_bytes(runtime.read_bytes()+b'\n')
    with pytest.raises(ValueError):
        execute(prepared, plan, live_check=lambda *a: pytest.fail('Live runtime contacted after drift'))
    assert repo.writes == []


@pytest.mark.parametrize('failure', ['runtime', 'generation', 'overflow', 'tokens'])
def test_native_failure_creates_no_experiment_or_attempt(prepared, failure):
    repo, _, _ = prepared
    plan = make_plan(prepared)
    def transport(url, payload):
        if failure == 'generation' and url.endswith('/api/chat'):
            return encode({'done':True, 'message':{'content':'unexpected'}})
        if url.endswith('/tokenize') and failure in ('overflow','tokens'):
            return encode({'tokens': [1]*32768 if failure=='overflow' else []})
        return native_transport(url, payload)
    with pytest.raises(ValueError):
        execute(prepared, plan, transport=transport, live_check=lambda *a: failure != 'runtime')
    assert repo.writes == [] and not repo.tables.get('experiments')


def test_reference_drift_during_measurement_blocks_materialization(prepared):
    repo, _, _ = prepared
    plan = make_plan(prepared)
    def transport(url, payload):
        result = native_transport(url, payload)
        if url.endswith('/tokenize'):
            repo.tables['reference_results'][11]['c3'] = 'FAIL'
        return result
    with pytest.raises(ValueError, match='changed after selection'):
        execute(prepared, plan, transport=transport)
    assert repo.writes == []


@pytest.mark.parametrize('digest_prefix', [False, True])
@pytest.mark.parametrize('content,expected', [
    (encode({c:{'verdict':'PASS','reason':'FABRICATED'} for c in ('c1','c2','c3')}).decode(), 'valid'),
    ('```json\n{}\n```', 'parser_failure')])
def test_new_demo_uses_canonical_batch_and_preserves_results(prepared, monkeypatch, content, expected, digest_prefix):
    repo, _, _ = prepared
    if digest_prefix:
        repo.tables['models'][1]['digest'] = 'sha256:' + repo.tables['models'][1]['digest']
    plan = make_plan(prepared)
    calls = []
    def attempt(repository, run_id, **kwargs):
        inputs, req = kwargs['prepare_request'](repository, run_id)
        assert kwargs['verify_runtime'](req, kwargs['context_proof']) is True
        assert kwargs['review_failure'](None, None) == 'ambiguous'
        calls.append((run_id, kwargs['attempt']))
        parsed = parser.parse(content)
        run = repo.tables['experiment_runs'][run_id]
        run.update(result=expected, request_file_id=1)
        repo.add('run_attempts', id=run_id, run_id=run_id, attempt=1, result=expected,
                 response_file_id=3, diagnostics_file_id=None, duration_ms=5)
        if parsed.prediction:
            repo.add('predictions', id=run_id, run_id=run_id, attempt_id=run_id, **parsed.prediction)
    monkeypatch.setattr(batch, 'execute_attempt', attempt)
    result = execute(prepared, plan)
    assert result['status'] == 'COMPLETED' and result['exit_code'] == 0
    assert result['experiment_id'] == 90001 and result['run_ids'] == [91001]
    assert calls == [(91001,1)]
    details = result['results'][0]
    assert details['response_id'] == 10 and details['run']['result'] == expected
    assert details['correctness'] == {c: True if expected=='valid' else None for c in ('c1','c2','c3')}
    created = next(value for action,value in repo.writes if action == 'experiment')
    assert created['name'].startswith('LIVE-DEMO ')
    assert created['dataset_id'] == 1 and created['setup']['format'] == demo.FORMAT
    assert created['setup']['scientific_evaluation'] is False
    assert created['setup']['gate_b_complete'] is True
    assert not repo.tables.get('evaluation_reports')


def test_ambiguous_technical_failure_pauses_without_retry(prepared, monkeypatch):
    from rest_api_checker.experiment.orchestration import Paused
    repo, _, _ = prepared
    plan = make_plan(prepared)
    calls = []
    def attempt(repository, run_id, **kwargs):
        inputs, req = kwargs['prepare_request'](repository, run_id)
        assert kwargs['verify_runtime'](req, kwargs['context_proof']) is True
        calls.append((run_id, kwargs['attempt']))
        repo.add('run_attempts', id=run_id, run_id=run_id, attempt=1, result=None,
                 response_file_id=3, diagnostics_file_id=None)
        raise Paused('FAILURE_ATTRIBUTION_ambiguous')
    monkeypatch.setattr(batch, 'execute_attempt', attempt)
    result = execute(prepared, plan)
    assert result['status'] == 'BLOCKED' and result['exit_code'] == 3
    assert calls == [(91001,1)] and result['pending'] == 1
    assert result['experiment_id'] == 90001 and result['run_ids'] == [91001]
    assert result['results'][0]['prediction'] is None
    assert 'FAILURE_ATTRIBUTION_ambiguous' in result['message']


@pytest.mark.parametrize('failure', ['setup_read', 'commit_acknowledgement'])
def test_post_creation_failure_retains_recovery_ids(prepared, monkeypatch, failure):
    from contextlib import contextmanager
    repo, _, _ = prepared
    plan = make_plan(prepared)
    events = []
    if failure == 'setup_read':
        original = repo._row
        def read(table, row_id):
            if table == 'experiments':
                raise OSError('fabricated unavailable database')
            return original(table, row_id)
        monkeypatch.setattr(repo, '_row', read)
    else:
        @contextmanager
        def transaction():
            yield
            raise OSError('fabricated lost commit acknowledgement')
        monkeypatch.setattr(repo, 'transaction', transaction)
    monkeypatch.setattr(batch, 'run', lambda *a, **k: pytest.fail('Provider dispatch after persistence failure'))
    result = execute(prepared, plan, notify=events.append)
    assert result['status'] == 'BLOCKED' and result['exit_code'] == 3
    assert result['experiment_id'] == 90001 and result['run_ids'] == [91001]
    assert result['results'] == [] and result['spool']
    if failure == 'setup_read':
        assert any(e.get('event') == 'created' and e['experiment_id'] == 90001 for e in events)


def test_unwritable_spool_creates_no_experiment(prepared):
    repo, root, _ = prepared
    plan = make_plan(prepared)
    (root/'spool').write_text('existing file, not directory')
    with pytest.raises(OSError):
        execute(prepared, plan)
    assert repo.writes == [] and not repo.tables.get('experiments')


def test_parser_drift_after_confirmation_blocks_before_runtime(prepared, monkeypatch):
    repo, _, _ = prepared
    plan = make_plan(prepared)
    monkeypatch.setattr(demo.parser, 'artifact_hash', lambda: '0'*64)
    with pytest.raises(ValueError, match='Parser changed after selection'):
        execute(prepared, plan, live_check=lambda *a: pytest.fail('Runtime contacted after parser drift'))
    assert repo.writes == []
