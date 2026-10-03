"""Fabricated repository/transport boundaries; no scientific state or live HTTP."""
from contextlib import nullcontext
from copy import deepcopy
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rest_api_checker import batch_terminal, cli, evaluation_batch_v2 as v2, terminal
from rest_api_checker.experiment import batch, orchestration, parser, renderer, request_v2
from rest_api_checker.experiment.encoding import digest, encode
from rest_api_checker.experiment.request import MODELS, SEEDS
from rest_api_checker.persistence import inspection
from rest_api_checker.persistence.database import require

ROOT = Path(__file__).resolve().parents[1]
PROMPT = (ROOT.parent/'bachelor_rest_api_checker/03_research_design/prompt_candidates_v1/p2_structured_checklist_v1.txt').read_bytes()


class FakeRepo:
    def __init__(self):
        self.cn = SimpleNamespace(commit=lambda: None)
        self.tables = {}
        self.files = {1: PROMPT, 2: b'{}', 3: b'{}'}
        self.writes = 0

    def _row(self, table, row_id):
        require(row_id in self.tables.get(table, {}), 'Missing '+table+' row')
        return deepcopy(self.tables[table][row_id])

    def file(self, file_id):
        return self.files[file_id]

    def source(self, file_id, pointer):
        return json.loads(self.file(file_id))

    def verify_closure(self, files):
        for item in files:
            require(digest(self.file(item['file_id'])) == item['sha256'], 'Source closure drift')

    def require_d07(self, config_id, name):
        require(config_id == MODELS.index(name)+1, 'Configuration drift')

    def dispatch_owner(self):
        return nullcontext()

    def complete_experiment(self, experiment_id, **kwargs):
        self.tables['experiments'][experiment_id]['finished_at'] = kwargs['finished_at']

    def execution_inputs(self, run_id):
        run = self._row('experiment_runs', run_id)
        raw = self.file(9)
        return dict(run=run, setup=json.loads(raw), setup_sha256=digest(raw),
            evidence=renderer.Evidence(encode({'openapi':'3.0.4','paths':{'/x':{'post':{'responses':{
                '200':{'description':'ok','content':{'application/json':{'schema':{'type':'object'}}}}}}}}}),
                'post','/x',200,'application/json',b'{}'), contract_identity='files:2', body_identity='files:3',
            prompt_name='P2', prompt=PROMPT, model=self._row('models',run['model_id']))


