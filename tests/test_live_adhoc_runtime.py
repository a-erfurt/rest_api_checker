"""Fabricated metadata/provider evidence only; no live SQL or model calls."""
from copy import deepcopy
from dataclasses import asdict, replace
import inspect
import json
from types import SimpleNamespace

import pytest

from rest_api_checker import live_adhoc_runtime as adhoc, live_demo as demo
from rest_api_checker.experiment import batch, orchestration, parser, request, request_v2
from rest_api_checker.experiment.encoding import digest, encode
from rest_api_checker.experiment.provider import OllamaClient
from test_live_demo import repository, prepared  # noqa: F401; shared fabricated fixtures


def api_for(repo, version='0.40.0'):
    def api(path, data=None):
        assert path in ('/api/version', '/api/tags', '/api/show', '/api/ps')
        if path == '/api/version':
            return {'version': version}
        if path == '/api/tags':
            return {'models': [{'name': m['name'], 'digest': m['digest']}
                               for m in repo.tables['models'].values()]}
        if path == '/api/ps':
            return {'models': [{'name': repo.tables['models'][1]['name']}]}
        return {'template': 'FABRICATED native template', 'parameters': 'FABRICATED', 'system': ''}
    return api


def make_plan(repo, root, repetitions=1):
    return demo.plan(repo, case_id=21, model_ids=[1], repetitions=repetitions, root=root, adhoc=True)


def scope(req, **overrides):
    result = dict(format=adhoc.FORMAT, live_adhoc=True, scientific_evaluation=False,
                  gate_b_complete=False, dataset_id=1, fabricated=False,
                  request_inventory=[{'sha256': digest(req.body)}])
    result.update(overrides)
    return result


def test_plan_is_offline_current_runtime_independent(repository, tmp_path, monkeypatch):
    monkeypatch.setattr(adhoc, 'metadata', lambda *a: pytest.fail('No network during selection'))
    monkeypatch.setattr(demo, 'load_runtime', lambda *a: pytest.fail('No thesis runtime path in ad-hoc plan'))
    value = make_plan(repository, tmp_path)
    assert value.adhoc and value.runtime_path is None and value.binding == {} and value.sources == {}
    assert value.summary['runtime_policy'] == 'live_adhoc' and value.summary['prompt'] == 'P2'
    assert value.summary['repetitions'] == 1 and value.summary['destination'].startswith('NEW LIVE-ADHOC')
    assert repository.writes == []


def test_strict_plan_still_requires_explicit_runtime(repository, tmp_path):
    with pytest.raises(ValueError, match='qualified runtime'):
        demo.plan(repository, case_id=21, model_ids=[1], repetitions=1, root=tmp_path)
    assert repository.writes == []


def test_version_difference_is_informational(repository):
    result = adhoc.probe_runtime(api=api_for(repository))
    assert result['available'] is True and result['version'] == '0.40.0'
    assert 'Runtime differs' in result['notice'] and 'Interactive checks remain available' in result['notice']
    assert 'live/ad-hoc' not in result['notice'].lower() and 'thesis' not in result['notice'].lower()


def test_metadata_unavailable_does_not_block_discovery():
    def fail(*args):
        raise OSError('FABRICATED unavailable')
    assert adhoc.probe_runtime(api=fail)['available'] is False
    assert adhoc.model_availability(api=fail) is None


def test_availability_uses_metadata_only(repository):
    result = adhoc.model_availability(api=api_for(repository))
    assert result[request.MODELS[0]] == 'installed · loaded'
    assert result[request.MODELS[1]] == 'installed · not loaded'


def test_capture_records_current_unqualified_runtime_and_model_template(repository):
    selected = [repository._row('models', 1)]
    binding, sources = adhoc.capture(selected, api=api_for(repository))
    assert binding['runtime']['ollama']['version'] == '0.40.0'
    assert binding['runtime']['scientifically_qualified'] is False
    assert binding['models'][0]['template_sha256'] == digest(b'FABRICATED native template')
    assert adhoc.verify_live(binding, sources, api=api_for(repository)) is True
    assert repository.writes == []


@pytest.mark.parametrize('change', ['version', 'digest', 'template'])
def test_current_runtime_drift_still_blocks(repository, change):
    api = api_for(repository)
    binding, sources = adhoc.capture([repository._row('models', 1)], api=api)
    def changed(path, data=None):
        value = api(path, data)
        if change == 'version' and path == '/api/version': value['version'] = '0.41.0'
        if change == 'digest' and path == '/api/tags': value['models'][0]['digest'] = 'e'*64
        if change == 'template' and path == '/api/show': value['template'] = 'changed'
        return value
    with pytest.raises(ValueError):
        adhoc.verify_live(binding, sources, api=changed)


