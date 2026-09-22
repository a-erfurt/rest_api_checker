"""Development construction probes; not a released or scored dataset."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import inspect
import json

import pytest

from rest_api_checker import OracleExecutionError, OracleNotReady, evaluate_response
from rest_api_checker import construction as c


@pytest.fixture
def snapshots(contract_paths):
    return {api: c.ContractSnapshot(api, path.read_bytes()) for api, path in contract_paths.items()}


def parent(snapshots, api='edx', status=200, body=b'{"code":0}', media='application/json'):
    return c.construct_parent('parent', snapshots[api], c.Response(status, media, body),
                              construction='explicit test parent; no dataset membership')


# Independent literal transformation expectations, including every approved variant.
FAULTS = [
    ('F03', 'string', 'edx', 200, b'{"code":0}', b'{"code":"0"}'),
    ('F03', 'boolean', 'edx', 200, b'{"code":0}', b'{"code":false}'),
    ('F03', 'null', 'edx', 200, b'{"code":0}', b'{"code":null}'),
    ('F04', 'root', 'edx', 200, b'{}', b'{"Code":0}'),
    ('F04', 'nested', 'edx', 200, b'{"data":[{}]}', b'{"data":[{"extra":true}]}'),
    ('F05', 'integer_key', 'edx', 200, b'{"data":[{"key":"seed","value":"kept"}]}',
     b'{"data":[{"key":7,"value":"kept"}]}'),
    ('F06', 'remove_msg', 'htts', 422, b'{"detail":[{"loc":[],"msg":"seed","type":"missing"}]}',
     b'{"detail":[{"loc":[],"type":"missing"}]}'),
    ('F07', 'string_loc', 'htts', 422, b'{"detail":[{"loc":[],"msg":"seed","type":"missing"}]}',
     b'{"detail":[{"loc":"file","msg":"seed","type":"missing"}]}'),
    ('F08', 'null', 'htts', 422, b'{"detail":[]}', b'{"detail":null}'),
    ('F08', 'integer', 'htts', 422, b'{"detail":[]}', b'{"detail":123}'),
]


@pytest.mark.parametrize('family,variant,api,status,raw,expected', FAULTS,
                         ids=[f'{row[0]}-{row[1]}' for row in FAULTS])
def test_schema_faults(snapshots, family, variant, api, status, raw, expected):
    original = parent(snapshots, api, status, raw)
    result = c.mutate('child', original, family, variant=variant)
    assert result.response == c.Response(status, 'application/json', expected)
    assert result.result.vector == ('PASS', 'PASS', 'FAIL')
    assert result.result.overall == 'INCONSISTENT'
    assert result.origin == c.Origin.INCONSISTENCY
    assert result.before.vector == ('PASS', 'PASS', 'PASS')
    assert result.parent is original
    assert original.response.body == raw
    assert result.transformation.family == family
    assert result.transformation.variant == variant
    assert result.transformation.body_edit.apply(raw) == expected
    assert result.parent_sha256 == original.response.sha256
    assert result.response.sha256 != result.parent_sha256
    assert result.result == evaluate_response(json.loads(original.contract.raw),
        original.contract.operation_path, 'post', status, 'application/json', expected)


@pytest.mark.parametrize('api,status,body', [
    ('edx', 200, b' { "code" : 500 }\n'),
    ('htts', 200, b' [ 1, "seed" ]\n'),
    ('htts', 422, b' { "detail" : [] }\n'),
])
@pytest.mark.parametrize('family', ['F01', 'F02', 'F09'])
def test_shared_faults_every_branch(snapshots, api, status, body, family):
    original = parent(snapshots, api, status, body)
    child = c.mutate('child', original, family)
    assert child.before.vector == ('PASS', 'PASS', 'PASS')
    assert child.parent.response.body == body
    assert child.response.sha256 != child.parent_sha256
    if family == 'F01':
        assert child.response == c.Response(500, 'application/json', body)
        assert child.result.vector == ('FAIL', 'NOT_APPLICABLE', 'NOT_APPLICABLE')
        assert child.result.selected_response is None
        assert child.transformation.parameters == (('status', '500'),)
    elif family == 'F02':
        media = 'application/xml' if api == 'edx' else 'text/plain'
        assert child.response == c.Response(status, media, body)
        assert child.result.vector == ('PASS', 'FAIL', 'NOT_APPLICABLE')
        assert child.transformation.parameters == (('content_type', media),)
    else:
        assert child.response == c.Response(status, 'application/json', b'{broken')
        assert child.result.vector == ('PASS', 'PASS', 'FAIL')
        assert child.result.diagnostics[0].code == 'INVALID_JSON_REPRESENTATION'
        assert child.transformation.body_edit.apply(body) == b'{broken'


CONTROLS = [
    ('K01', 'omitted', 'edx', 200, b'{}'),
    ('K01', 'integer_code', 'edx', 200, b'{"code":500}'),
    ('K01', 'nullable', 'edx', 200, b'{"message":null,"data":null}'),
    ('K01', 'nested_strings', 'edx', 200, b'{"data":[{"key":"a","value":"b"}]}'),
    ('K01', 'nested_optional_nullable', 'edx', 200,
     b'{"code":0,"message":"ok","warning":null,"mode":null,"data":[{}, {"key":null,"value":null}]}'),
    ('K01', 'charset', 'edx', 200, b'{"code":0}'),
    ('K02', 'null', 'htts', 200, b'null'),
    ('K02', 'array', 'htts', 200, b'[1,"x"]'),
    ('K02', 'object', 'htts', 200, b'{"detail":123}'),
    ('K03', 'omitted', 'htts', 422, b'{}'),
    ('K03', 'empty_detail', 'htts', 422, b'{"detail":[]}'),
    ('K03', 'string_locations', 'htts', 422,
     b'{"detail":[{"loc":["body","file"],"msg":"Field required","type":"missing","input":null}]}'),
    ('K03', 'integer_location_extras', 'htts', 422,
     b'{"detail":[{"loc":[0],"msg":"x","type":"x","extra":1}],"extra":true}'),
]


@pytest.mark.parametrize('family,variant,api,status,body', CONTROLS,
                         ids=[f'{row[0]}-{row[1]}' for row in CONTROLS])
def test_controls(snapshots, family, variant, api, status, body):
    case = c.construct_control('control', snapshots[api], family, variant)
    media = 'application/json; charset=utf-8' if variant == 'charset' else 'application/json'
    assert case.response == c.Response(status, media, body)
    assert case.result.vector == ('PASS', 'PASS', 'PASS')
    assert case.result.overall == 'CONSISTENT'
    assert case.origin == c.Origin.CONTROL
    assert case.parent is None and case.before is None
    assert case.transformation.family == family
    assert case.transformation.variant == variant
    assert case.transformation.parameters


@pytest.mark.parametrize('raw,expected', [
    (b'{"detail":[{"msg":"x", "loc":[],"type":"x"}]}', b'{"detail":[{"loc":[],"type":"x"}]}'),
    (b'{"detail":[{"loc":[], "type":"x", "msg":"x"}]}', b'{"detail":[{"loc":[], "type":"x"}]}'),
    (b'{"detail":[{"loc":[], "msg":"x", "type":"x"}]}', b'{"detail":[{"loc":[], "type":"x"}]}'),
])
def test_msg_deletion_in_each_member_position(snapshots, raw, expected):
    case = c.mutate('child', parent(snapshots, 'htts', 422, raw), 'F06')
    assert case.response.body == expected


def test_splice_preserves_unicode_escapes_whitespace_and_other_items(snapshots):
    raw = ' {"message":"Grüße 🧪", "data" : [{"key":"untouched"}, {"key":"target", "value":"\\u0061"}]}\n'.encode()
    original = parent(snapshots, body=raw)
    child = c.mutate('child', original, 'F05', item_index=1)
    assert child.response.body == raw.replace(b'"target"', b'7')
    assert child.transformation.parameters[0] == ('item_index', '1')
    assert original.response.body is raw


def test_escaped_target_name_is_preserved(snapshots):
    raw = b'{"co\\u0064e":0,"message":"code:0"}'
    child = c.mutate('child', parent(snapshots, body=raw), 'F03')
    assert child.response.body == b'{"co\\u0064e":"0","message":"code:0"}'


@pytest.mark.parametrize('raw,expected', [
    (b' { }\n', b' { "Code":0}\n'),
    (b'{"code":0 }', b'{"code":0 ,"Code":0}'),
])
def test_insert_preserves_existing_bytes(snapshots, raw, expected):
    assert c.mutate('child', parent(snapshots, body=raw), 'F04').response.body == expected


@pytest.mark.parametrize('family,variant,api,status,body,code', [
    ('F03', None, 'edx', 200, b'{}', 'INTEGER_CODE_PARENT_REQUIRED'),
    ('F04', 'nested', 'edx', 200, b'{"data":[{"key":"a"}]}', 'EMPTY_DATA_ITEM_REQUIRED'),
    ('F05', None, 'edx', 200, b'{"data":[{"key":null}]}', 'STRING_KEY_PARENT_REQUIRED'),
    ('F05', None, 'edx', 200, b'{"data":null}', 'MISSING_MUTATION_TARGET'),
    ('F06', None, 'htts', 422, b'{"detail":[]}', 'MISSING_MUTATION_TARGET'),
    ('F07', None, 'htts', 422, b'{}', 'MISSING_MUTATION_TARGET'),
    ('F08', None, 'htts', 422, b'{}', 'ARRAY_DETAIL_PARENT_REQUIRED'),
    ('F08', None, 'htts', 200, b'{"detail":[]}', 'INAPPLICABLE_FAMILY'),
    ('F04', None, 'htts', 422, b'{}', 'INAPPLICABLE_FAMILY'),
    ('F06', None, 'edx', 200, b'{}', 'INAPPLICABLE_FAMILY'),
    ('F10', None, 'edx', 200, b'{}', 'UNAPPROVED_FAULT_FAMILY'),
    ('F07', 'remove_type', 'htts', 422, b'{}', 'UNAPPROVED_FAULT_VARIANT'),
])
def test_rejected_preconditions(snapshots, family, variant, api, status, body, code):
    original = parent(snapshots, api, status, body)
    with pytest.raises(c.ConstructionRejected, match=code) as caught:
        c.mutate('child', original, family, variant=variant)
    assert caught.value.parent is original
    assert caught.value.candidate is None


@pytest.mark.parametrize('index', [-1, True, 0.5, '0', 3])
def test_invalid_item_index(snapshots, index):
    original = parent(snapshots, body=b'{"data":[{"key":"a"}]}')
    with pytest.raises(c.ConstructionRejected):
        c.mutate('child', original, 'F05', item_index=index)


def test_irrelevant_parameter_and_charset_fault_parent_rejected(snapshots):
    with pytest.raises(c.ConstructionRejected, match='INVALID_ITEM_INDEX'):
        c.mutate('child', parent(snapshots), 'F03', item_index=0)
    with pytest.raises(c.ConstructionRejected, match='EXACT_JSON_MEDIA'):
        c.mutate('child', parent(snapshots, media='application/json; charset=utf-8'), 'F09')


@pytest.mark.parametrize('status,media,body,vector', [
    (500, 'application/json', b'{}', ('FAIL', 'NOT_APPLICABLE', 'NOT_APPLICABLE')),
    (200, 'application/xml', b'{}', ('PASS', 'FAIL', 'NOT_APPLICABLE')),
    (200, 'application/json', b'{"code":null}', ('PASS', 'PASS', 'FAIL')),
    (200, 'application/json', b'{broken', ('PASS', 'PASS', 'FAIL')),
])
def test_nonconformant_parent_never_repaired(snapshots, status, media, body, vector):
    response = c.Response(status, media, body)
    with pytest.raises(c.ConstructionRejected, match='NONCONFORMANT_PARENT') as caught:
        c.construct_parent('invalid', snapshots['edx'], response, construction='explicit invalid probe')
    assert caught.value.candidate.response is response
    assert caught.value.candidate.result.vector == vector


def test_natural_observations_keep_raw_archive_and_are_not_filtered(snapshots):
    archive = c.Observation('archive://run-1', b'raw request', b'raw response')
    natural = c.observe('natural', snapshots['edx'], c.Response(200, 'application/json', b'{}'), archive)
    child = c.mutate('child', natural, 'F04')
    assert natural.origin == c.Origin.NATURAL
    assert child.parent.observation is archive
    assert child.origin == c.Origin.INCONSISTENCY
    failed = c.observe('natural-failure', snapshots['edx'], c.Response(500, None, b'original'), archive)
    assert failed.origin == c.Origin.NATURAL
    assert failed.result.overall == 'INCONSISTENT'
    with pytest.raises(c.ConstructionRejected, match='NONCONFORMANT_PARENT') as caught:
        c.mutate('child', failed, 'F09')
    assert caught.value.before == failed.result
    assert caught.value.parent is failed


def test_parent_remeasured_instead_of_trusting_stored_label(snapshots):
    original = parent(snapshots)
    forged = replace(original, response=replace(original.response, body=b'{"code":false}'))
    with pytest.raises(c.ConstructionRejected, match='NONCONFORMANT_PARENT') as caught:
        c.mutate('child', forged, 'F03')
    assert caught.value.before.vector == ('PASS', 'PASS', 'FAIL')


@pytest.mark.parametrize('mode,code', [('no_op', 'NO_OP_MUTATION'), ('ineffective', 'INEFFECTIVE_MUTATION')])
def test_no_op_and_ineffective_outcomes_retained(snapshots, monkeypatch, mode, code):
    original = parent(snapshots)
    replacement = original.response.body if mode == 'no_op' else b'{"code":500}'
    monkeypatch.setattr(c, '_body_edit', lambda *args: c.BodyEdit(0, len(original.response.body), replacement))
    with pytest.raises(c.ConstructionRejected, match=code) as caught:
        c.mutate('child', original, 'F03')
    candidate = caught.value.candidate
    assert candidate.result.vector == ('PASS', 'PASS', 'PASS')
    assert candidate.origin == c.Origin.CONTROL
    assert candidate.transformation.family == 'F03'
    assert candidate.response.body == replacement
    assert candidate.parent is original


def test_unexpected_vector_retained_without_overwriting(snapshots, monkeypatch):
    original = parent(snapshots)
    unexpected = evaluate_response(json.loads(original.contract.raw), original.contract.operation_path,
                                   'post', 500, 'application/json', b'{}')
    real = c.oracle.evaluate_response

    def surprising_oracle(**kwargs):
        return real(**kwargs) if kwargs['body'] == original.response.body else unexpected

    monkeypatch.setattr(c.oracle, 'evaluate_response', surprising_oracle)
    with pytest.raises(c.ConstructionRejected, match='UNEXPECTED_FAULT_PROFILE') as caught:
        c.mutate('child', original, 'F03')
    assert caught.value.candidate.result is unexpected
    assert caught.value.candidate.response.body == b'{"code":"0"}'


def test_schema_mutation_cannot_be_admitted_as_representation_failure(snapshots, monkeypatch):
    original = parent(snapshots)
    monkeypatch.setattr(c, '_body_edit', lambda *args: c.BodyEdit(0, len(original.response.body), b'{broken'))
    with pytest.raises(c.ConstructionRejected, match='UNEXPECTED_FAULT_DIAGNOSTIC') as caught:
        c.mutate('child', original, 'F03')
    assert caught.value.candidate.result.vector == ('PASS', 'PASS', 'FAIL')
    assert caught.value.candidate.result.diagnostics[0].code == 'INVALID_JSON_REPRESENTATION'


def test_f09_requires_representation_diagnostic(snapshots, monkeypatch):
    original = parent(snapshots)
    real = c.oracle.evaluate_response
    schema_failure = real(json.loads(original.contract.raw), original.contract.operation_path,
                          'post', 200, 'application/json', b'{"code":null}')
    def wrong_diagnostic(**kwargs):
        return schema_failure if kwargs['body'] == b'{broken' else real(**kwargs)
    monkeypatch.setattr(c.oracle, 'evaluate_response', wrong_diagnostic)
    with pytest.raises(c.ConstructionRejected, match='UNEXPECTED_FAULT_DIAGNOSTIC') as caught:
        c.mutate('child', original, 'F09')
    assert caught.value.candidate.result is schema_failure


def test_oracle_receives_only_evidence_before_and_after(snapshots, monkeypatch):
    calls = []
    real = c.oracle.evaluate_response

    def spy(**kwargs):
        calls.append(kwargs)
        assert set(kwargs) == {'contract', 'operation_path', 'method', 'status', 'content_type', 'body'}
        return real(**kwargs)

    monkeypatch.setattr(c.oracle, 'evaluate_response', spy)
    original = parent(snapshots)
    calls.clear()
    child = c.mutate('K01-intentionally-misleading-ID', original, 'F03')
    assert len(calls) == 2
    assert calls[0]['body'] == original.response.body
    assert calls[1]['body'] == child.response.body
    changed_metadata = replace(child, case_id='CONSISTENT', origin=c.Origin.CONTROL,
                               transformation=c.Transformation('K01', 'expected_PASS'))
    assert c._measure(changed_metadata.contract, changed_metadata.response) == child.result
    assert child.result.overall == 'INCONSISTENT'


def test_oracle_interface_has_no_metadata_or_expected_label_input():
    assert tuple(inspect.signature(evaluate_response).parameters) == (
        'contract', 'operation_path', 'method', 'status', 'content_type', 'body')
    for forbidden in ('fault_id', 'family', 'expected_vector', 'expected_label', 'origin'):
        with pytest.raises(TypeError, match='unexpected keyword'):
            evaluate_response({}, '', 'post', 200, None, b'', **{forbidden: 'PASS'})


def test_actual_status_changes_reference_not_intent(snapshots):
    body = b'{"detail":123}'
    at_200 = c.construct_control('200', snapshots['htts'], 'K02', 'object')
    with pytest.raises(c.ConstructionRejected) as caught:
        parent(snapshots, 'htts', 422, body)
    assert at_200.result.vector == ('PASS', 'PASS', 'PASS')
    assert caught.value.candidate.result.vector == ('PASS', 'PASS', 'FAIL')


@pytest.mark.parametrize('error', [OracleNotReady('TEST_HOLD'), OracleExecutionError('test failure')])
def test_oracle_failures_propagate_without_labels(snapshots, monkeypatch, error):
    original = parent(snapshots)
    def fail(**kwargs):
        raise error
    monkeypatch.setattr(c.oracle, 'evaluate_response', fail)
    with pytest.raises(type(error)) as caught:
        c.mutate('child', original, 'F03')
    assert caught.value is error


def test_contract_and_response_hashes_and_immutability(snapshots):
    original = parent(snapshots)
    assert original.contract.sha256 == hashlib.sha256(original.contract.raw).hexdigest()
    envelope = ['response-v1', 200, 'application/json', original.response.body.hex()]
    assert original.response.sha256 == hashlib.sha256(json.dumps(envelope, separators=(',', ':')).encode()).hexdigest()
    for field, value in [('status', 500), ('content_type', 'application/xml'), ('body', b'{}')]:
        assert replace(original.response, **{field: value}).sha256 != original.response.sha256
    with pytest.raises(FrozenInstanceError):
        original.response.body = b'changed'
    with pytest.raises(FrozenInstanceError):
        original.case_id = 'changed'
    with pytest.raises(TypeError):
        c.Response(200, 'application/json', bytearray(b'{}'))
    with pytest.raises(ValueError, match='qualified contract'):
        c.ContractSnapshot('edx', snapshots['edx'].raw + b'\n')
    with pytest.raises(ValueError, match='qualified contract'):
        c.ContractSnapshot('edx', snapshots['htts'].raw)


def test_invalid_construction_requests(snapshots):
    with pytest.raises(ValueError, match='distinct case ID'):
        c.mutate('parent', parent(snapshots), 'F03')
    with pytest.raises(ValueError, match='nonempty'):
        c.construct_control('', snapshots['edx'], 'K01', 'omitted')
    with pytest.raises(c.ConstructionRejected, match='INAPPLICABLE_FAMILY'):
        c.construct_control('control', snapshots['edx'], 'K02', 'null')
    with pytest.raises(c.ConstructionRejected, match='UNAPPROVED_CONTROL_VARIANT'):
        c.construct_control('control', snapshots['htts'], 'K02', 'boolean')


def test_control_outcome_is_checked_not_assumed(snapshots, monkeypatch):
    monkeypatch.setitem(c._CONTROLS, ('K01', 'omitted'), ('edx', 200, b'{"code":null}'))
    with pytest.raises(c.ConstructionRejected, match='UNEXPECTED_CONTROL_PROFILE') as caught:
        c.construct_control('control', snapshots['edx'], 'K01', 'omitted')
    assert caught.value.candidate.result.vector == ('PASS', 'PASS', 'FAIL')


def test_explicit_control_retains_nonconformant_context(snapshots):
    context = c.observe('natural', snapshots['edx'],
        c.Response(200, 'application/json; charset=utf-8', b'{"Code":0}'),
        c.Observation('test archive', b'request', b'headers'))
    control = c.construct_parent('control', snapshots['edx'],
        c.Response(200, 'application/json', b'{"code":0}'),
        construction='explicit lowercase control', parent=context)
    assert control.parent is context
    assert control.before.vector == ('PASS', 'PASS', 'FAIL')
    assert control.result.vector == ('PASS',) * 3
    assert control.transformation.body_edit.apply(context.response.body) == control.response.body
    assert dict(control.transformation.parameters)['content_type'] == 'application/json'
    child = c.mutate('fault', control, 'F03')
    assert child.parent.parent is context
    assert child.before.vector == ('PASS',) * 3


def test_template_control_retains_parent_and_full_replacement(snapshots):
    original = parent(snapshots, 'htts', body=b'{"Warning":"unchanged context"}')
    control = c.construct_control('null', snapshots['htts'], 'K02', 'null', parent=original)
    assert control.parent is original
    assert control.before == original.result
    assert control.transformation.body_edit == c.BodyEdit(0, len(original.response.body), b'null')


@pytest.mark.parametrize('template', [False, True])
def test_control_lineage_rejects_contract_mismatch_and_ancestor_id(snapshots, template):
    original = parent(snapshots)

    def construct(case_id, contract):
        if template:
            return c.construct_control(case_id, contract, 'K02', 'null', parent=original)
        return c.construct_parent(case_id, contract, c.Response(200, 'application/json', b'{}'),
                                   construction='test', parent=original)

    with pytest.raises(c.ConstructionRejected, match='CONTROL_PARENT_CONTRACT_MISMATCH'):
        construct('child', snapshots['htts'])
    with pytest.raises(ValueError, match='distinct case ID'):
        construct(original.case_id, snapshots['htts'])
