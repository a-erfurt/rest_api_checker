"""Current interactive model identities; all provider/SQL evidence is fabricated."""
from contextlib import contextmanager
from copy import deepcopy
import io
import json
from types import SimpleNamespace

import pytest

from rest_api_checker import freeze, interactive_app, live_adhoc_runtime as adhoc, live_demo as demo, terminal
from rest_api_checker.experiment.encoding import digest, encode
from rest_api_checker.experiment.provider import Receipt
from rest_api_checker.persistence import inspection, spool
from test_live_demo import prepared, repository  # noqa: F401

CURRENT_DIGEST = 'd' * 64
SHOW = dict(template='FABRICATED current template', parameters='FABRICATED', system='',
    details=dict(family='gemma3', families=['gemma3'], parameter_size='27B', quantization_level='Q4_K_M'),
    model_info={'general.architecture': 'gemma3', 'general.parameter_count': 27000000000,
                'gemma3.context_length': 32768})


def installed_api(repo, *, installed=True, digest_prefix=False):
    """Installed tags are independent from immutable historical SQL model rows."""
    tags = [dict(name=row['name'], digest=row['digest']) for row in repo.tables['models'].values()]
    gemma = next(row for row in tags if row['name'] == 'gemma3:27b')
    gemma['digest'] = ('sha256:' if digest_prefix else '') + CURRENT_DIGEST
    if not installed:
        tags.remove(gemma)
    def api(path, data=None):
        if path == '/api/version':
            return {'version': '0.40.0'}
        if path == '/api/tags':
            return {'models': deepcopy(tags)}
        if path == '/api/ps':
            return {'models': []}
        assert path == '/api/show' and data == {'model': 'gemma3:27b'}
        return deepcopy(SHOW)
    return api


@pytest.fixture
def append_model(repository, monkeypatch):
    calls = []
    def model(**values):
        calls.append(deepcopy(values))
        row_id = max(repository.tables['models']) + 1
        repository.add('models', id=row_id, **values)
        repository.writes.append(('model', row_id))
        return row_id
    monkeypatch.setattr(repository, 'model', model, raising=False)
    return calls


@pytest.fixture
def attempt_storage(repository, monkeypatch):
    """Keep canonical attempt/spool/parser code, replacing only database writes."""
    content = encode({category: {'verdict': 'PASS', 'reason': 'FABRICATED conforming response'}
                      for category in ('c1', 'c2', 'c3')}).decode()
    raw = encode(dict(done=True, message=dict(role='assistant', content=content),
                      prompt_eval_count=20, eval_count=10))
    receipt = Receipt(raw, dict(complete=True, http_status=200, duration_ms=7),
                      '2026-10-07T10:00:00+00:00', '2026-10-07T10:00:01+00:00')
    calls = []
    def send(req, *, on_start):
        calls.append(req)
        on_start(receipt.started_at)
        return receipt
    def reserve(run_id, request_bytes, *, attempt):
        request_file = repository.archive('FABRICATED-request.bin', request_bytes)
        repository.tables['experiment_runs'][run_id]['request_file_id'] = request_file
        repository.add('run_attempts', id=run_id, run_id=run_id, attempt=attempt, result=None,
                       request_file_id=request_file, response_file_id=None,
                       diagnostics_file_id=None, duration_ms=None)
        return run_id
    @contextmanager
    def provider_io(attempt_id):
        yield lambda started: None
    def reconcile(repo, path, *, outcome=None):
        _, value, response = spool.read(path)
        assert response == raw
        attempt = repo.tables['run_attempts'][value['attempt_id']]
        attempt['response_file_id'] = repo.archive('FABRICATED-response.bin', response)
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
    return SimpleNamespace(send=send), calls


@pytest.mark.parametrize('digest_prefix', [False, True])
def test_interactive_capture_binds_current_tag_despite_historical_digest(repository, digest_prefix):
    historical = repository._row('models', 2)
    api = installed_api(repository, digest_prefix=digest_prefix)
    binding, sources = adhoc.capture([historical], api=api)
    identity = binding['models'][0]
    assert identity['name'] == historical['name'] and identity['digest'] == CURRENT_DIGEST
    assert identity['metadata_sha256'] == digest(encode(SHOW))
    assert sources[identity['show']] == encode(SHOW)
    assert binding['runtime']['ollama']['version'] == '0.40.0'
    assert binding['runtime']['scientifically_qualified'] is False
    assert adhoc.verify_live(binding, sources, api=api) is True
    assert repository._row('models', 2) == historical and repository.writes == []


