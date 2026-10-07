"""Metadata-driven descriptions over fabricated rows; no SQL or model access."""
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace

import pytest

from rest_api_checker import live_demo, live_presenter as presenter
from rest_api_checker.experiment.encoding import encode


@pytest.mark.parametrize(('reference', 'title', 'needle'), [
    (['PASS', 'PASS', 'PASS'], '✓ conforming', 'matches the documented'),
    (['FAIL', 'NOT_APPLICABLE', 'NOT_APPLICABLE'], 'C1 fault', 'HTTP 500'),
    (['PASS', 'FAIL', 'NOT_APPLICABLE'], 'C2 fault', 'application/xml'),
    (['PASS', 'PASS', 'FAIL'], 'C3 fault', 'schema'),
    (None, 'Stored response case', 'Reference ???'),
])
def test_every_case_has_a_human_readable_description(reference, title, needle):
    result = presenter.describe_case(dict(case_code='Future case', status_code=500,
        content_type='application/xml', reference=reference))
    assert result['title'] == title
    assert needle.casefold() in result['description'].casefold()
    assert result['description'].strip()
    assert result['details'] == ['HTTP status: 500; Content-Type: application/xml']


def test_missing_metadata_has_truthful_fallback_and_unknown_reference():
    result = presenter.describe_case({'case_code': 'FUTURE-99'})
    assert result['reference_vector'] == '???'
    assert result['reference_text'] == 'Reference unavailable'
    assert result['description'] == 'Stored response case · HTTP unknown · not recorded · Reference ???'


def test_construction_intent_never_supplies_or_changes_reference():
    metadata = {'fault_control_family': 'F01', 'verification_target': {'expected_vector': ['FAIL']*3},
                'oracle': {'vector': ['FAIL']*3}, 'transformation': {'variant': 'status_500'}}
    row = dict(reference=['PASS']*3, origin='synthetic_inconsistency', metadata=metadata)
    result = presenter.describe_case(row)
    assert result['reference_vector'] == 'PPP'
    assert result['title'] == '✓ conforming'
    assert 'provenance, not a verdict' in ' '.join(result['details'])
    del row['reference']
    assert presenter.describe_case(row)['reference_vector'] == '???'


@pytest.mark.parametrize(('diagnostic', 'needle'), [
    ({'code': 'INVALID_JSON_REPRESENTATION'}, 'not valid JSON'),
    ({'code': 'SCHEMA_ASSERTION_FAILED', 'keyword': 'required', 'instance_pointer': '/detail/0'}, 'required property is missing at /detail/0'),
    ({'code': 'SCHEMA_ASSERTION_FAILED', 'keyword': 'type', 'instance_pointer': '/code'}, 'wrong JSON type at /code'),
    ({'code': 'SCHEMA_ASSERTION_FAILED', 'keyword': 'additionalProperties'}, 'additional properties are forbidden at body root'),
])
def test_reference_diagnostics_explain_actual_schema_failures(diagnostic, needle):
    result = presenter.describe_case(dict(reference=['PASS', 'PASS', 'FAIL'],
        reference_metadata={'diagnostics': [diagnostic]}))
    assert needle.casefold() in result['description'].casefold()


def test_controlled_modifications_use_parameters_and_parent_metadata():
    row = dict(reference=['PASS', 'PASS', 'FAIL'], parent_case='PARENT-A', metadata={
        'parent_status': 200, 'parent_content_type': 'application/json',
        'transformation': {'parameters': [['status', '500'], ['content_type', 'text/plain'],
            ['action', 'remove'], ['path', '["detail", 0, "msg"]']], 'variant': 'remove_msg'}})
    result = presenter.describe_case(row)
    assert 'HTTP status 200 → 500' in ' '.join(result['details'])
    assert 'Content-Type application/json → text/plain' in ' '.join(result['details'])
    assert 'removal at /detail/0/msg' in ' '.join(result['details'])
    assert 'Controlled change' not in result['description']
    assert 'Derived from: PARENT-A' in result['details']


