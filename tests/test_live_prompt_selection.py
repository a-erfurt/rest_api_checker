"""Offline prompt selection with approved source bytes and fabricated run storage."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import json
from types import MethodType, SimpleNamespace

import pytest

from rest_api_checker import evaluation_batch_v2, live_adhoc_request as builder
from rest_api_checker import live_adhoc_runtime as runtime, live_demo as demo
from rest_api_checker.experiment import renderer, request_v2
from rest_api_checker.experiment.encoding import digest, encode
from rest_api_checker.experiment.provider import Receipt
from rest_api_checker.persistence import spool
from rest_api_checker.persistence.repository import Repository
from test_live_adhoc_runtime import api_for
from test_live_demo import ROOT, repository, prepared  # noqa: F401

PROMPT_PATHS = {'P1': 'p1_minimal_direct_v1.txt', 'P2': 'p2_structured_checklist_v1.txt',
                'P3': 'p3_explicit_contract_interpretation_v1.txt'}
PROMPTS = {name: (ROOT.parent/'bachelor_rest_api_checker/03_research_design/prompt_candidates_v1'/path).read_bytes()
           for name, path in PROMPT_PATHS.items()}


@pytest.fixture
def prompts(repository, monkeypatch):
    for prompt_id, name in ((10, 'P1'), (11, 'P3')):
        repository.files[prompt_id] = PROMPTS[name]
        repository.add('prompts', id=prompt_id, name=name, file_id=prompt_id)
    # Exercise the actual persisted schedule/closure/prompt lookup adapter.
    monkeypatch.setattr(repository, 'execution_inputs', MethodType(Repository.execution_inputs, repository))
    return repository


def plan(repo, root, prompt_id=None, *, case_id=21, **kwargs):
    return demo.plan(repo, case_id=case_id, model_ids=[1], repetitions=1, root=root,
                     adhoc=True, prompt_id=prompt_id, **kwargs)


def test_catalog_only_returns_real_approved_distinct_candidates(prompts):
    prompts.add('prompts', id=50, name='P1', file_id=10)
    prompts.add('prompts', id=51, name='P3', file_id=3)  # Tampered/unapproved bytes.
    prompts.add('prompts', id=52, name='P4', file_id=10)
    before = deepcopy(prompts.tables), dict(prompts.files)
    assert [(p['id'], p['name']) for p in demo.catalog(prompts, adhoc=True)['prompts']] == [
        (1, 'P2'), (10, 'P1'), (11, 'P3')]
    assert [(p['id'], p['name']) for p in demo.catalog(prompts)['prompts']] == [(1, 'P2')]
    assert (prompts.tables, prompts.files) == before and prompts.writes == []


@pytest.mark.parametrize('name,prompt_id', [('P1', 10), ('P2', 1), ('P3', 11)])
def test_prompt_selection_reaches_summary_schedule_and_actual_request(prompts, tmp_path, name, prompt_id):
    value = plan(prompts, tmp_path, prompt_id)
    assert value.summary['prompt'] == name and value.summary['prompt_id'] == prompt_id
    assert {slot['prompt_id'] for slot in value.schedule} == {prompt_id}
    req = value.requests[1]
    assert json.loads(req.body)['messages'][0]['content'].encode() == PROMPTS[name]
    assert req.metadata['prompt_name'] == name and req.metadata['prompt_sha256'] == digest(PROMPTS[name])
    assert req.metadata['request_version'] == builder.REQUEST_VERSION
    assert req.metadata['request_builder_sha256'] == builder.artifact_hash()
    builder.validate_request_adhoc(req)
    assert prompts.writes == []


def test_omitted_selection_keeps_p2_even_when_its_id_is_larger(prompts, tmp_path):
    prompts.tables['prompts'][20] = {**prompts.tables['prompts'].pop(1), 'id': 20}
    value = plan(prompts, tmp_path)
    assert value.summary['prompt'] == 'P2' and value.summary['prompt_id'] == 20


def test_selection_propagates_to_every_model_and_repetition(prompts, tmp_path):
    value = demo.plan(prompts, case_id=21, model_ids=[1, 2], repetitions=3,
                      root=tmp_path, adhoc=True, prompt_id=11)
    assert len(value.schedule) == len(value.requests) == 6
    assert {slot['prompt_id'] for slot in value.schedule} == {11}
    assert {req.metadata['prompt_name'] for req in value.requests.values()} == {'P3'}
    assert {req.metadata['seed'] for req in value.requests.values()} == {101, 202, 303}


def test_missing_p2_requires_explicit_available_selection(prompts, tmp_path):
    del prompts.tables['prompts'][1]
    with pytest.raises(ValueError, match='P2 is missing'):
        plan(prompts, tmp_path)
    assert plan(prompts, tmp_path, 10).summary['prompt'] == 'P1'


@pytest.mark.parametrize('prompt_id', [2, 999, '10', True])
def test_invalid_selection_is_rejected_before_any_write(prompts, tmp_path, prompt_id):
    with pytest.raises(ValueError, match='approved prompt ID'):
        plan(prompts, tmp_path, prompt_id)
    assert prompts.writes == []


def test_strict_path_remains_p2_only(prompts, prepared):
    repo, root, runtime_path = prepared
    with pytest.raises(ValueError, match='Strict demo requires.*P2'):
        demo.plan(repo, case_id=21, model_ids=[1], repetitions=1, root=root,
                  runtime_path=runtime_path, prompt_id=10)
    default = demo.plan(repo, case_id=21, model_ids=[1], repetitions=1, root=root, runtime_path=runtime_path)
    selected = demo.plan(repo, case_id=21, model_ids=[1], repetitions=1, root=root,
                         runtime_path=runtime_path, prompt_id=1)
    assert selected.requests == default.requests and type(default.requests[1]) is request_v2.RequestV2
    assert default.summary['prompt'] == 'P2'


def test_p2_wire_payload_and_old_adhoc_context_remain_compatible(prompts, prepared):
    repo, root, runtime_path = prepared
    old = demo.plan(repo, case_id=21, model_ids=[1], repetitions=1, root=root, runtime_path=runtime_path).requests[1]
    new = plan(repo, root).requests[1]
    assert old.body == new.body
    binding, sources = runtime.capture([repo._row('models', 1)], api=api_for(repo))
    runtime.context_check(old, binding['models'][0], sources).verify(old)
    runtime.validate_request(old)


@pytest.mark.parametrize('change', ['body_prompt', 'body_option', 'body_format', 'body_role',
    'prompt_name', 'prompt_sha256', 'request_version', 'request_builder_sha256',
    'request_identity_sha256', 'output_interface_version', 'seed', 'contract_identity',
    'rendered_metadata_sha256', 'unknown_field', 'timeout'])
def test_boundary_rejects_payload_or_sidecar_tampering(prompts, tmp_path, change):
    req = plan(prompts, tmp_path, 10).requests[1]
    if change.startswith('body_'):
        payload = json.loads(req.body)
        if change == 'body_prompt': payload['messages'][0]['content'] = PROMPTS['P3'].decode()
        if change == 'body_option': payload['options']['seed'] = 202
        if change == 'body_format': payload['format'] = None
        if change == 'body_role': payload['messages'][0]['role'] = 'user'
        req = replace(req, body=encode(payload))
    elif change == 'timeout':
        req = replace(req, timeout=1)
    else:
        req = replace(req, metadata={**req.metadata, change: 'changed'})
    with pytest.raises(ValueError):
        runtime.validate_request(req)


def install_attempt_storage(repo, monkeypatch):
    """Keep actual batch/orchestration/prepare/parser/spool with in-memory SQL writes."""
    def reserve(run_id, request_bytes, *, attempt):
        request_file = repo.archive('fabricated-request.bin', request_bytes)
        repo.tables['experiment_runs'][run_id]['request_file_id'] = request_file
        repo.add('run_attempts', id=run_id, run_id=run_id, attempt=attempt, result=None,
                 request_file_id=request_file, response_file_id=None, diagnostics_file_id=None, duration_ms=None)
        return run_id
    def dataset(name, version, purpose):
        row_id = max(repo.tables['datasets']) + 1
        repo.add('datasets', id=row_id, name=name, version=version, purpose=purpose)
        return row_id
    def membership(dataset_id, case_id, reference_id, case_code, position):
        row_id = max(repo.tables['dataset_cases']) + 1
        repo.add('dataset_cases', id=row_id, dataset_id=dataset_id, case_id=case_id,
                 reference_id=reference_id, case_code=case_code, position=position)
        return row_id
    @contextmanager
    def provider_io(attempt_id):
        yield lambda started: None
    def reconcile(repository, path, *, outcome=None):
        _, value, response = spool.read(path)
        attempt = repository.tables['run_attempts'][value['attempt_id']]
        attempt['response_file_id'] = repository.archive('fabricated-response.bin', response)
        if outcome is not None:
            attempt.update(result=outcome['result'], duration_ms=outcome['duration_ms'])
            repository.tables['experiment_runs'][value['run_id']]['result'] = outcome['result']
            if outcome['prediction']:
                repository.add('predictions', id=value['run_id'], run_id=value['run_id'],
                    attempt_id=value['attempt_id'], **outcome['prediction'])
        return True
    monkeypatch.setattr(repo, 'reserve', reserve, raising=False)
    monkeypatch.setattr(repo, 'dataset', dataset, raising=False)
    monkeypatch.setattr(repo, 'membership', membership, raising=False)
    monkeypatch.setattr(repo, 'provider_io', provider_io, raising=False)
    monkeypatch.setattr(repo, 'attempt_state', lambda i: repo._row('run_attempts', i), raising=False)
    monkeypatch.setattr(spool, 'reconcile', reconcile)


@pytest.mark.parametrize('name,prompt_id', [('P1', 10), ('P2', 1), ('P3', 11)])
@pytest.mark.parametrize('case_id', [21, 23, 24])
def test_actual_prepare_and_attempt_persist_selected_prompt(prompts, tmp_path, monkeypatch, name, prompt_id, case_id):
    install_attempt_storage(prompts, monkeypatch)
    monkeypatch.setattr(evaluation_batch_v2, 'prepare', lambda *args: pytest.fail('Ad-hoc must not use scientific prepare'))
    prompts.add('experiments', id=10003, dataset_id=3, name='Protected historical experiment')
    prompts.add('experiment_runs', id=10436, experiment_id=10003, dataset_id=3, result='valid')
    before = deepcopy(prompts.tables)
    reqs = []
    content = encode({c: {'verdict': 'PASS', 'reason': 'FABRICATED'} for c in ('c1', 'c2', 'c3')}).decode()
    receipt = Receipt(encode({'done': True, 'message': {'role': 'assistant', 'content': content}}),
        {'complete': True, 'http_status': 200, 'duration_ms': 1},
        '2026-10-23T10:00:00+00:00', '2026-10-23T10:00:01+00:00')
    def send(req, *, on_start):
        reqs.append(req)
        on_start(receipt.started_at)
        return receipt
    result = demo.execute(prompts, plan(prompts, tmp_path, prompt_id, case_id=case_id), root=tmp_path,
        spool=tmp_path/'spool', runtime_api=api_for(prompts), client=SimpleNamespace(send=send))
    assert result['status'] == 'COMPLETED' and len(reqs) == 1
    run = prompts._row('experiment_runs', result['run_ids'][0])
    assert run['prompt_id'] == prompt_id and run['result'] == 'valid'
    assert prompts.file(run['request_file_id']) == reqs[0].body
    _, request_again = builder.prepare(prompts, run['id'])
    assert request_again == reqs[0]
    exp = prompts._row('experiments', result['experiment_id'])
    setup = json.loads(prompts.file(exp['setup_file_id']))
    assert setup['prompt_selection'] == dict(prompt_id=prompt_id, name=name, sha256=digest(PROMPTS[name]))
    assert setup['schedule'][0]['prompt_id'] == prompt_id
    assert setup['request_builder_sha256'] == builder.artifact_hash()
    saved_receipt = spool.read(next((tmp_path/'spool').glob('*.json')))[1]
    sidecar = json.loads(prompts.file(saved_receipt['transport']['request_provenance_file_id']))
    assert sidecar['prompt_name'] == name and sidecar['prompt_sha256'] == digest(PROMPTS[name])
    assert {table: {key: prompts.tables[table][key] for key in records}
            for table, records in before.items()} == before
    if case_id != 21:
        assert run['dataset_id'] != before['dataset_cases'][case_id]['dataset_id']
        assert run['dataset_id'] != 3 and run['dataset_case_id'] != case_id
        assert setup['source_selection']['dataset_case_id'] == case_id


@pytest.mark.parametrize('field,value', [('parser_sha256', 'x'), ('renderer_sha256', 'x'),
    ('request_builder_sha256', 'x'), ('output_interface', {}), ('prompt_selection', {}),
    ('scientific_evaluation', True)])
def test_prepare_rejects_setup_drift(prompts, tmp_path, field, value):
    selection = plan(prompts, tmp_path, 10)
    req = selection.requests[1]
    setup = dict(format=runtime.FORMAT, live_adhoc=True, scientific_evaluation=False,
        gate_b_complete=False, dataset_id=1, fabricated=False, parser_sha256=demo.parser.artifact_hash(),
        renderer_sha256=renderer.artifact_hash(), request_builder_sha256=builder.artifact_hash(),
        output_interface=builder.output_interface(), files=[], schedule=selection.schedule,
        prompt_selection={'prompt_id': 10, 'name': 'P1', 'sha256': req.metadata['prompt_sha256']})
    setup[field] = value
    _, runs = prompts.plan_experiment(name='FABRICATED', dataset_id=1, schedule_seed=101,
        kind='comparison', setup=setup, schedule=selection.schedule)
    with pytest.raises(ValueError):
        builder.prepare(prompts, runs[0])


def test_prompt_changes_after_selection_block_before_runtime(prompts, tmp_path):
    selection = plan(prompts, tmp_path, 10)
    prompts.files[10] = b'changed P1'
    with pytest.raises(ValueError):
        demo.execute(prompts, selection, root=tmp_path, spool=tmp_path/'spool',
                     runtime_api=lambda *a: pytest.fail('Runtime reached after prompt drift'))
    assert prompts.writes == []
