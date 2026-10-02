"""Local/fabricated pilot receipts only; never generate or mutate scientific data."""
from dataclasses import asdict
import json
from pathlib import Path

import pytest

from rest_api_checker import freeze, interface_pilot_v2 as preparer
from rest_api_checker import interface_pilot_v2_live as live, runtime_evidence
from rest_api_checker.experiment import parser, provider, request_v2
from rest_api_checker.experiment.encoding import Blocked, digest, encode, loads
from rest_api_checker.experiment.request import ContextProof, MODELS, OPTIONS

ROOT = Path(__file__).resolve().parents[2]
CASES = ['DEV-03', 'DEV-09']  # Fabricated test selection, never an author decision.
VALID = json.dumps({c: dict(verdict='PASS', reason='Fabricated evidence') for c in ('c1', 'c2', 'c3')})


def receipt(content=VALID, *, reason='stop', status=200, raw=None, complete=True):
    if raw is None:
        raw = json.dumps(dict(model=MODELS[0], done=True, done_reason=reason,
            message=dict(role='assistant', content=content, thinking=' fabricated thinking\n'),
            prompt_eval_count=1000, eval_count=512 if reason == 'length' else 80),
            indent=2).encode('utf-8') + b'\n'
    return provider.Receipt(raw, dict(complete=complete, http_status=status,
        error_kind=None if complete else 'transport', error_message=None if complete else 'fabricated loss',
        headers=[['Content-Type', 'application/json']], duration_ms=2),
        '2026-10-02T12:00:00+00:00', '2026-10-02T12:00:01+00:00')


class FakeClient:
    def __init__(self, response=None):
        self.requests = []
        self.response = response or receipt()

    def send(self, request, *, on_start):
        request_v2.validate_request_v2(request)
        on_start(self.response.started_at)
        self.requests.append(request)
        return self.response


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    from rest_api_checker import oracle
    from rest_api_checker.persistence import database, importer
    def forbidden(*args, **kwargs):
        pytest.fail('Pilot requires no SQL, Oracle, reference or dataset mutation')
    monkeypatch.setattr(database, 'connect', forbidden)
    monkeypatch.setattr(importer, 'import_development', forbidden)
    monkeypatch.setattr(oracle, 'evaluate_response', forbidden)
    identities = json.loads((ROOT/runtime_evidence.DIRECTORY/'identities.json').read_bytes())
    digests = {i['name']: i['digest'] for i in identities}
    directory = tmp_path/'prepared'
    plan = preparer.prepare_pilot(CASES, digests, directory)
    binding_path = tmp_path/'runtime.json'
    binding_path.write_bytes(encode(dict(runtime={'fabricated': True}, models=identities)))
    proofs_path = tmp_path/'proofs.json'
    proofs = {s['request_sha256']: asdict(ContextProof(s['request_sha256'], digests[s['model']],
        next(i['template_sha256'] for i in identities if i['name'] == s['model']), 'a'*64, 1000))
        for s in plan['slots']}
    proofs_path.write_bytes(encode(proofs))
    verified = []
    monkeypatch.setattr(freeze, 'verify_live', lambda b, r: verified.append(b) or True)
    return dict(prepared=directory, cases=CASES, model_digests=digests, runtime_binding=binding_path,
        context_proofs=proofs_path, output=tmp_path/'output', confirm_development_interface_pilot=True), plan, verified


