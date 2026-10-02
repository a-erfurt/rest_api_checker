"""Offline v2 interface tests; historical request baselines recorded before edits."""
from dataclasses import replace
from itertools import product
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from rest_api_checker.experiment import parser, provider, renderer, request, request_v2
from rest_api_checker.experiment.encoding import Blocked, digest, encode, loads
from rest_api_checker import interface_pilot_v2 as pilot

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT.parent/'bachelor_rest_api_checker'
PROMPTS = dict(P1='p1_minimal_direct_v1.txt', P2='p2_structured_checklist_v1.txt',
               P3='p3_explicit_contract_interpretation_v1.txt')
MODELS = ('qwen3.6:27b', 'gemma3:27b', 'mistral-small3.2:24b')
SETTINGS = dict(temperature=0.2, top_p=0.9, top_k=40, min_p=0.0, repeat_penalty=1.0,
                repeat_last_n=64, draft_num_predict=0, num_ctx=32768, num_predict=512)
# Order: P1/P2/P3, then Qwen/Gemma/Mistral, then repetitions 1/2/3.
V1_HASHES = (
    '37f74422978d985815ec8a7b54d9507e4f5aa83586937b5de7bd8b9a78f2b9d9',
    '060c78f4e89e1af32d18cdeeb3e702def9a49be2052751550c2a3427e4ce8c1d',
    '746101958c674c9fd2dd2112763595d80f84faacb5bcf8e94b62990badf0f602',
    '61e95094dd8435c758f4d661cb0654165bc0319709bf6cc871568c35731bb44d',
    '224643174bad573875e48c01090082940565a6396a1db5f0d7e54ef6ae500f27',
    '2e60148f91e192c8db3d4546306f01601e735e43d543d4e8591d9b1aa6fce1c2',
    'a7328beb8a24e90acdef389a6188b22fb77e1f80116739e90049982fe02db3dd',
    '6337d212851e9c0a94a004c0030f11afa75ad03b0b67e0635663ec0d59a2380a',
    'd12afceb8cc2f185c18801dc454bb46e5ba9fc8f153a7fa8b0c46f9ff9d8f971',
    '4d47e58a89880cca08060f8c5a889d312c82caf4706cda4da603e20788265cca',
    '54f24861901513072dc459b26ab67ae1569aa2faab32380cabfd3a402399e397',
    '6cbadff6741a0982b1c53562f12f7232155f73ce3708e1619ebad5a7ec8bbc92',
    'aca412cda0c681f9ea2b231c22c17f00115c2c202aff12a75af613a168026284',
    '0b1c163c21f361b0fccb56ce90b09249d8ae51bca9bed3c5508ddec6c0fc8b81',
    '32bb6a6912288146c0b82f2f36c5ade50bb12879abc6975a598df3bbcb16cab0',
    '9c2b30f9e640deeb2e6a4c3bbedc35d6133d7fcf20f137f71c1e2af3a84455d0',
    'be8bd6d8b48c9803fb50bc5115f7683f5471de2ba8dc9ee0dfcf98c4d12cc0f6',
    '79bd4c9aea5cf64e6713ecf04b0a7f3442596f89d4daba385779b7510d8a69d9',
    '03fb63a6ec261dc843778df66fc1b881218cb43f0db85abf08c764f2fc299b32',
    '63f7efcc211d0f864e120f2e159ea8a3d75a9f1076b29a6b7cf8a721c4bce93b',
    '49b51739eb325c7add18550c37d440115b16677c595e494857692fd64f71d3dc',
    '47a168fa0e3702a20ed3873e62aad8a8587e986ddcab9639d145d2b992c32a9d',
    'ba29fce784490febe4f24d23d865e3ee01e36078bf148c2666324c4a25ca05a7',
    'fd5ae4e7142fe5ef1f25f0e3e43afb7f41f7895ec8a13f46fd713ef1cf17b6d1',
    'd09808fd1eea30421739f2482c9281e4147a44b47f6a71370016aa211b4096a1',
    '0244f1b9b8656d44930d4abf310a65a3d981888a8540fc0f3a32da35f6c8dccf',
    'f92ccc71ff0374725841932bbcf9ad4c96953843ed812571c3990d8c572b37db',
)


def prompt(name='P2'):
    return (RESEARCH/'03_research_design/prompt_candidates_v1'/PROMPTS[name]).read_bytes()


def sample():
    content = encode({'operation': {'method': 'post', 'path': '/x'}, 'openapi': {},
        'observed_response': {'status': 200, 'content_type': 'application/json', 'body': '{}'}})
    return renderer.Rendered(content, dict(rendered_evidence_sha256=digest(content),
        reference_labels='SECRET_REFERENCE', fault_id='SECRET_FAULT', expected_answer='SECRET_EXPECTED',
        provenance='SECRET_PROVENANCE', case_id='SECRET_CASE'))


