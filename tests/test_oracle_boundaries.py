"""Implementation probes, distinct from the human-approved Q01–Q26."""
from copy import deepcopy
import json

import pytest
from rest_api_checker import OracleExecutionError, OracleNotReady, evaluate_response
from rest_api_checker.media_type import select_media

E = '/edx/validation/body'
H = '/resistance/validation/file'


def run(doc, body=b'{}', status=200, media='application/json', path=H):
    return evaluate_response(doc, path, 'post', status, media, body)


@pytest.mark.parametrize('body', [b'null', b'[]', b'{}', b'"hello"', b'123', b'1.5', b'true', b'false'])
def test_empty_schema_valid_json_kinds(contracts, body):
    assert run(contracts['htts'], body).vector == ('PASS', 'PASS', 'PASS')


@pytest.mark.parametrize('body', [b'', b'{broken', b'NaN', b'Infinity', b'-Infinity', b'\xff', b'{}{}'])
def test_invalid_representation(contracts, body):
    result = run(contracts['htts'], body)
    assert result.vector == ('PASS', 'PASS', 'FAIL')
    assert result.diagnostics[0].code == 'INVALID_JSON_REPRESENTATION'


@pytest.mark.parametrize('body,code', [
    (b'{"x":1,"x":2}', 'DUPLICATE_JSON_NAME'),
    (b'{"detail":[{"msg":"a","msg":"b"}]}', 'DUPLICATE_JSON_NAME'),
    (b'1e9999', 'UNQUALIFIED_NUMERIC_EXTREME'),
    (b'1e-9999', 'UNQUALIFIED_NUMERIC_EXTREME'),
    (b'1.0000000000000001', 'UNQUALIFIED_NUMERIC_EXTREME'),
    (b'9' * 5000, 'UNQUALIFIED_NUMERIC_EXTREME'),
])
def test_unresolved_json_no_labels(contracts, body, code):
    with pytest.raises(OracleNotReady) as caught:
        run(contracts['htts'], body)
    assert caught.value.code == code


@pytest.mark.parametrize('media', [None, '', 'application', 'application/json, text/plain',
    'application/json\r\nx: y', 'application/json; profile=x',
    'application/json; charset=latin-1', 'application/json; charset=utf-8; x=y',
    'application/json; charset="utf-8"', 'text/plain; charset=utf-8'])
def test_unqualified_headers_no_labels(contracts, media):
    with pytest.raises(OracleNotReady):
        run(contracts['htts'], media=media)


@pytest.mark.parametrize('media', ['application/json', ' Application/JSON ', 'application/json; charset=utf-8'])
def test_qualified_normalization(contracts, media):
    assert run(contracts['edx'], b'{"code":0}', media=media, path=E).c3 == 'PASS'


@pytest.mark.parametrize('media', ['text/plain', 'text/json'])
def test_edx_alternatives_match_component_but_hold_body(contracts, media):
    content = contracts['edx']['paths'][E]['post']['responses']['200']['content']
    assert select_media(content, media) == media
    with pytest.raises(OracleNotReady, match='UNQUALIFIED_REPRESENTATION'):
        run(contracts['edx'], media=media, path=E)


@pytest.mark.parametrize('status,expected', [(200, '200'), (201, '2XX'), (500, 'default')])
def test_exact_range_default_precedence(contracts, status, expected):
    doc = contracts['htts']
    responses = doc['paths'][H]['post']['responses']
    responses['2XX'] = deepcopy(responses['200'])
    responses['default'] = deepcopy(responses['422'])
    result = run(doc, b'{"detail":123}', status=status)
    assert result.selected_response == expected
    assert result.c3 == ('FAIL' if status == 500 else 'PASS')


def test_uncovered_status_short_circuits(contracts):
    result = run(contracts['htts'], b'{broken', status=500, media=None)
    assert result.vector == ('FAIL', 'NOT_APPLICABLE', 'NOT_APPLICABLE')


def test_media_mismatch_short_circuits(contracts):
    result = run(contracts['htts'], b'{broken', media='application/xml')
    assert result.vector == ('PASS', 'FAIL', 'NOT_APPLICABLE')


@pytest.mark.parametrize('value,expected', [('file', 'PASS'), (0, 'PASS'), (False, 'FAIL'), (None, 'FAIL'), ([], 'FAIL')])
def test_htts_loc_anyof_items(contracts, value, expected):
    body = json.dumps({'detail': [{'loc': [value], 'msg': 'x', 'type': 'x'}]}).encode()
    assert run(contracts['htts'], body, status=422).c3 == expected