@pytest.fixture
def prepared(monkeypatch, tmp_path):
    repo = FakeRepo()
    def add(table, **row):
        repo.tables.setdefault(table, {})[row['id']] = row
    def read(repository, table, **filters):
        return [deepcopy(r) for _,r in sorted(repository.tables.get(table, {}).items())
                if all(r[k] == v for k,v in filters.items())]
    monkeypatch.setattr(v2, 'rows', read)
    monkeypatch.setattr(inspection, 'rows', read)
    monkeypatch.setattr(batch, 'rows', read)
    from rest_api_checker import main_v2_authorization
    monkeypatch.setattr(main_v2_authorization, 'rows', read)
    add('datasets', id=1, name='FABRICATED ELIGIBILITY FIXTURE', version='test-only', purpose='evaluation')
    add('dataset_cases', id=1, dataset_id=1, case_id=1, reference_id=1, case_code='TEST-CASE', position=1)
    add('reference_results', id=1, case_id=1, source_file_id=3, source_pointer='')
    add('test_cases', id=1, operation_id=1, response_id=1)
    add('responses', id=1, body_file_id=3)
    add('api_operations', id=1, contract_id=1)
    add('api_contracts', id=1, file_id=2, api_id=1)
    add('apis', id=1, name='SYNTHETIC API')
    add('prompts', id=1, name='P2', file_id=1)
    identities, schedule = [], []
    directory = tmp_path/v2.runtime_evidence.DIRECTORY
    directory.mkdir(parents=True)
    for n, model in enumerate(MODELS, 1):
        add('models', id=n, name=model, digest=str(n)*64)
        add('run_configs', id=n)
        (directory/f'{n}.json').write_bytes(encode({'template':'test-template'}))
        identities.append(dict(name=model, digest=str(n)*64, show=f'{n}.json', template_sha256=digest(b'test-template')))
        for rep, seed in SEEDS.items():
            slot = dict(dataset_case_id=1, model_id=n, prompt_id=1, run_config_id=n, repetition=rep,
                        seed=seed, run_order=len(schedule)+1)
            schedule.append(slot)
            add('experiment_runs', id=len(schedule), experiment_id=1, result=None, request_file_id=None, **slot)
    setup = dict(format='main-evaluation-setup-v2', dataset_id=1, schedule_seed=17,
        schedule=schedule, files=[dict(file_id=3, sha256=digest(b'{}'))],
        parser_sha256=parser.artifact_hash(), renderer_sha256=renderer.artifact_hash(),
        request_builder_sha256=request_v2.artifact_hash(), models=identities,
        runtime={'ollama':{'version':'TEST QUALIFICATION'}}, output_interface={'mode':'format_json'},
        gate_b_complete=True, plan_authorized=True, execution_authorized=False)
    setup['bindings'] = inspection.bindings(repo, 1, schedule)
    add('experiments', id=1, dataset_id=1, setup_file_id=9, schedule_seed=17, kind='evaluation', finished_at=None)
    repo.files[9] = encode(setup)
    inventory, proofs = [], {}
    for run in repo.tables['experiment_runs'].values():
        _, req = v2.prepare(repo, run['id'])
        inventory.append(dict(run_order=run['run_order'], sha256=digest(req.body),
                              request_identity_sha256=req.metadata['request_identity_sha256']))
        proofs[str(run['run_order'])] = dict(request_sha256=digest(req.body), model_digest=req.metadata['model_digest'],
            template_sha256=digest(b'test-template'), measurement_sha256='f'*64, input_tokens=100)
    setup.update(request_inventory=inventory, context_proofs=proofs)
    repo.files[9] = encode(setup)
    fabricated_authorization(repo)
    return repo, tmp_path


def fabricated_authorization(repo):
    from rest_api_checker.main_v2_authorization import execution_binding
    setup = json.loads(repo.files[9])
    setup.pop('execution_authorization', None)
    setup['execution_authorized'] = False
    repo.files[10] = encode(setup)
    repo.files[11] = encode(dict(decision='AUTHORIZE_MAIN_V2_EXECUTION', author='FABRICATED TEST ONLY',
        accepted_at='2026-10-03T12:00:00+02:00', **execution_binding(repo.files[10], 1, 1, 'TEST ONLY')))
    repo.files[9] = encode({**setup, 'execution_authorized': True, 'execution_authorization': dict(
        plan_file_id=10, plan_sha256=digest(repo.files[10]), authorization_file_id=11, authorization_sha256=digest(repo.files[11]))})


def preflight(prepared, **kwargs):
    repo, root = prepared
    return v2.preflight(repo, 1, 1, database='TEST ONLY', root=root, **kwargs)


def change_setup(repo, update):
    setup = json.loads(repo.files[9])
    update(setup)
    repo.files[9] = encode(setup)


def settle(repo, run_id, result):
    _, req = v2.prepare(repo, run_id)
    file_id = 100+run_id
    repo.files[file_id] = req.body
    repo.tables['experiment_runs'][run_id].update(result=result, request_file_id=file_id)
    repo.tables.setdefault('run_attempts', {})[run_id] = dict(id=run_id, run_id=run_id, attempt=1, result=result, started_at='TEST')
    if result == 'valid':
        repo.tables.setdefault('predictions', {})[run_id] = dict(id=run_id, run_id=run_id, attempt_id=run_id)


def test_full_preflight_is_read_only_and_complete(prepared):
    repo, _ = prepared
    before = deepcopy(repo.tables), dict(repo.files)
    calls = []
    plan = preflight(prepared, live_check=lambda *a: calls.append(a) or True)
    assert plan.summary['planned'] == 9
    assert plan.summary['seeds'] == [101,202,303]
    assert plan.summary['output_mode'] == 'format_json'
    assert plan.summary['token_limit'] == 512
    assert len(plan.requests) == 9 and len(calls) == 1
    assert (repo.tables, repo.files) == before and repo.writes == 0