def test_exact_prepared_bytes_three_modes_full_raw_and_unchanged_parser(prepared, monkeypatch):
    args, plan, verified = prepared
    response = receipt(' \n' + VALID + '\t ')
    client = FakeClient(response)
    original_parse, parsed_contents = parser.parse, []
    def parse_exact(content):
        parsed_contents.append(content)
        return original_parse(content)
    monkeypatch.setattr(parser, 'parse', parse_exact)
    # artifact_hash hashes the unchanged file, not the test instrumentation.
    summary = live.run_pilot(**args, client=client)
    assert summary['status'] == 'COMPLETED'
    assert summary['attempted_calls'] == summary['provider_success'] == len(client.requests) == 18
    assert summary['unsettled_calls'] == 0 and len(verified) == 19
    assert len(parsed_contents) == 18 and set(parsed_contents) == {' \n' + VALID + '\t '}
    assert len({(s['case'], s['model'], s['mode']) for s in plan['slots']}) == 18
    assert [r.metadata['output_interface_mode'] for r in client.requests[:3]] == list(request_v2.MODES)
    assert len({digest(r.body) for r in client.requests}) == 18
    assert all(row['attempted_calls'] == row['provider_success'] == row['parser_valid'] == 2
               for row in summary['rows'])
    assert digest((args['output']/'prepared/manifest.json').read_bytes()) == digest(
        (args['prepared']/'manifest.json').read_bytes())
    for slot, request in zip(plan['slots'], client.requests, strict=True):
        directory = args['output']/f"calls/{slot['slot']:02}"
        assert request.body == (args['prepared']/slot['request_path']).read_bytes()
        assert request.metadata == loads((args['prepared']/slot['provenance_path']).read_bytes())
        assert (directory/'response.bin').read_bytes() == response.raw
        assert (directory/'content.txt').read_bytes() == (' \n' + VALID + '\t ').encode()
        assert (directory/'thinking.txt').read_bytes() == b' fabricated thinking\n'
        record = loads((directory/'result.json').read_bytes())
        assert record['raw_response_sha256'] == digest(response.raw)
        assert record['parser'] == asdict(original_parse(parsed_contents[0]))
        assert record['request_sha256'] == digest(request.body) and record['done_reason'] == 'stop'
        assert encode(record['generation_settings']) == encode({**OPTIONS, 'seed': 101})
        assert record['attempt'] == record['repetition'] == 1
        user = loads(loads(request.body)['messages'][1]['content'])
        assert set(user) == {'operation', 'openapi', 'observed_response'}
        assert not any(t in request.body for t in (b'DEV-', b'expected_vector', b'reference_labels', b'fault_id'))


@pytest.mark.parametrize('content,reason', [('```json\n'+VALID+'\n```', 'stop'), (VALID[:-10], 'length')])
def test_parser_failure_is_terminal_per_item_without_retry_or_mode_fallback(prepared, content, reason):
    args, plan, _ = prepared
    client = FakeClient(receipt(content, reason=reason))
    summary = live.run_pilot(**args, client=client)
    assert summary['status'] == 'COMPLETED' and len(client.requests) == 18
    assert [r.metadata['output_interface_mode'] for r in client.requests] == [s['mode'] for s in plan['slots']]
    assert all(r['parser_failure'] == 2 and r['parser_valid'] == 0 for r in summary['rows'])
    assert all(r['length_stops'] == (2 if reason == 'length' else 0) for r in summary['rows'])
    assert loads((args['output']/'calls/01/result.json').read_bytes())['parser'] == asdict(parser.parse(content))


@pytest.mark.parametrize('response', [receipt(status=500), receipt(status=400),
    receipt(raw=b'partial raw bytes', complete=False), receipt(raw=b'invalid envelope'),
    receipt(raw=b'[1, 2]', status=500), receipt(raw=b'', complete=False)])
def test_provider_failure_preserved_and_stops_without_redispatch(prepared, response):
    args, _, _ = prepared
    client = FakeClient(response)
    summary = live.run_pilot(**args, client=client)
    assert summary['status'] == 'STOPPED_PROVIDER_FAILURE'
    assert summary['attempted_calls'] == len(client.requests) == 1
    assert (args['output']/'calls/01/response.bin').read_bytes() == response.raw
    assert summary['rows'][0]['provider_failure'] == 1 and summary['rows'][0]['parser_failure'] == 0


def test_absent_response_is_distinct_from_empty(prepared):
    args, _, _ = prepared
    response = provider.Receipt(None, dict(complete=False, error_kind='transport', http_status=None), 'a', 'b')
    live.run_pilot(**args, client=FakeClient(response))
    assert not (args['output']/'calls/01/response.bin').exists()
    assert loads((args['output']/'calls/01/result.json').read_bytes())['raw_response_sha256'] is None