def test_explicit_empty_schema_is_described_only_when_contract_confirms_it():
    row = dict(reference=['PASS']*3, schema_empty=True)
    assert presenter.describe_case(row)['title'] == '✓ conforming'
    row['schema_empty'] = False
    assert presenter.describe_case(row)['title'] == '✓ conforming'


def test_case_description_and_control_sequences_are_safe_text():
    result = presenter.describe_case(dict(description='Stored [bold]label[/bold]\x1b[2J',
        reference=['PASS']*3, metadata={'root_family': 'FAMILY\x07'}))
    assert '\x1b' not in str(result['details']) and '\\x1b' in ' '.join(result['details'])
    assert '[bold]label[/bold]' in ' '.join(result['details'])
    assert result['details'][-1] == 'Case family: FAMILY\\x07'


def test_services_and_operations_use_available_metadata_without_inventing_descriptions():
    assert presenter.service_label(dict(service='Future API', service_description='Stored description')) == 'Future API\nStored description'
    assert presenter.service_label(dict(service='Unknown')) == 'Unknown\nStored API service'
    resistance = dict(service='htts', path='/resistance/validation/file', method='post',
                      operation_summary='Validation Of Incoming File')
    assert presenter.service_label(resistance) == 'Resistance\nFile validation service'
    assert presenter.operation_label(resistance) == 'POST /resistance/validation/file   Validate incoming file'
    assert presenter.service_name(dict(service='htts', path='/other')) == 'htts'


def test_model_label_uses_actual_tag_size_and_quantization():
    row = dict(name='future-model:23b', parameters_b=Decimal('23.00'), quantization='Q4_K_M',
               availability='installed; not currently loaded')
    assert presenter.model_label(row) == 'future-model:23b   Q4_K_M   installed; not currently loaded'
    assert presenter.model_label({'name': 'other:tag'}) == 'other:tag'


def test_contract_context_preserves_descriptions_and_resolves_only_local_schema_references():
    document = {'info': {'title': 'Future API'}, 'paths': {'/validate': {'post': {
        'summary': 'Validate incoming document', 'responses': {'200': {'content': {
            'application/json': {'schema': {'$ref': '#/components/schemas/Empty'}}}}}}}},
        'components': {'schemas': {'Empty': {}}}}
    value = presenter.contract_context(document, dict(http_method='post', path_template='/validate'),
        {'schema_pointer': '#/paths/~1validate/post/responses/200/content/application~1json/schema'})
    assert value['schema_empty'] is True
    assert value['operation_summary'] == 'Validate incoming document'
    assert value['contract_title'] == 'Future API'
    assert presenter.contract_context({}, dict(http_method='post', path_template='/missing'), {})['schema_empty'] is False


def test_catalog_enriches_dynamic_cases_without_writes_or_reference_inference(monkeypatch):
    tables = {
        'datasets': [dict(id=1, name='FABRICATED DEV', purpose='development')],
        'dataset_cases': [dict(id=87, dataset_id=1, case_id=9, reference_id=3, case_code='FUTURE-1')],
        'test_cases': [dict(id=9, operation_id=5, response_id=7, family_id=4, parent_case_id=None,
            source_file_id=2, source_pointer='/cases/0', native_case_id='native-name',
            origin='natural_observation', description=None)],
        'api_operations': [dict(id=5, contract_id=6, http_method='post', path_template='/future')],
        'api_contracts': [dict(id=6, api_id=8, file_id=1)],
        'apis': [dict(id=8, name='Future API', description='API description')],
        'responses': [dict(id=7, status_code=200, content_type='application/json')],
        'case_families': [dict(id=4, code='FUTURE-FAMILY')],
        'reference_results': [dict(id=3, case_id=9, c1='PASS', c2='PASS', c3='FAIL',
            source_file_id=2, source_pointer='/cases/0/oracle')],
        'models': [dict(id=11, name=live_demo.MODELS[0]), dict(id=99, name='unapproved:1b')],
    }
    metadata = {'description': 'Original stored response', 'oracle': {'diagnostics': [
        {'code': 'SCHEMA_ASSERTION_FAILED', 'keyword': 'required', 'instance_pointer': '/item'}]}}
    files = {1: encode({'paths': {'/future': {'post': {'summary': 'Future operation'}}}}),
             2: encode({'cases': [metadata]})}
    before = deepcopy(tables), deepcopy(files)
    repo = SimpleNamespace(file=files.__getitem__)
    monkeypatch.setattr(live_demo, 'rows', lambda repo, table: deepcopy(tables.get(table, [])))
    result = live_demo.catalog(repo)
    case = result['cases'][0]
    assert case['case_code'] == 'FUTURE-1' and case['native_case_id'] == 'native-name'
    assert case['service'] == 'Future API' and case['operation_id'] == 5
    assert case['operation_summary'] == 'Future operation'
    assert case['family'] == 'FUTURE-FAMILY'
    assert case['presentation']['reference_vector'] == 'PPF'
    assert 'required property is missing at /item' in case['presentation']['description']
    assert result['models'] == [dict(id=11, name=live_demo.MODELS[0])]
    assert (tables, files) == before