@pytest.mark.parametrize('failure', ['missing','empty','reference','model','seed','schedule','prompt','config','request','context','authorization','duplicate'])
def test_preflight_failures_before_runtime_or_executor(prepared, failure):
    repo, _ = prepared
    if failure == 'missing': repo.tables['datasets'].clear()
    elif failure == 'empty': repo.tables['dataset_cases'].clear()
    elif failure == 'reference': repo.tables['dataset_cases'][1]['reference_id'] = None
    elif failure == 'model': repo.tables['models'][1]['name'] = 'absent'
    elif failure == 'seed': repo.tables['experiment_runs'][1]['seed'] = 999
    elif failure == 'schedule': repo.tables['experiment_runs'].pop(1)
    elif failure == 'prompt': repo.files[1] = b'changed'
    elif failure == 'config': repo.tables['experiment_runs'][1]['run_config_id'] = 99
    elif failure == 'request': change_setup(repo, lambda s: s['request_inventory'][0].update(sha256='0'*64))
    elif failure == 'context': change_setup(repo, lambda s: s['context_proofs']['1'].update(input_tokens=999999))
    elif failure == 'authorization': change_setup(repo, lambda s: s.update(plan_authorized=False))
    else: repo.tables['experiments'][2] = {**repo.tables['experiments'][1], 'id':2}
    with pytest.raises((ValueError, KeyError)):
        preflight(prepared, live_check=lambda *a: pytest.fail('Runtime must not be checked'))
    assert repo.writes == 0


@pytest.mark.parametrize('error', [ConnectionRefusedError('unavailable'), ValueError('Ollama version drift')])
def test_runtime_failure(prepared, error):
    def unavailable(*args): raise error
    with pytest.raises(type(error), match=str(error)):
        preflight(prepared, live_check=unavailable)


def run_fake(prepared, monkeypatch, outcomes, *, resume=False, stop=None):
    repo, root = prepared
    plan = preflight(prepared, live_check=lambda *a: True)
    calls, events = [], []
    def attempt(repository, run_id, **kwargs):
        # Exercise the real batch scheduler and the injected v2 preparation hook.
        inputs, req = kwargs['prepare_request'](repository, run_id)
        kwargs['context_proof'].verify(req)
        assert kwargs['verify_runtime'](req, kwargs['context_proof'])
        calls.append(run_id)
        outcome = outcomes[len(calls)-1]
        if isinstance(outcome, BaseException):
            repo.tables.setdefault('run_attempts', {})[run_id] = dict(id=run_id, run_id=run_id, attempt=1, result=None, started_at='TEST')
            raise outcome
        settle(repo, run_id, outcome)
        repo.writes += 1
    monkeypatch.setattr(batch, 'execute_attempt', attempt)
    result = v2.execute(repo, plan, root=root, spool=root/'spool', resume=resume,
                        notify=events.append, client=object(), live_check=lambda *a: True, stop=stop)
    return result, calls, events


def test_parser_failure_continues_and_counts_are_canonical(prepared, monkeypatch):
    result, calls, events = run_fake(prepared, monkeypatch, ['valid','parser_failure']+['valid']*7)
    assert result['exit_code'] == 0 and result['executed_now'] == 9
    assert result['counts_now'] == dict(valid=8, parser_failure=1, technical_failure=0)
    assert calls == list(range(1,10))
    current = [e['current'] for e in events if e['event'] == 'current']
    assert [(c['model'],c['seed']) for c in current] == [(m,s) for m in MODELS for s in SEEDS.values()]


def test_technical_failure_stops_without_retry_and_blocks_resume(prepared, monkeypatch):
    result, calls, _ = run_fake(prepared, monkeypatch, [orchestration.Paused('FAILURE_ATTRIBUTION_ambiguous')])
    assert result['exit_code'] == 3 and calls == [1]
    assert result['counts_now']['parser_failure'] == 0 and result['technical_problems'] == 1
    plan = preflight(prepared, live_check=lambda *a: True)
    assert plan.summary['problematic'] == 1 and plan.summary['to_execute'] == 0
    assert plan.summary['missing_unattempted'] == 8
    with pytest.raises(ValueError, match='RECONCILIATION'): v2.require_continuation(plan, True)