@pytest.mark.parametrize('cases', [['DEV-03', 'DEV-03'], ['DEV-03', 'FC-EDX-001'],
    ['DEV-03', 'FINAL-01'], ['DEV-03', 'MAIN-01'], ['DEV-03', 'DEV-13'], ['DEV-01', 'DEV-02']])
def test_only_explicit_released_selected_dev_cases_before_runtime_or_provider(prepared, cases):
    args, _, verified = prepared
    client = FakeClient()
    with pytest.raises((Blocked, FileNotFoundError)):
        live.run_pilot(**{**args, 'cases': cases}, client=client)
    assert not client.requests and not verified and not args['output'].exists()


@pytest.mark.parametrize('name', ['requests/01.json', 'provenance/01.json', 'manifest.json', 'manifest.sha256'])
def test_changed_prepared_bytes_cannot_reach_provider(prepared, name):
    args, _, verified = prepared
    path = args['prepared']/name
    path.write_bytes(path.read_bytes()+b' ')
    client = FakeClient()
    with pytest.raises(Blocked, match='PREPARED_PILOT_BYTES_CHANGED'):
        live.run_pilot(**args, client=client)
    assert client.requests == verified == []


@pytest.mark.parametrize('mutation', ['missing_proof', 'old_request', 'wrong_digest', 'wrong_template',
    'context_overflow', 'missing_model', 'lm_studio', 'changed_model_digest'])
def test_missing_or_wrong_runtime_context_bindings_stop_before_dispatch(prepared, mutation):
    args, plan, verified = prepared
    path = args['runtime_binding'] if mutation in ('missing_model', 'lm_studio', 'changed_model_digest') else args['context_proofs']
    value = loads(path.read_bytes())
    key = plan['slots'][0]['request_sha256']
    if mutation == 'missing_proof': del value[key]
    if mutation == 'old_request': value[key]['request_sha256'] = '0'*64
    if mutation == 'wrong_digest': value[key]['model_digest'] = '0'*64
    if mutation == 'wrong_template': value[key]['template_sha256'] = '0'*64
    if mutation == 'context_overflow': value[key]['input_tokens'] = 32768
    if mutation == 'missing_model': value['models'].pop()
    if mutation == 'lm_studio': value['models'][0]['name'] = 'lm-studio/qwen'
    if mutation == 'changed_model_digest': value['models'][0]['digest'] = '0'*64
    path.write_bytes(encode(value))
    client = FakeClient()
    with pytest.raises(Blocked): live.run_pilot(**args, client=client)
    assert not client.requests and not verified


def test_live_drift_stops_before_next_attempt(prepared, monkeypatch):
    args, _, _ = prepared
    count = 0
    def verify(*unused):
        nonlocal count
        count += 1
        if count == 3: raise ValueError('Live model digest drift')
        return True
    monkeypatch.setattr(freeze, 'verify_live', verify)
    client = FakeClient()
    summary = live.run_pilot(**args, client=client)
    assert summary['status'] == 'STOPPED_REQUIRES_MANUAL_REVIEW' and len(client.requests) == 1
    assert summary['attempted_calls'] == 1 and 'digest drift' in summary['error']


def test_initial_runtime_unverified_has_zero_calls_and_no_claim(prepared, monkeypatch):
    args, _, _ = prepared
    monkeypatch.setattr(freeze, 'verify_live', lambda *unused: False)
    client = FakeClient()
    with pytest.raises(Blocked, match='RUNTIME_IDENTITY_UNVERIFIED'):
        live.run_pilot(**args, client=client)
    assert not client.requests and not (args['prepared']/'live-dispatch.json').exists()


def test_one_execution_even_with_different_output_after_failure(prepared):
    args, _, _ = prepared
    client = FakeClient(receipt(status=500))
    live.run_pilot(**args, client=client)
    with pytest.raises(Blocked, match='PILOT_ALREADY_CLAIMED'):
        live.run_pilot(**{**args, 'output': args['output'].with_name('second-output')}, client=client)
    assert len(client.requests) == 1


