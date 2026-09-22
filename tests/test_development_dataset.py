"""Materialization probes using temporary archives, never released DEV artifacts.

Bodies match the pinned inventory; acquisition metadata is explicitly test-only.
The real research input pins are exercised during the recorded staging run.
"""
from copy import deepcopy
import hashlib
import json

import pytest

from rest_api_checker import construction as c
from rest_api_checker import development_dataset as d
from rest_api_checker.models import OracleExecutionError

SPEC = json.loads(d.SPEC_PATH.read_bytes())
BODIES = {
    'EDX-P02': b'{"Code":0,"Message":null,"Warning":null,"Mode":"CSV","Data":null}',
    'HTTS-H01': (b'{"Code":0,"Message":null,"Warning":"Columns names are inferred from the file structure",'
                 b'"Mode":"Triple-R, Tab-delimited"}'),
    'HTTS-H05': b'{"detail":[{"type":"missing","loc":["body","file"],"msg":"Field required","input":null}]}',
}
EXPECTED = [
    (200, 'application/json; charset=utf-8', BODIES['EDX-P02'], 'PPF', 'NATURAL', None),
    (200, 'application/json', b'{"code":0}', 'PPP', 'SYNTHETIC_CONFORMANT', 'DEV-01'),
    (500, 'application/json', b'{"code":0}', 'FNN', 'SYNTHETIC_INCONSISTENT', 'DEV-02'),
    (200, 'application/xml', b'{"code":0}', 'PFN', 'SYNTHETIC_INCONSISTENT', 'DEV-02'),
    (200, 'application/json', b'{"code":"0"}', 'PPF', 'SYNTHETIC_INCONSISTENT', 'DEV-02'),
    (200, 'application/json', b'{"code":0,"Code":0}', 'PPF', 'SYNTHETIC_INCONSISTENT', 'DEV-02'),
    (200, 'application/json', BODIES['HTTS-H01'], 'PPP', 'NATURAL', None),
    (200, 'application/json', b'null', 'PPP', 'SYNTHETIC_CONFORMANT', 'DEV-07'),
    (422, 'application/json', BODIES['HTTS-H05'], 'PPP', 'NATURAL', None),
    (422, 'application/json', b'{"detail":[{"type":"missing","loc":["body","file"],"input":null}]}',
     'PPF', 'SYNTHETIC_INCONSISTENT', 'DEV-09'),
    (200, 'text/plain', BODIES['HTTS-H01'], 'PFN', 'SYNTHETIC_INCONSISTENT', 'DEV-07'),
    (200, 'application/json', b'{broken', 'PPF', 'SYNTHETIC_INCONSISTENT', 'DEV-07'),
]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tree(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.fixture
def archive(tmp_path, monkeypatch, contract_paths):
    research = tmp_path / 'test-research'
    spec = deepcopy(SPEC)
    for path in spec['sources']:
        target = research / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'Test-only provenance, not a research observation.\n')
    for api, path in spec['contracts'].items():
        (research / path).write_bytes(contract_paths[api].read_bytes())
    for family, root in spec['roots'].items():
        directory = research / root['source_directory']
        body = BODIES[family]
        status = 422 if family == 'HTTS-H05' else 200
        media = 'application/json; charset=utf-8' if family == 'EDX-P02' else 'application/json'
        (directory / 'response_body.bin').write_bytes(body)
        (directory / 'response_headers.txt').write_bytes(
            f'HTTP/2 {status} \r\ncontent-type: {media}\r\n\r\n'.encode())
        (directory / 'curl_result.txt').write_bytes(
            f'http_code={status}\ncontent_type={media}\nsize_download={len(body)}\n'.encode())
    spec['sources'] = {p: sha((research / p).read_bytes()) for p in spec['sources']}
    spec_path = tmp_path / 'test_inventory.json'
    spec_path.write_bytes(d._json(spec))
    monkeypatch.setattr(d, 'SPEC_PATH', spec_path)
    # Version capture is tested separately against the real implementation files.
    monkeypatch.setattr(d, '_versions', lambda: {'test_only': True})
    return research, tmp_path / 'output', spec_path


@pytest.mark.parametrize('index', range(12), ids=[f'DEV-{i:02}' for i in range(1, 13)])
def test_exact_case_artifacts_and_measured_references(archive, index):
    research, output, _ = archive
    manifest = d.materialize(research, output)
    record = manifest['cases'][index]
    status, media, body, vector, origin, parent = EXPECTED[index]
    assert record['case_id'] == f'DEV-{index + 1:02}'
    assert record['status'] == status
    assert record['content_type'] == media
    assert (output / record['body']['path']).read_bytes() == body
    assert record['body']['sha256'] == sha(body)
    assert record['origin'] == origin
    assert record['immediate_parent'] == parent
    assert record['oracle']['vector'] == [{'P': 'PASS', 'F': 'FAIL', 'N': 'NOT_APPLICABLE'}[v] for v in vector]
    assert record['oracle']['overall'] == ('CONSISTENT' if vector == 'PPP' else 'INCONSISTENT')
    assert not record['manually_reviewed']
    assert record['contract_sha256'] == SPEC['sources'][SPEC['contracts'][record['api']]]