def built(mode='prompt_only', model=MODELS[0], repetition=1):
    return request_v2.build_request_v2(sample(), interface=request_v2.OutputInterfaceV2(mode),
        prompt=prompt(), model=model, model_digest='a'*64, repetition=repetition)


@pytest.mark.parametrize('name,model,repetition,expected', [(*slot, sha) for slot, sha in
    zip(product(PROMPTS, MODELS, (1, 2, 3)), V1_HASHES, strict=True)])
def test_historical_v1_exact_byte_baselines(name, model, repetition, expected):
    old = request.build_request(sample(), prompt_name=name, prompt=prompt(name),
                                model=model, model_digest='a'*64, repetition=repetition)
    assert digest(old.body) == expected
    assert 'format' not in loads(old.body)
    request.validate_request(old)
    altered = replace(old, body=encode({**loads(old.body), 'format': 'json'}))
    with pytest.raises(Blocked):
        request.validate_request(altered)


@pytest.mark.parametrize('mode', request_v2.MODES)
@pytest.mark.parametrize('model', MODELS)
@pytest.mark.parametrize('repetition,seed', [(1, 101), (2, 202), (3, 303)])
def test_three_modes_exact_conditions_and_no_metadata_leak(mode, model, repetition, seed):
    result = built(mode, model, repetition)
    payload = loads(result.body)
    expected_fields = {'model', 'messages', 'stream', 'options'}
    if model == MODELS[0]:
        expected_fields.add('think')
        assert payload['think'] is False
    if mode != 'prompt_only':
        expected_fields.add('format')
        assert payload['format'] == ('json' if mode == 'format_json' else request_v2.transport_schema())
    assert set(payload) == expected_fields
    assert encode(payload['options']) == encode({**SETTINGS, 'seed': seed})
    assert payload['messages'] == [{'role': 'system', 'content': prompt().decode()},
                                   {'role': 'user', 'content': sample().content.decode()}]
    assert b'SECRET' not in result.body
    assert result.metadata['reference_labels'] == 'SECRET_REFERENCE'  # Sidecar only.
    assert result.timeout == 300 and payload['stream'] is False
    assert result.metadata['output_interface_version'] == 'output-interface-v2'
    assert result.metadata['output_interface_mode'] == mode
    assert result.metadata['request_version'] == 'ollama-chat-request-v2'
    assert result == built(mode, model, repetition)
    request_v2.validate_request_v2(result)


def test_modes_change_only_format_and_have_distinct_identity():
    results = [built(mode) for mode in request_v2.MODES]
    assert len({r.metadata['request_identity_sha256'] for r in results}) == 3
    for result in results:
        payload = loads(result.body)
        payload.pop('format', None)
        assert encode(payload) == results[0].body
    old = request.build_request(sample(), prompt_name='P2', prompt=prompt(), model=MODELS[0],
                                model_digest='a'*64, repetition=1)
    assert old.body == results[0].body
    assert old.metadata['request_version'] != results[0].metadata['request_version']
    assert results[0].metadata['request_identity_sha256'] != digest(old.body)
    assert results[0].metadata['transport_schema_sha256'] is None
    assert results[1].metadata['transport_schema_sha256'] is None
    assert results[2].metadata['transport_schema_sha256'] == digest(request_v2.SCHEMA_PATH.read_bytes())


def test_transport_schema_has_only_independent_structural_constraints():
    schema = request_v2.transport_schema()
    Draft202012Validator.check_schema(schema)
    assert set(schema) == {'type', 'required', 'additionalProperties', 'properties'}
    assert schema['type'] == 'object' and schema['additionalProperties'] is False
    assert schema['required'] == ['c1', 'c2', 'c3']
    assert set(schema['properties']) == {'c1', 'c2', 'c3'}
    for category in schema['properties'].values():
        assert category == dict(type='object', required=['verdict', 'reason'], additionalProperties=False,
            properties=dict(verdict=dict(type='string', enum=['PASS', 'FAIL', 'NOT_APPLICABLE']),
                            reason=dict(type='string')))


@pytest.mark.parametrize('vector', tuple(product(('PASS', 'FAIL', 'NOT_APPLICABLE'), repeat=3)))
def test_transport_and_unchanged_parser_permit_all_27_vectors(vector):
    value = {c: dict(verdict=v, reason='Evidence') for c, v in zip(('c1', 'c2', 'c3'), vector)}
    Draft202012Validator(request_v2.transport_schema()).validate(value)
    assert parser.parse(json.dumps(value)).status == 'VALID_OUTPUT'