def test_ambiguous_interruption_is_retained_and_never_retried(prepared):
    args, _, _ = prepared
    class Interrupted(FakeClient):
        def send(self, request, *, on_start):
            on_start('fabricated start')
            self.requests.append(request)
            raise KeyboardInterrupt()
    client = Interrupted()
    summary = live.run_pilot(**args, client=client)
    assert len(client.requests) == summary['attempted_calls'] == summary['unsettled_calls'] == 1
    assert summary['rows'][0]['attempted_calls'] == summary['rows'][0]['unsettled_calls'] == 1
    assert summary['rows'][0]['provider_failure'] == 0
    assert (args['output']/'calls/01/started.json').exists() and (args['output']/'stop.json').exists()


def test_raw_receipt_survives_later_persistence_failure_without_retry(prepared, monkeypatch):
    args, _, _ = prepared
    original = live.publish
    def fail_result(path, raw):
        if Path(path).name == 'result.json': raise OSError('fabricated result persistence failure')
        return original(path, raw)
    monkeypatch.setattr(live, 'publish', fail_result)
    client = FakeClient()
    summary = live.run_pilot(**args, client=client)
    assert summary['status'] == 'STOPPED_REQUIRES_MANUAL_REVIEW' and len(client.requests) == 1
    assert summary['unsettled_calls'] == 1
    assert (args['output']/'calls/01/response.bin').read_bytes() == client.response.raw
    assert (args['output']/'calls/01/receipt.json').exists()


def test_native_metadata_template_hash_cannot_be_fabricated(prepared):
    args, _, verified = prepared
    value = loads(args['runtime_binding'].read_bytes())
    value['models'][0]['template_sha256'] = '0'*64
    args['runtime_binding'].write_bytes(encode(value))
    client = FakeClient()
    with pytest.raises(Blocked, match='NATIVE_TEMPLATE_BINDING_CHANGED'):
        live.run_pilot(**args, client=client)
    assert client.requests == verified == []


def test_native_metadata_is_hash_bound_and_source_drift_stops(prepared, tmp_path, monkeypatch):
    args, _, _ = prepared
    copied_root = tmp_path/'technical'
    native = copied_root/runtime_evidence.DIRECTORY
    native.mkdir(parents=True)
    binding = loads(args['runtime_binding'].read_bytes())
    for identity in binding['models']:
        (native/identity['show']).write_bytes((ROOT/runtime_evidence.DIRECTORY/identity['show']).read_bytes())
    client = FakeClient()
    send = client.send
    def send_and_change(request, *, on_start):
        response = send(request, on_start=on_start)
        path = native/binding['models'][0]['show']
        path.write_bytes(path.read_bytes()+b' ')
        return response
    monkeypatch.setattr(client, 'send', send_and_change)
    # Use real released inputs with copied runtime metadata only.
    original_files = preparer.pilot_files
    monkeypatch.setattr(preparer, 'pilot_files', lambda *a, **k: original_files(*a, **{**k, 'root': ROOT}))
    summary = live.run_pilot(**args, root=copied_root, client=client)
    assert len(client.requests) == 1 and summary['error'].endswith('NATIVE_METADATA_SNAPSHOT_CHANGED')
    execution = loads((args['output']/'execution.json').read_bytes())
    for name, sha in execution['native_metadata_sha256'].items():
        assert digest((args['output']/'native-metadata'/name).read_bytes()) == sha


def test_content_with_unpaired_json_surrogate_preserved_and_parsed_unchanged(prepared):
    args, _, _ = prepared
    content = VALID.replace('Fabricated evidence', '\ud800')
    summary = live.run_pilot(**args, client=FakeClient(receipt(content)))
    assert summary['status'] == 'COMPLETED'
    directory = args['output']/'calls/01'
    assert (directory/'content.txt').read_bytes().decode('utf-8', errors='surrogatepass') == content
    assert loads((directory/'result.json').read_bytes())['parser'] == asdict(parser.parse(content))