def test_interactive_new_model_is_append_only_and_bound_to_persisted_result(
        repository, tmp_path, append_model, attempt_storage):
    historical = deepcopy(repository.tables['models'])
    plan = demo.plan(repository, case_id=21, model_ids=[2], repetitions=1, root=tmp_path, adhoc=True)
    original_requests, original_snapshot = deepcopy(plan.requests), deepcopy(plan.snapshot)
    client, calls = attempt_storage
    result = demo.execute(repository, plan, root=tmp_path, spool=tmp_path/'spool',
                          runtime_api=installed_api(repository), client=client)
    assert result['status'] == 'COMPLETED', result
    assert len(calls) == len(append_model) == 1
    current = repository._row('models', result['results'][0]['run']['model_id'])
    assert current['id'] not in historical and current['digest'] == CURRENT_DIGEST
    assert current['name'] == 'gemma3:27b'
    assert current['family'] == current['architecture'] == 'gemma3'
    assert float(current['parameters_b']) == 27
    assert current['quantization'] == 'Q4_K_M' and current['context_length'] == 32768
    assert json.loads(repository.file(current['metadata_file_id'])) == SHOW
    assert {key: repository.tables['models'][key] for key in historical} == historical
    assert plan.requests == original_requests and plan.snapshot == original_snapshot
    assert calls[0].metadata['model_digest'].removeprefix('sha256:') == CURRENT_DIGEST
    experiment = repository._row('experiments', result['experiment_id'])
    setup = json.loads(repository.file(experiment['setup_file_id']))
    assert experiment['name'].startswith('LIVE-ADHOC ') and experiment['id'] != 10003
    assert setup['models'][0]['digest'] == CURRENT_DIGEST
    assert setup['runtime']['ollama']['version'] == '0.40.0'
    assert setup['bindings']['models'] == [inspection.portable(current)]
    assert dict(file_id=current['metadata_file_id'], sha256=digest(encode(SHOW))) in setup['files']
    assert setup['model_selection'] == [dict(configured_model_id=2,
        configured_digest=historical[2]['digest'], model_id=current['id'], installed_digest=CURRENT_DIGEST)]
    assert setup['context_proofs']['1']['model_digest'].removeprefix('sha256:') == CURRENT_DIGEST
    assert setup['request_inventory'][0]['request_identity_sha256'] == calls[0].metadata['request_identity_sha256']
    assert setup['scientific_evaluation'] is False and setup['gate_b_complete'] is False
    detail = inspection.run_detail(repository, result['run_ids'][0])
    assert detail['run']['result'] == 'valid' and detail['prediction']['c1'] == 'PASS'
    assert all(detail['correctness'].values())
    assert detail['attempts'][0]['response_file_id'] is not None


@pytest.mark.parametrize('digest_prefix', [False, True])
def test_existing_current_identity_is_reused_without_mutating_any_model(
        repository, tmp_path, append_model, attempt_storage, digest_prefix):
    repository.add('models', id=101, name='gemma3:27b',
                   digest=('sha256:' if digest_prefix else '')+CURRENT_DIGEST, context_length=32768)
    before = deepcopy(repository.tables['models'])
    plan = demo.plan(repository, case_id=21, model_ids=[2], repetitions=1, root=tmp_path, adhoc=True)
    client, calls = attempt_storage
    result = demo.execute(repository, plan, root=tmp_path, spool=tmp_path/'spool',
                          runtime_api=installed_api(repository), client=client)
    assert result['status'] == 'COMPLETED', result
    assert result['results'][0]['run']['model_id'] == 101
    assert len(calls) == 1 and append_model == []
    assert repository.tables['models'] == before


def test_interactive_catalog_shows_one_entry_per_tag_with_historical_selection(repository):
    repository.add('models', id=101, name='gemma3:27b', digest=CURRENT_DIGEST, context_length=32768)
    models = demo.catalog(repository, adhoc=True)['models']
    assert [row['id'] for row in models if row['name'] == 'gemma3:27b'] == [2]
    assert len({row['name'] for row in models}) == len(models) == 3
    assert repository.writes == []