def test_resume_preserves_completed_and_executes_only_missing(prepared, monkeypatch):
    repo, _ = prepared
    settle(repo, 1, 'parser_failure')
    plan = preflight(prepared, live_check=lambda *a: True)
    with pytest.raises(ValueError, match='--resume'): v2.require_continuation(plan, False)
    result, calls, _ = run_fake(prepared, monkeypatch, ['valid']*8, resume=True)
    assert calls == list(range(2,10)) and result['executed_now'] == 8
    assert result['plan']['previously_complete'] == 1 and result['completed'] == 9
    assert repo.tables['experiment_runs'][1]['result'] == 'parser_failure'


def test_interrupt_stops_before_next_call(prepared, monkeypatch):
    result, calls, _ = run_fake(prepared, monkeypatch, [], stop=batch.StopRequest(True))
    assert result['exit_code'] == 130 and result['interrupted'] and not calls


def test_interrupt_during_attempt_preserves_problem_and_never_retries(prepared, monkeypatch):
    result, calls, _ = run_fake(prepared, monkeypatch, [KeyboardInterrupt()])
    assert result['exit_code'] == 130 and result['interrupted'] and calls == [1]
    assert result['executed_now'] == 1 and result['completed'] == 0
    assert preflight(prepared, live_check=lambda *a: True).summary['problematic'] == 1


def test_unexpected_database_failure_is_not_parser_failure(prepared, monkeypatch):
    def failed(*a, **k): raise RuntimeError('secret driver information')
    monkeypatch.setattr(batch, 'run', failed)
    repo, root = prepared
    result = v2.execute(repo, preflight(prepared, live_check=lambda *a: True), root=root,
        spool=root/'spool', resume=False, notify=lambda e: None, client=object())
    assert result['exit_code'] == 3 and result['counts_now'] is None
    assert 'secret' not in json.dumps(result)


def test_status_no_runtime_and_breakdown(prepared):
    repo, _ = prepared
    settle(repo, 1, 'valid')
    result = v2.inspect_plan(repo, 1, 1, database='test').summary
    assert result['previously_complete'] == 1 and result['remaining'] == 8
    assert result['model_breakdown'][0]['valid'] == 1
    assert [r['planned'] for r in result['repetition_breakdown']] == [3,3,3]


def test_cli_dry_run_no_executor_or_prediction_write(prepared, monkeypatch, capsys):
    repo, root = prepared
    repo.files[9] = repo.files[10]  # Pristine plan, no execution authorization.
    original = v2.preflight
    monkeypatch.setattr(v2, 'preflight', lambda *a, **k: original(*a, **k, live_check=lambda *a: True))
    monkeypatch.setattr(v2, 'execute', lambda *a, **k: pytest.fail('Dry-run execution'))
    before = deepcopy(repo.tables), dict(repo.files)
    args = cli.arguments().parse_args(['experiment','run-batch','1','--dataset-id','1','--root',str(root),'--dry-run','--plain'])
    value, code = cli._batch_v2(repo, args, terminal.console(plain=True))
    cli.present(terminal.console(plain=True), args, value)
    out = capsys.readouterr().out
    assert code == 0 and value['model_calls'] == value['prediction_writes'] == 0
    assert all(t in out for t in ('Evaluation v2 Main','format_json','101, 202, 303','TEST QUALIFICATION','DRY RUN'))
    assert 'Execution authorization' in out and 'NOT GRANTED' in out
    assert (repo.tables, repo.files) == before


def test_noninteractive_requires_yes(prepared, monkeypatch):
    repo, root = prepared
    plan = preflight(prepared, live_check=lambda *a: True)
    monkeypatch.setattr(v2, 'preflight', lambda *a, **k: plan)
    args = cli.arguments().parse_args(['experiment','run-batch','1','--dataset-id','1','--spool',str(root),'--json'])
    with pytest.raises(ValueError, match='--yes'): cli._batch_v2(repo, args, terminal.console())