@pytest.mark.parametrize('mutation', ['missing_category', 'extra_category', 'category_array',
    'missing_verdict', 'missing_reason', 'extra_member', 'bad_verdict', 'nonstring_reason', 'scalar'])
def test_transport_rejects_malformed_structure(mutation):
    value = {c: dict(verdict='PASS', reason='Evidence') for c in ('c1', 'c2', 'c3')}
    if mutation == 'missing_category': del value['c3']
    if mutation == 'extra_category': value['c4'] = value['c1']
    if mutation == 'category_array': value['c1'] = []
    if mutation == 'missing_verdict': del value['c1']['verdict']
    if mutation == 'missing_reason': del value['c1']['reason']
    if mutation == 'extra_member': value['c1']['truth'] = 'CONSISTENT'
    if mutation == 'bad_verdict': value['c1']['verdict'] = 'UNKNOWN'
    if mutation == 'nonstring_reason': value['c1']['reason'] = 1
    if mutation == 'scalar': value = 'PASS'
    assert not Draft202012Validator(request_v2.transport_schema()).is_valid(value)


@pytest.mark.parametrize('reason', ['', ' \n\t '])
def test_transport_does_not_replace_strict_parser(reason):
    value = {c: dict(verdict='FAIL', reason=reason) for c in ('c1', 'c2', 'c3')}
    Draft202012Validator(request_v2.transport_schema()).validate(value)
    assert parser.parse(json.dumps(value)).code == 'BLANK_OR_NONSTRING_REASON'


def test_parser_hash_and_surrounding_markdown_rejection_are_unchanged():
    assert parser.artifact_hash() == 'd8d7fa7a853e0a09b73067f78304ae833b90e2405645b7818139b904ffc33783'
    value = json.dumps({c: dict(verdict='PASS', reason='Evidence') for c in ('c1', 'c2', 'c3')})
    assert parser.parse(value).status == 'VALID_OUTPUT'
    assert parser.parse('```json\n' + value + '\n```').code == 'INVALID_JSON'


@pytest.mark.parametrize('mode', [None, 'v1', 'json', 'unknown', 1])
def test_explicit_v2_mode_required(mode):
    with pytest.raises(Blocked): request_v2.OutputInterfaceV2(mode)


def test_v1_config_and_changed_prompt_cannot_be_reinterpreted():
    with pytest.raises(Blocked): request_v2.OutputInterfaceV2('prompt_only', 'strict-output-v1')
    with pytest.raises(Blocked):
        request_v2.build_request_v2(sample(), interface={'mode': 'prompt_only'}, prompt=prompt(),
                                   model=MODELS[0], model_digest='a'*64, repetition=1)
    with pytest.raises(Blocked):
        request_v2.build_request_v2(sample(), interface=request_v2.OutputInterfaceV2('prompt_only'),
                                   prompt=prompt() + b'changed', model=MODELS[0], model_digest='a'*64, repetition=1)


@pytest.mark.parametrize('field', ['request_version', 'output_interface_version', 'output_interface_mode',
    'transport_schema_sha256', 'output_interface_sha256', 'request_identity_sha256',
    'request_builder_sha256', 'rendered_request_sha256', 'prompt_name', 'seed', 'timeout_seconds'])
def test_changed_v2_sidecar_binding_is_rejected(field):
    result = built('json_schema')
    changed = replace(result, metadata={**result.metadata, field: 'changed'})
    with pytest.raises(Blocked): request_v2.validate_request_v2(changed)


@pytest.mark.parametrize('change', ['format', 'schema', 'tools', 'images', 'history',
                                  'budget', 'seed', 'prompt', 'think', 'timeout'])
def test_v2_http_boundary_rejects_mutations_before_connection(change):
    result = built('json_schema')
    payload = loads(result.body)
    if change == 'format': payload['format'] = 'json'
    if change == 'schema': payload['format']['properties']['c1']['properties']['verdict']['enum'] = ['PASS']
    if change == 'tools': payload['tools'] = []
    if change == 'images': payload['messages'][1]['images'] = []
    if change == 'history': payload['messages'].append(dict(role='assistant', content='prior output'))
    if change == 'budget': payload['options']['num_predict'] = 1024
    if change == 'seed': payload['options']['seed'] = 999
    if change == 'prompt': payload['messages'][0]['content'] += 'changed'
    if change == 'think': del payload['think']
    changed = replace(result, body=encode(payload), timeout=301 if change == 'timeout' else 300)
    def forbidden(*args, **kwargs): pytest.fail('Mutated request reached connection creation')
    client = provider.OllamaClient(request_validator=request_v2.validate_request_v2, connection_factory=forbidden)
    with pytest.raises(Blocked): client.send(changed, on_start=forbidden)