def test_repeat_is_byte_identical_and_source_is_read_only(archive):
    research, output, _ = archive
    before = tree(research)
    first = d.materialize(research, output)
    second_output = output.with_name('second')
    second = d.materialize(research, second_output)
    assert first == second
    assert tree(output) == tree(second_output)
    assert tree(research) == before
    digest = sha((output / 'manifest.json').read_bytes())
    assert (output / 'manifest.sha256').read_text() == f'{digest}  manifest.json\n'
    assert first['manual_review'] == {'completed': 0, 'required': 12}
    assert first['release_status'] == 'CANDIDATE_PENDING_MANUAL_REVIEW'


def test_complete_manifest_references_exact_raw_artifacts_and_lineage(archive):
    research, output, _ = archive
    manifest = d.materialize(research, output)
    records = {r['case_id']: r for r in manifest['cases']}
    references = list(manifest['sources'].values())
    for r in records.values():
        references.extend([r['body'], r['response']])
        response = json.loads((output / r['response']['path']).read_bytes())
        assert response == {'status': r['status'], 'content_type': r['content_type'], 'body': r['body']}
        raw = (output / r['body']['path']).read_bytes()
        assert c.Response(r['status'], r['content_type'], raw).sha256 == r['response_sha256']
        assert r['oracle']['selected_response'] == (None if r['case_id'] == 'DEV-03' else str(r['status']))
        if r['immediate_parent']:
            parent = records[r['immediate_parent']]
            assert parent['root_family'] == r['root_family']
            assert r['parent_body_sha256'] == parent['body']['sha256']
            assert r['parent_response_sha256'] == parent['response_sha256']
            assert r['parent_status'] == parent['status']
            assert r['oracle_before'] == parent['oracle']
            if r['origin'] == 'SYNTHETIC_INCONSISTENT':
                assert r['oracle_before']['vector'] == ['PASS'] * 3
            edit = r['transformation']['body_edit']
            if edit:
                references.append(edit['replacement'])
                original = (output / parent['body']['path']).read_bytes()
                replacement = (output / edit['replacement']['path']).read_bytes()
                assert original[:edit['start']] + replacement + original[edit['end']:] == raw
        else:
            assert r['origin'] == 'NATURAL'
            assert r['oracle_before'] is None
            assert r['observation_source'] == SPEC['roots'][r['root_family']]['source_directory']
    for source, ref in manifest['sources'].items():
        assert (output / ref['path']).read_bytes() == (research / source).read_bytes()
    for ref in references:
        raw = (output / ref['path']).read_bytes()
        assert sha(raw) == ref['sha256']
        assert len(raw) == ref['size_bytes']
    assert set(tree(output)) == {r['path'] for r in references} | {'manifest.json', 'manifest.sha256'}
    assert records['DEV-02']['oracle_before']['vector'] == ['PASS', 'PASS', 'FAIL']
    assert dict(records['DEV-02']['transformation']['parameters'])['content_type'] == 'application/json'
    assert records['DEV-12']['oracle']['diagnostics'][0]['code'] == 'INVALID_JSON_REPRESENTATION'


def test_no_siblings_or_held_out_patterns_are_materialized(archive):
    research, output, _ = archive
    sibling = research / '04_case_studies/edx/pilot_responses/P03/response_body.bin'
    sibling.parent.mkdir()
    sibling.write_bytes(b'never read')
    manifest = d.materialize(research, output)
    assert len(list((output / 'cases').iterdir())) == 12
    assert manifest['counts']['api'] == {'edx': 6, 'htts': 6}
    assert manifest['counts']['origin'] == {
        'NATURAL': 3, 'SYNTHETIC_CONFORMANT': 2, 'SYNTHETIC_INCONSISTENT': 7}
    variants = {(r['fault_control_family'], r['transformation']['variant'])
                for r in manifest['cases'] if r['transformation']}
    assert variants == {('K01', 'explicit_parent'), ('K02', 'null'), ('F01', 'status_500'),
                        ('F02', 'undeclared_media'), ('F03', 'string'), ('F04', 'root'),
                        ('F06', 'remove_msg'), ('F09', 'broken_json')}
    assert all('P03' not in path for path in tree(output))
    assert manifest['held_out_variants_absent']


def test_oracle_receives_only_artifacts_not_inventory_metadata(archive, monkeypatch):
    research, output, _ = archive
    original = c.oracle.evaluate_response
    calls = []

    def measure(**kwargs):
        assert set(kwargs) == {'contract', 'operation_path', 'method', 'status', 'content_type', 'body'}
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(c.oracle, 'evaluate_response', measure)
    d.materialize(research, output)
    assert len(calls) == 21  # 12 resulting cases, 7 fault parents, 2 control contexts.