@pytest.mark.parametrize(('vector', 'kind'), [
    (['PASS'] * 3, 'conforming'), (['FAIL', 'NOT_APPLICABLE', 'NOT_APPLICABLE'], 'c1'),
    (['PASS', 'FAIL', 'NOT_APPLICABLE'], 'c2'), (['PASS', 'PASS', 'FAIL'], 'c3'), (None, 'unknown'),
])
def test_case_type_filter_uses_only_bound_reference(vector, kind):
    row = dict(reference=vector, metadata={'fault_control_family': 'C2',
        'original_candidate': {'vector': ['FAIL'] * 3, 'C1': 'FAIL'}})
    assert presenter.case_type(row) == kind
    assert presenter.filter_cases([row], 'all') == [row]
    if kind != 'unknown':
        assert presenter.filter_cases([row], kind) == [row]
    assert presenter.filter_cases([row], 'controls') == []


def test_controls_are_explicit_metadata_and_do_not_replace_reference_category():
    row = dict(reference=['PASS', 'PASS', 'FAIL'], metadata={'formatting_control': True})
    assert presenter.filter_cases([row], 'controls') == [row]
    assert presenter.filter_cases([row], 'c3') == [row]
    row['metadata']['formatting_control'] = False
    assert presenter.filter_cases([row], 'controls') == []
    with pytest.raises(ValueError, match='Unknown case type'):
        presenter.filter_cases([row], 'made-up')


def test_compact_text_omits_provenance_and_cleans_known_service_operation_names():
    row = dict(service='edx', method='post', path='/EDX/Validation/body',
        operation_summary='Validation of incoming stream from POST body (post call to /EDX/Validation/body)',
        reference=['PASS'] * 3, description='Long provenance. ' * 100)
    assert presenter.service_label(row) == 'EDX\nDocument/data-stream validation service'
    assert presenter.operation_label(row) == 'POST /EDX/Validation/body   Validate incoming data stream'
    assert len(presenter.describe_case(row)['description']) < 150
    assert presenter.model_label(dict(name='gemma3:27b', quantization='Q4_K_M')) == 'Gemma 3 27B   Q4_K_M'


def test_schema_pointer_casing_is_not_altered_in_description():
    row = dict(reference=['PASS', 'PASS', 'FAIL'], reference_metadata={'diagnostics': [
        {'code': 'SCHEMA_ASSERTION_FAILED', 'keyword': 'type', 'instance_pointer': '/CaseSensitive'}]})
    assert '/CaseSensitive' in presenter.describe_case(row)['description']



def test_final_formatting_control_uses_preserved_provenance_without_relabelling():
    row = dict(reference=['PASS'] * 3,
        metadata={'original_candidate': {'service_state': 'formatting_control'}})
    assert presenter.filter_cases([row], 'controls') == [row]
    assert presenter.filter_cases([row], 'conforming') == [row]