def test_context_guard_never_claims_native_token_measurement(repository, tmp_path):
    plan = make_plan(repository, tmp_path)
    binding, sources = adhoc.capture([repository._row('models', 1)], api=api_for(repository))
    check = adhoc.context_check(plan.requests[1], binding['models'][0], sources)
    assert check.method == adhoc.CONTEXT_METHOD
    assert 'input_tokens' not in asdict(check) and check.budget_units > len(plan.requests[1].body)
    with pytest.raises(ValueError, match='context budget'):
        replace(check, template_bytes=100_000).verify(plan.requests[1])
    with pytest.raises(ValueError, match='request/model'):
        replace(check, request_sha256='f'*64).verify(plan.requests[1])


@pytest.mark.parametrize('changes,experiment,dataset', [
    ({}, 10003, 1), ({'dataset_id': 3}, 90001, 3),
    ({'format': 'main-evaluation-setup-v2'}, 90001, 1),
    ({'scientific_evaluation': True}, 90001, 1),
    ({'gate_b_complete': True}, 90001, 1),
    ({'live_adhoc': False}, 90001, 1),
])
def test_adhoc_transport_refuses_final_or_mislabelled_setup(repository, tmp_path, changes, experiment, dataset):
    req = make_plan(repository, tmp_path).requests[1]
    with pytest.raises(ValueError):
        adhoc.AdhocClient(scope(req, **changes), experiment, dataset, client=object())


def test_adhoc_transport_only_sends_its_exact_prepared_requests(repository, tmp_path):
    req = make_plan(repository, tmp_path, repetitions=2).requests
    called = []
    underlying = SimpleNamespace(send=lambda value, **kwargs: called.append(value) or 'receipt')
    client = adhoc.AdhocClient(scope(req[1]), 90001, 1, client=underlying)
    assert client.send(req[1], on_start=lambda value: None) == 'receipt'
    with pytest.raises(ValueError, match='outside this interactive context'):
        client.send(req[2], on_start=lambda value: None)
    assert called == [req[1]]


def test_default_batch_factory_is_still_strict_context_proof():
    assert inspect.signature(batch.run).parameters['context_proof_factory'].default is request.ContextProof


def test_stock_scientific_client_still_requires_gate_b(repository, tmp_path):
    req = make_plan(repository, tmp_path).requests[1]
    proof = request.ContextProof(digest(req.body), req.metadata['model_digest'], 'a'*64, 'b'*64, 2)
    inputs = {'run': {'run_order': 1}, 'setup': {'context_proofs': {'1': asdict(proof)}, 'gate_b_complete': False}}
    with pytest.raises(ValueError, match='GATE_B_NOT_COMPLETE'):
        orchestration.execute_attempt(repository, 1, attempt=1,
            client=OllamaClient(request_validator=request_v2.validate_request_v2), spool_directory=tmp_path,
            context_proof=proof, verify_runtime=lambda *args: pytest.fail('Blocked before runtime'),
            prepare_request=lambda *args: (inputs, req))
    assert repository.writes == []


@pytest.mark.parametrize('content,expected', [
    (encode({c: {'verdict': 'PASS', 'reason': 'FABRICATED'} for c in ('c1', 'c2', 'c3')}).decode(), 'valid'),
    ('```json\n{}\n```', 'parser_failure')])
def test_multiple_adhoc_runs_reuse_canonical_batch_and_emit_immediate_results(repository, tmp_path, monkeypatch, content, expected):
    plan = make_plan(repository, tmp_path, repetitions=3)
    events, executions = [], []
    def attempt(repo, run_id, **kwargs):
        inputs, req = kwargs['prepare_request'](repo, run_id)
        assert isinstance(kwargs['context_proof'], adhoc.AdhocContextCheck)
        assert kwargs['verify_runtime'](req, kwargs['context_proof']) is True
        assert isinstance(kwargs['client'], adhoc.AdhocClient)
        assert inputs['setup']['gate_b_complete'] is False
        assert inputs['setup']['live_adhoc'] is True
        executions.append(run_id)
        if len(executions) > 1:
            assert sum(event['event'] == 'result' for event in events) == len(executions)-1
        parsed = parser.parse(content)
        repository.tables['experiment_runs'][run_id].update(result=expected, request_file_id=1)
        repository.add('run_attempts', id=run_id, run_id=run_id, attempt=1, result=expected,
                       response_file_id=3, diagnostics_file_id=None, duration_ms=5)
        if parsed.prediction:
            repository.add('predictions', id=run_id, run_id=run_id, attempt_id=run_id, **parsed.prediction)
    monkeypatch.setattr(batch, 'execute_attempt', attempt)
    monkeypatch.setattr(demo, '_measure', lambda *a, **k: pytest.fail('No native render/generation probe'))
    before = deepcopy({table: repository.tables[table] for table in ('datasets', 'dataset_cases', 'reference_results')})
    result = demo.execute(repository, plan, root=tmp_path, spool=tmp_path/'spool',
        runtime_api=api_for(repository), client=object(), notify=events.append,
        live_check=lambda *args: pytest.fail('No global qualification override'))
    assert result['status'] == 'COMPLETED' and result['experiment_id'] != 10003
    assert len(result['results']) == 3
    assert len([event for event in events if event['event'] == 'result']) == 3
    stored = next(value for action, value in repository.writes if action == 'experiment')
    assert stored['name'].startswith('LIVE-ADHOC ') and stored['setup']['format'] == adhoc.FORMAT
    assert stored['setup']['context_policy'].startswith('Conservative byte-budget')
    assert stored['setup']['scientific_evaluation'] is False
    assert {table: repository.tables[table] for table in before} == before