@pytest.mark.parametrize('schema,code', [
    ({'$ref': '#/components/schemas/Absent'}, 'UNRESOLVED_REFERENCE'),
    ({'$ref': 'https://example.invalid/schema'}, 'UNSUPPORTED_REFERENCE'),
    ({'type': 'invalid'}, 'INVALID_SOURCE_SCHEMA'),
    ({'type': 'string', 'pattern': 'x'}, 'UNQUALIFIED_SCHEMA_KEYWORD'),
    ({'$schema': 'https://example.invalid/dialect'}, 'UNQUALIFIED_SCHEMA_KEYWORD'),
    ({'type': 'string', 'format': 'date'}, 'UNQUALIFIED_SCHEMA_FORMAT'),
    (None, 'UNSUPPORTED_SCHEMA_FORM'),
])
def test_source_problems_no_labels(contracts, schema, code):
    doc = contracts['htts']
    doc['paths'][H]['post']['responses']['200']['content']['application/json']['schema'] = schema
    with pytest.raises(OracleNotReady) as caught:
        run(doc, b'{broken')
    assert caught.value.code == code


def test_nested_unresolved_ref_checked_even_when_property_absent(contracts):
    doc = contracts['htts']
    doc['components']['schemas']['HTTPValidationError']['properties']['detail']['items']['$ref'] = '#/absent'
    with pytest.raises(OracleNotReady, match='UNRESOLVED_REFERENCE'):
        run(doc, status=422)


def test_schema_absence_is_not_empty_schema(contracts):
    del contracts['htts']['paths'][H]['post']['responses']['200']['content']['application/json']['schema']
    with pytest.raises(OracleNotReady, match='MISSING_SCHEMA'):
        run(contracts['htts'])


def test_response_local_reference(contracts):
    doc = contracts['htts']
    response = doc['paths'][H]['post']['responses']['200']
    doc['components']['responses'] = {'Ok': response}
    doc['paths'][H]['post']['responses']['200'] = {'$ref': '#/components/responses/Ok'}
    result = run(doc)
    assert result.c3 == 'PASS'
    assert result.schema_pointer == '#/components/responses/Ok/content/application~1json/schema'


def test_library_error_is_not_scientific_failure(contracts, monkeypatch):
    class BrokenValidator:
        def iter_errors(self, instance):
            raise RuntimeError('probe')
    monkeypatch.setattr('rest_api_checker.oracle.prepare_validator', lambda *args: BrokenValidator())
    with pytest.raises(OracleExecutionError) as caught:
        run(contracts['htts'])
    assert isinstance(caught.value.__cause__, RuntimeError)


def test_immutability_repeatability_and_diagnostics(contracts):
    doc = contracts['edx']
    before = deepcopy(doc)
    body = b'{"code":"0","data":[{"key":7}]}'
    first = run(doc, body, path=E)
    assert first == run(doc, body, path=E)
    assert doc == before
    assert body == b'{"code":"0","data":[{"key":7}]}'
    assert [d.instance_pointer for d in first.diagnostics] == ['/code', '/data/0/key']
    assert all(d.keyword == 'type' for d in first.diagnostics)


def test_file_input_is_read_only(contracts, contract_paths):
    path = contract_paths['edx']
    before = path.read_bytes()
    assert run(path, path=E) == run(contracts['edx'], path=E)
    assert path.read_bytes() == before


def test_unknown_metadata_is_not_an_input(contracts):
    with pytest.raises(TypeError):
        evaluate_response(contracts['htts'], H, 'post', 200, 'application/json', b'{}', fault_id='F01')


@pytest.mark.parametrize('status', [True, '200', 0, 600])
def test_invalid_status_not_coverage_failure(contracts, status):
    with pytest.raises(OracleNotReady, match='INVALID_OBSERVED_STATUS'):
        run(contracts['htts'], status=status)


@pytest.mark.parametrize('body,code', [
    (b'{"code":2147483648}', 'UNQUALIFIED_FORMAT_CASE'),
    (b'{"code":-2147483649}', 'UNQUALIFIED_FORMAT_CASE'),
    (b'{"code":0.0}', 'UNQUALIFIED_INTEGER_REPRESENTATION'),
])
def test_unqualified_edx_numeric_edges_are_held(contracts, body, code):
    with pytest.raises(OracleNotReady) as caught:
        run(contracts['edx'], body, path=E)
    assert caught.value.code == code


@pytest.mark.parametrize('body', [b'{"code":2147483647}', b'{"code":-2147483648}'])
def test_library_int32_boundary_does_not_add_fault(contracts, body):
    assert run(contracts['edx'], body, path=E).c3 == 'PASS'


@pytest.mark.parametrize('api', ['edx', 'htts'])
def test_contract_hash_guard_rejects_changed_bytes(tmp_path, monkeypatch, api):
    import conftest
    for record in conftest.MANIFEST['contracts'].values():
        dest = tmp_path / record['copy']
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((conftest.ROOT / record['copy']).read_bytes())
    changed = tmp_path / conftest.MANIFEST['contracts'][api]['copy']
    changed.write_bytes(changed.read_bytes() + b'\n')
    monkeypatch.setattr(conftest, 'ROOT', tmp_path)
    with pytest.raises(pytest.UsageError, match=f'{api} contract hash mismatch'):
        conftest.verified_bytes()


@pytest.mark.parametrize('path,method', [('/other', 'post'), (H, 'get')])
def test_unqualified_operation(contracts, path, method):
    with pytest.raises(OracleNotReady, match='UNQUALIFIED_OPERATION'):
        evaluate_response(contracts['htts'], path, method, 200, 'application/json', b'{}')