def test_missing_model_is_truthful_and_blocks_before_writes(repository, tmp_path):
    plan = demo.plan(repository, case_id=21, model_ids=[2], repetitions=1, root=tmp_path, adhoc=True)
    with pytest.raises(ValueError, match='^✗ Gemma 3 27B is not installed in Ollama\\.$'):
        demo.execute(repository, plan, root=tmp_path, spool=tmp_path/'spool',
                     runtime_api=installed_api(repository, installed=False))
    assert repository.writes == []


def test_missing_model_returns_to_main_menu_without_cli_crash(monkeypatch):
    console = terminal.console(plain=True, file=io.StringIO())
    def missing(*args):
        raise ValueError('✗ Gemma 3 27B is not installed in Ollama.')
    monkeypatch.setattr(interactive_app, 'run_check', missing)
    answers = iter(['1', '4'])
    assert interactive_app.launch(SimpleNamespace(), console, input_fn=lambda prompt: next(answers)) == 0
    assert '✗ Gemma 3 27B is not installed in Ollama.' in console.file.getvalue()
    assert console.file.getvalue().count('Choose an action:') == 2


def test_qualified_plan_still_rejects_configured_digest_mismatch(prepared):
    repo, root, runtime = prepared
    repo.tables['models'][2]['digest'] = CURRENT_DIGEST
    with pytest.raises(ValueError, match='does not match the explicit runtime binding'):
        demo.plan(repo, case_id=21, model_ids=[2], repetitions=1, runtime_path=runtime, root=root)
    assert repo.writes == []


def test_qualified_live_runtime_guard_still_rejects_installed_digest_mismatch(repository, tmp_path, monkeypatch):
    monkeypatch.setattr(freeze.platform, 'machine', lambda: 'FABRICATED architecture')
    monkeypatch.setattr(freeze.platform, 'python_version', lambda: 'FABRICATED python')
    monkeypatch.setattr(freeze.subprocess, 'check_output', lambda *args, **kwargs: 'FABRICATED host')
    candidate = dict(runtime=dict(ollama={'version': '0.40.0'}, architecture='FABRICATED architecture',
        python='FABRICATED python', os='FABRICATED host', cpu='FABRICATED host',
        ram_bytes='FABRICATED host', hardware='FABRICATED host', binaries={}),
        models=[repository._row('models', 2)])
    with pytest.raises(ValueError, match='Live model digest drift'):
        freeze.verify_live(candidate, tmp_path, api=installed_api(repository))
    assert repository.writes == []


def test_ollama_runner_variants_bind_the_selected_manifest_not_first_same_tag(repository):
    api = installed_api(repository)
    historical = repository._row('models', 2)
    selected_show = deepcopy(SHOW)
    selected_show['details']['runner'] = 'llamacpp'
    selected_show['manifests'] = [
        dict(digest='sha256:'+historical['digest'], runner='ggml', format='gguf'),
        dict(digest='sha256:'+CURRENT_DIGEST, runner='llamacpp', format='gguf', selected=True)]
    def variants(path, data=None):
        if path == '/api/tags':
            return {'models': [dict(name=historical['name'], digest=historical['digest']),
                               dict(name=historical['name'], digest=CURRENT_DIGEST)]}
        if path == '/api/show':
            return deepcopy(selected_show)
        return api(path, data)
    binding, sources = adhoc.capture([historical], api=variants)
    assert binding['models'][0]['digest'] == CURRENT_DIGEST
    assert json.loads(sources[binding['models'][0]['show']]) == selected_show
    assert adhoc.verify_live(binding, sources, api=variants) is True
    assert repository.writes == []


def test_ambiguous_same_tag_variants_do_not_claim_model_is_missing(repository):
    api = installed_api(repository)
    historical = repository._row('models', 2)
    def variants(path, data=None):
        if path == '/api/tags':
            return {'models': [dict(name=historical['name'], digest=historical['digest']),
                               dict(name=historical['name'], digest=CURRENT_DIGEST)]}
        return api(path, data)
    with pytest.raises(ValueError, match='(?i)ambiguous') as caught:
        adhoc.capture([historical], api=variants)
    assert 'not installed' not in str(caught.value)
    assert repository.writes == []