def test_demo_no_connections_or_executor_and_shared_display(monkeypatch, capsys):
    def forbidden(*a, **k): pytest.fail('Scientific boundary used in simulation')
    for name in ('connect','Repository','read_settings'): monkeypatch.setattr(cli, name, forbidden)
    monkeypatch.setattr(v2, 'execute', forbidden)
    monkeypatch.setattr(v2, 'OllamaClient', forbidden)
    monkeypatch.setattr(parser, 'parse', forbidden)
    assert cli.main(['experiment','demo-batch','--delay','0','--json']) == 0
    value = json.loads(capsys.readouterr().out)
    assert value['simulated'] and value['model_calls'] == value['prediction_writes'] == 0
    assert value['simulated_steps'] == 27 and value['counts_now']['parser_failure'] == 3
    plan = value['plan']
    assert plan['dataset'] == dict(id='demo-dataset-v2-001', name='SYNTHETIC DEMO', version='presentation-only')
    assert plan['experiment_id'] == 'demo-main-v2-001'
    assert plan['runtime'] == {'ollama': {'version': '0.35.0 · SIMULATED / NOT CONTACTED'}}
    assert plan['output_mode'] == 'format_json · SIMULATED'
    assert plan['prompt'] == 'P2' and plan['prompt_sha256'] == 'DEMO-PROMPT-HASH'
    assert plan['setup_sha256'] == 'DEMO-SETUP-HASH'
    assert cli.main(['experiment','demo-batch','--delay','0','--plain']) == 0
    text = capsys.readouterr().out
    assert 'DEMO / SIMULATION' in text and 'NO PREDICTION WRITES' in text
    assert 'Simulated steps' in text and 'Real executions' in text and 'ETA (estimate)' in text


def test_simulation_order_and_interrupt():
    all_events = []
    for _ in range(2):
        events = []
        v2.simulate(v2.demo_plan(), notify=lambda e: events.append(deepcopy(e)), delay=0)
        all_events.append(events)
    assert all_events[0] == all_events[1]
    def interrupt(_): raise KeyboardInterrupt
    result = v2.simulate(v2.demo_plan(), notify=lambda e: None, sleep=interrupt)
    assert result['exit_code'] == 130 and result['model_calls'] == 0


@pytest.mark.parametrize('extra', ['--yes','--resume','--dry-run','--spool'])
def test_demo_rejects_execution_options(extra):
    with pytest.raises(SystemExit): cli.arguments().parse_args(['experiment','demo-batch',extra])


def test_live_and_plain_share_safe_renderer():
    from rich.console import Console
    stream = io.StringIO()
    plan = v2.demo_plan()
    display = batch_terminal.Display(Console(file=stream, force_terminal=True, width=120), plan.summary)
    display.event(dict(event='current', current={**plan.labels[1], 'case':'\x1b[31mUNTRUSTED'}))
    display.console.print(display)
    assert '\\x1b[31mUNTRUSTED' in stream.getvalue()


@pytest.mark.parametrize('mode', request_v2.MODES)
def test_adapter_reuses_exact_v2_request_builder(prepared, mode):
    repo, _ = prepared
    change_setup(repo, lambda s: s.update(output_interface={'mode':mode}))
    inputs, req = v2.prepare(repo, 1)
    expected = request_v2.build_request_v2(renderer.render(inputs['evidence'], contract_identity='files:2', body_identity='files:3'),
        interface=request_v2.OutputInterfaceV2(mode), prompt=PROMPT, model=MODELS[0], model_digest='1'*64, repetition=1)
    assert req == expected


def test_completed_without_prediction_cannot_resume(prepared):
    repo, _ = prepared
    settle(repo, 1, 'valid')
    repo.tables['predictions'].clear()
    with pytest.raises(ValueError, match='Prediction/terminal'):
        preflight(prepared, live_check=lambda *a: True)


def test_persisted_request_drift_cannot_resume(prepared):
    repo, _ = prepared
    settle(repo, 1, 'valid')
    repo.files[101] += b' '
    with pytest.raises(ValueError, match='Persisted request'):
        preflight(prepared, live_check=lambda *a: True)


def test_unordered_database_results_keep_frozen_order(prepared, monkeypatch):
    original = inspection.rows
    def unordered(repo, table, **filters):
        result = original(repo, table, **filters)
        return list(reversed(result)) if table == 'experiment_runs' else result
    monkeypatch.setattr(inspection, 'rows', unordered)
    result, calls, _ = run_fake(prepared, monkeypatch, ['valid']*9)
    assert result['exit_code'] == 0 and calls == list(range(1,10))