def test_explicit_confirmation_new_output_and_research_read_only(prepared):
    args, _, _ = prepared
    for changes in (dict(confirm_development_interface_pilot=False), dict(output=args['prepared']),
        dict(output=preparer.RESEARCH/'forbidden-pilot'), dict(prepared=preparer.RESEARCH/'forbidden-pilot')):
        with pytest.raises(Blocked): live.run_pilot(**{**args, **changes}, client=FakeClient())
    args['output'].mkdir()
    with pytest.raises(Blocked, match='NEW_EXECUTION_DIRECTORY_REQUIRED'):
        live.run_pilot(**args, client=FakeClient())


def test_existing_transport_sends_exact_prepared_bytes_once_per_slot(prepared):
    args, plan, _ = prepared
    raw = receipt().raw
    sent = []
    class Response:
        status = 200
        length = len(raw)
        def getheaders(self): return [('Content-Type', 'application/json')]
        def read1(self, size):
            self.length = 0
            return raw
    class Connection:
        sock = None
        def __init__(self, host, port, timeout):
            assert (host, port, timeout) == ('127.0.0.1', 11434, 300)
        def connect(self): pass
        def request(self, method, path, *, body, headers):
            assert (method, path) == ('POST', '/api/chat')
            sent.append(body)
        def getresponse(self): return Response()
        def close(self): pass
    client = provider.OllamaClient(connection_factory=Connection, request_validator=request_v2.validate_request_v2)
    assert live.run_pilot(**args, client=client)['status'] == 'COMPLETED'
    assert sent == [(args['prepared']/s['request_path']).read_bytes() for s in plan['slots']]
    assert len(sent) == 18


def test_v1_client_or_nonlocal_endpoint_cannot_dispatch(prepared):
    args, _, _ = prepared
    for client in (provider.OllamaClient(), provider.OllamaClient('http://localhost:9999/api/chat',
        request_validator=request_v2.validate_request_v2)):
        with pytest.raises(Blocked, match='EXACT_LOCAL_OLLAMA_V2_BOUNDARY_REQUIRED'):
            live.run_pilot(**args, client=client)


def test_cli_requires_all_explicit_inputs_and_dev_confirmation(prepared, monkeypatch):
    args, _, _ = prepared
    digests = args['prepared'].parent/'digests.json'
    digests.write_bytes(encode(args['model_digests']))
    argv = ['run', '--prepared', str(args['prepared']), '--cases', *CASES,
        '--model-digests', str(digests), '--runtime-binding', str(args['runtime_binding']),
        '--context-proofs', str(args['context_proofs']), '--output', str(args['output'])]
    with pytest.raises(SystemExit) as missing: live.main(argv)
    assert missing.value.code == 2
    client = FakeClient()
    run = live.run_pilot
    monkeypatch.setattr(live, 'run_pilot', lambda *a, **k: run(*a, **k, client=client))
    assert live.main(argv + ['--confirm-development-interface-pilot']) == 0
    assert len(client.requests) == 18


def test_cli_late_persistence_error_does_not_claim_zero_dispatch(prepared, monkeypatch, capsys):
    args, _, _ = prepared
    digests = args['prepared'].parent/'digests.json'
    digests.write_bytes(encode(args['model_digests']))
    client, run, publish = FakeClient(), live.run_pilot, live.publish
    monkeypatch.setattr(live, 'run_pilot', lambda *a, **k: run(*a, **k, client=client))
    def fail_summary(path, raw):
        if Path(path).name == 'summary.json': raise OSError('fabricated summary write failure')
        return publish(path, raw)
    monkeypatch.setattr(live, 'publish', fail_summary)
    with pytest.raises(SystemExit) as stopped:
        live.main(['run', '--prepared', str(args['prepared']), '--cases', *CASES,
            '--model-digests', str(digests), '--runtime-binding', str(args['runtime_binding']),
            '--context-proofs', str(args['context_proofs']), '--output', str(args['output']),
            '--confirm-development-interface-pilot'])
    assert stopped.value.code == 1 and len(client.requests) == 18
    assert 'before dispatch' not in capsys.readouterr().err
    assert (args['output']/'calls/18/result.json').exists()