def test_missing_installed_model_blocks_before_database_writes(repository, tmp_path):
    plan = make_plan(repository, tmp_path)
    api = api_for(repository)
    def missing(path, data=None):
        return {'models': []} if path == '/api/tags' else api(path, data)
    with pytest.raises(ValueError, match='not installed'):
        demo.execute(repository, plan, root=tmp_path, spool=tmp_path/'spool', runtime_api=missing)
    assert repository.writes == []


@pytest.mark.parametrize('case_id', [10003])
def test_adhoc_cannot_select_absent_cases(repository, tmp_path, case_id):
    with pytest.raises(ValueError, match='eligible'):
        demo.plan(repository, case_id=case_id, model_ids=[1], repetitions=1, root=tmp_path, adhoc=True)
    assert repository.writes == []


@pytest.mark.parametrize('valid', [True, False])
def test_real_attempt_orchestration_retains_raw_receipt_and_parser_outcome(repository, tmp_path, monkeypatch, valid):
    """Only the in-memory SQL adapter is fake; attempt, spool and parser are real."""
    from contextlib import contextmanager
    from rest_api_checker.experiment.provider import Receipt
    from rest_api_checker.persistence import spool

    plan = make_plan(repository, tmp_path)
    content = encode({c: {'verdict': 'PASS', 'reason': 'FABRICATED'} for c in ('c1', 'c2', 'c3')}).decode() if valid else '```json\n{}\n```'
    raw = encode({'done': True, 'message': {'role': 'assistant', 'content': content},
                  'prompt_eval_count': 20, 'eval_count': 10})
    receipt = Receipt(raw, {'complete': True, 'http_status': 200, 'duration_ms': 7},
                      '2026-10-07T10:00:00+00:00', '2026-10-07T10:00:01+00:00')
    calls, retained = [], []
    def send(req, *, on_start):
        calls.append(req)
        on_start(receipt.started_at)
        return receipt
    def reserve(run_id, request_bytes, *, attempt):
        request_file = repository.archive('fabricated-reservation-request.bin', request_bytes)
        repository.tables['experiment_runs'][run_id]['request_file_id'] = request_file
        repository.add('run_attempts', id=run_id, run_id=run_id, attempt=attempt,
                       result=None, request_file_id=request_file, response_file_id=None,
                       diagnostics_file_id=None, duration_ms=None)
        return run_id
    @contextmanager
    def provider_io(attempt_id):
        yield lambda started: None
    def reconcile(repo, path, *, outcome=None):
        _, value, response = spool.read(path)
        retained.append(response)
        assert response == raw
        attempt = repo.tables['run_attempts'][value['attempt_id']]
        attempt['response_file_id'] = repo.archive('fabricated-raw-response.bin', response)
        if outcome is not None:
            attempt.update(result=outcome['result'], duration_ms=outcome['duration_ms'])
            repo.tables['experiment_runs'][value['run_id']]['result'] = outcome['result']
            if outcome['prediction']:
                repo.add('predictions', id=value['run_id'], run_id=value['run_id'],
                         attempt_id=value['attempt_id'], **outcome['prediction'])
        return True
    monkeypatch.setattr(repository, 'reserve', reserve, raising=False)
    monkeypatch.setattr(repository, 'provider_io', provider_io, raising=False)
    monkeypatch.setattr(repository, 'attempt_state', lambda i: repository._row('run_attempts', i), raising=False)
    monkeypatch.setattr(spool, 'reconcile', reconcile)
    result = demo.execute(repository, plan, root=tmp_path, spool=tmp_path/'spool',
        runtime_api=api_for(repository), client=SimpleNamespace(send=send))
    assert result['status'] == 'COMPLETED' and len(calls) == 1
    assert result['results'][0]['run']['result'] == ('valid' if valid else 'parser_failure')
    assert (result['results'][0]['prediction'] is not None) is valid
    assert retained == [raw, raw]
    archived = list((tmp_path/'spool').glob('*.json'))
    assert len(archived) == 1 and spool.read(archived[0])[2] == raw