def test_completed_resume_has_zero_new_calls(prepared, monkeypatch):
    repo, _ = prepared
    for run_id in range(1,10): settle(repo, run_id, 'parser_failure')
    repo.tables['experiments'][1]['finished_at'] = 'TEST'
    result, calls, _ = run_fake(prepared, monkeypatch, [], resume=True)
    assert not calls and result['exit_code'] == 0 and result['executed_now'] == 0


@pytest.mark.parametrize('code', [0,3,130])
def test_cli_yes_routes_shared_executor_and_returns_code(prepared, monkeypatch, code):
    repo, root = prepared
    plan = preflight(prepared, live_check=lambda *a: True)
    monkeypatch.setattr(v2, 'preflight', lambda *a, **k: plan)
    monkeypatch.setattr(v2, 'repository_commit', lambda root: 'a'*40)
    calls = []
    monkeypatch.setattr(v2, 'execute', lambda *a, **k: calls.append(k) or dict(plan=plan.summary, exit_code=code))
    args = cli.arguments().parse_args(['experiment','run-batch','1','--dataset-id','1','--spool',str(root/'spool'),'--yes','--json'])
    value, actual = cli._batch_v2(repo, args, terminal.console())
    assert actual == code and len(calls) == 1 and value['repository_commit'] == 'a'*40


def test_cli_decline_does_not_execute(prepared, monkeypatch):
    repo, root = prepared
    plan = preflight(prepared, live_check=lambda *a: True)
    monkeypatch.setattr(v2, 'preflight', lambda *a, **k: plan)
    monkeypatch.setattr(cli.sys, 'stdin', SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr('builtins.input', lambda: '')
    monkeypatch.setattr(v2, 'execute', lambda *a, **k: pytest.fail('Declined execution'))
    args = cli.arguments().parse_args(['experiment','run-batch','1','--dataset-id','1','--spool',str(root)])
    value, code = cli._batch_v2(repo, args, terminal.console(plain=True))
    assert code == 0 and value['status'] == 'CANCELLED'


def test_cli_preflight_error_exit_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(cli, 'read_settings', lambda p: {})
    monkeypatch.setattr(cli, 'connect', lambda *a: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(cli, 'Repository', lambda cn: object())
    def failed(*a, **k): raise ValueError('Runtime mismatch')
    monkeypatch.setattr(v2, 'preflight', failed)
    assert cli.main(['experiment','run-batch','1','--dataset-id','1','--env-file','unused','--dry-run','--json']) == 3
    value = json.loads(capsys.readouterr().out)
    assert value['status'] == 'BLOCKED' and value['error'] == 'Runtime mismatch'


def test_spool_unwritable_shape_rejected(tmp_path):
    path = tmp_path/'file'
    path.write_bytes(b'preserve')
    with pytest.raises(OSError): v2.prepare_spool(path)
    assert path.read_bytes() == b'preserve'


def test_plan_size_is_not_fixed_to_one_dataset(prepared):
    repo, _ = prepared
    setup = json.loads(repo.files[9])
    repo.tables['test_cases'][2] = {**repo.tables['test_cases'][1], 'id':2}
    repo.tables['reference_results'][2] = {**repo.tables['reference_results'][1], 'id':2, 'case_id':2}
    repo.tables['dataset_cases'][2] = {**repo.tables['dataset_cases'][1], 'id':2, 'case_id':2,
                                     'reference_id':2, 'position':2, 'case_code':'TEST-SECOND'}
    for n in range(1,10):
        slot = {**setup['schedule'][n-1], 'dataset_case_id':2, 'run_order':n+9}
        setup['schedule'].append(slot)
        repo.tables['experiment_runs'][n+9] = {**repo.tables['experiment_runs'][n], 'id':n+9, **slot}
        setup['request_inventory'].append({**setup['request_inventory'][n-1], 'run_order':n+9})
        setup['context_proofs'][str(n+9)] = setup['context_proofs'][str(n)]
    setup['bindings'] = inspection.bindings(repo, 1, setup['schedule'])
    repo.files[9] = encode(setup)
    fabricated_authorization(repo)
    plan = preflight(prepared, live_check=lambda *a: True)
    assert plan.summary['cases'] == 2 and plan.summary['planned'] == 18