@pytest.mark.parametrize('field,value', [
    ('expected_vector', ['PASS', 'PASS', 'PASS']),
    ('expected_overall', 'CONSISTENT'),
    ('expected_body_sha256', '0' * 64),
])
@pytest.mark.parametrize('index', [0, 4], ids=['natural', 'single_fault'])
def test_specified_targets_do_not_override_measurement(archive, field, value, index):
    research, output, spec_path = archive
    spec = json.loads(spec_path.read_bytes())
    spec['cases'][index][field] = value
    spec_path.write_bytes(d._json(spec))
    with pytest.raises(d.DatasetRejected):
        d.materialize(research, output)
    rejection = json.loads((output / 'rejection.json').read_bytes())
    assert rejection['cases'][index]['oracle']['vector'] == ['PASS', 'PASS', 'FAIL']
    assert rejection['cases'][index]['oracle']['overall'] == 'INCONSISTENT'
    assert (output / 'cases/DEV-01/response_body.bin').read_bytes() == BODIES['EDX-P02']
    assert not (output / 'manifest.json').exists()


def test_rejected_mutation_retains_measured_candidate(archive, monkeypatch):
    research, output, _ = archive
    original = c.mutate

    def reject(*args, **kwargs):
        candidate = original(*args, **kwargs)
        raise c.ConstructionRejected('TEST_REJECTION', candidate=candidate,
                                     parent=candidate.parent, before=candidate.before)

    monkeypatch.setattr(c, 'mutate', reject)
    with pytest.raises(c.ConstructionRejected):
        d.materialize(research, output)
    rejection = json.loads((output / 'rejection.json').read_bytes())
    assert rejection['case_id'] == 'DEV-03'
    assert rejection['cases'][-1]['oracle']['vector'] == ['FAIL', 'NOT_APPLICABLE', 'NOT_APPLICABLE']
    assert rejection['oracle_before']['vector'] == ['PASS'] * 3
    assert (output / 'cases/DEV-03/response_body.bin').read_bytes() == b'{"code":0}'
    assert not (output / 'manifest.json').exists()


def test_oracle_error_stops_without_fabricating_result(archive, monkeypatch):
    research, output, _ = archive

    def fail(**kwargs):
        raise OracleExecutionError('test infrastructure failure')

    monkeypatch.setattr(c.oracle, 'evaluate_response', fail)
    with pytest.raises(OracleExecutionError):
        d.materialize(research, output)
    rejection = json.loads((output / 'rejection.json').read_bytes())
    assert rejection['cases'] == []
    assert rejection['case_id'] == 'DEV-01'
    assert (output / 'sources' / SPEC['roots']['EDX-P02']['source_directory'] / 'response_body.bin').exists()
    assert not (output / 'manifest.json').exists()


@pytest.mark.parametrize('change', ['changed', 'missing'])
def test_source_integrity_failure_is_held(archive, change):
    research, output, _ = archive
    source = research / SPEC['roots']['HTTS-H05']['source_directory'] / 'response_body.bin'
    if change == 'changed':
        source.write_bytes(b'{}')
    else:
        source.unlink()
    with pytest.raises((d.DatasetRejected, FileNotFoundError)):
        d.materialize(research, output)
    assert (output / 'rejection.json').exists()
    assert not (output / 'manifest.json').exists()


def test_existing_output_and_research_destination_are_protected(archive):
    research, output, _ = archive
    d.materialize(research, output)
    before = tree(output)
    with pytest.raises(FileExistsError):
        d.materialize(research, output)
    assert tree(output) == before
    with pytest.raises(ValueError, match='read-only'):
        d.materialize(research, research / 'generated')
    assert not (research / 'generated').exists()


@pytest.mark.parametrize('problem', ['missing_case', 'sibling_family', 'held_out', 'wrong_count'])
def test_inventory_guard_rejects_scope_drift(archive, problem):
    research, output, _ = archive
    records = d.materialize(research, output)['cases']
    if problem == 'missing_case':
        records.pop()
    elif problem == 'sibling_family':
        records[0]['root_family'] = 'EDX-P03'
    elif problem == 'held_out':
        records[5]['transformation']['variant'] = 'nested'
    else:
        records[0]['origin'] = 'SYNTHETIC_CONFORMANT'
    with pytest.raises(d.DatasetRejected):
        d._verify_inventory(records)


def test_version_record_binds_implementation_and_qualification():
    versions = d._versions()
    assert len(versions['implementation_commit']) == 40
    assert len(versions['oracle_commit']) == 40
    assert versions['dependencies']['openapi-schema-validator'] == '0.9.0'
    assert versions['dependencies']['jsonschema'] == '4.26.0'
    for path, expected in versions['files'].items():
        assert sha((d.REPOSITORY / path).read_bytes()) == expected
    assert 'tests/test_oracle_qualification.py' in versions['files']
    assert 'src/rest_api_checker/development_dataset_v1.json' in versions['files']