@pytest.mark.parametrize('mode', request_v2.MODES)
def test_default_v1_client_rejects_v2_and_explicit_client_sends_exact_bytes(mode):
    result = built(mode)
    calls = []
    class Connection:
        sock = None
        def __init__(self, *args, **kwargs): calls.append(('init', kwargs))
        def connect(self): pass
        def request(self, *args, **kwargs):
            calls.append(('send', kwargs['body']))
            raise ConnectionResetError('fabricated')
        def close(self): pass
    with pytest.raises(Blocked):
        provider.OllamaClient(connection_factory=Connection).send(result, on_start=lambda _: None)
    assert calls == []
    receipt = provider.OllamaClient(connection_factory=Connection,
        request_validator=request_v2.validate_request_v2).send(result, on_start=lambda _: None)
    assert calls[1] == ('send', result.body) and len(calls) == 2
    assert provider.classify(receipt).kind == 'TECHNICAL_FAILURE'
    with pytest.raises(Blocked):
        request_v2.validate_request_v2(request.Request(result.body, result.metadata))


def model_digests():
    return {model: str(i)*64 for i, model in enumerate(MODELS, 1)}


def test_pilot_exact_18_deterministic_dev_requests_without_oracle(monkeypatch, tmp_path):
    from rest_api_checker import oracle
    def forbidden(*args, **kwargs): pytest.fail('Pilot preparation measured reference truth')
    monkeypatch.setattr(oracle, 'evaluate_response', forbidden)
    files = pilot.pilot_files(['DEV-01', 'DEV-02'], model_digests())
    assert files == pilot.pilot_files(['DEV-01', 'DEV-02'], model_digests())
    plan = loads(files['manifest.json'])
    assert plan['planned_calls'] == 18 and plan['completed_calls'] == 0
    assert plan['status'] == 'PREPARED_NOT_EXECUTED'
    assert len(plan['slots']) == len({(s['case'], s['model'], s['mode']) for s in plan['slots']}) == 18
    assert all(s['seed'] == 101 and s['repetition'] == 1 for s in plan['slots'])
    for item in plan['files']:
        assert digest(files[item['path']]) == item['sha256']
    for slot in plan['slots']:
        body = files[slot['request_path']]
        metadata = loads(files[slot['provenance_path']])
        request_v2.validate_request_v2(request_v2.RequestV2(body, metadata))
        user = loads(loads(body)['messages'][1]['content'])
        assert set(user) == {'operation', 'openapi', 'observed_response'}
        assert user['observed_response']['body'].encode() == files[f"sources/{slot['case']}/body.bin"]
        assert slot['case'].encode() not in body
        assert not {'oracle', 'fault_id', 'reference_labels', 'expected', 'origin'} & set(user)
        assert encode(loads(body)['options']) == encode({**SETTINGS, 'seed': 101})
    dest = tmp_path/'prepared'
    assert pilot.prepare_pilot(['DEV-01', 'DEV-02'], model_digests(), dest) == plan
    assert {str(p.relative_to(dest)): p.read_bytes() for p in dest.rglob('*') if p.is_file()} == files
    with pytest.raises(FileExistsError): pilot.prepare_pilot(['DEV-01', 'DEV-02'], model_digests(), dest)


@pytest.mark.parametrize('cases', [[], ['DEV-01'], ['DEV-01', 'DEV-01'],
    ['DEV-01', 'FINAL-01'], ['DEV-01', 'DEV-13'], ['DEV-01', 'DEV-02', 'DEV-03']])
def test_pilot_rejects_wrong_case_scope(cases):
    with pytest.raises(Blocked): pilot.pilot_files(cases, model_digests())


def test_pilot_rejects_incomplete_models_and_research_output(tmp_path):
    with pytest.raises(Blocked): pilot.pilot_files(['DEV-01', 'DEV-02'], {MODELS[0]: 'a'*64})
    with pytest.raises(Blocked):
        pilot.prepare_pilot(['DEV-01', 'DEV-02'], model_digests(), RESEARCH/'forbidden-new-directory')
    with pytest.raises(Blocked):
        request_v2.build_request_v2(sample(), interface=request_v2.OutputInterfaceV2('json_schema'),
                                   prompt=prompt(), model=MODELS[0], model_digest='short', repetition=1)


def test_pilot_cli_prepares_only(tmp_path, capsys):
    path = tmp_path/'digests.json'
    path.write_bytes(encode(model_digests()))
    dest = tmp_path/'cli-prepared'
    assert pilot.main(['--cases', 'DEV-01', 'DEV-02', '--model-digests', str(path), '--output', str(dest)]) == 0
    assert capsys.readouterr().out == 'Prepared 18 requests; completed model calls: 0\n'
    assert loads((dest/'manifest.json').read_bytes())['completed_calls'] == 0
