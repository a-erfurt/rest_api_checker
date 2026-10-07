"""Read-only artifact/menu projections over fabricated persisted associations."""
from copy import deepcopy
from hashlib import sha256
from io import StringIO
import json

import pytest

from rest_api_checker import interactive_evidence as evidence, terminal
from rest_api_checker.web.queries import DataUnavailable, NotFound, WebQueries


class Query:
    _file = WebQueries._file

    def __init__(self, *, vector=('PASS', 'PASS', 'FAIL'), extra=None):
        self.calls = []
        self.files = {}
        self.source = dict(description='Stored case source', **(extra or {}))
        self.reference = dict(id=30, case_id=10, c1=vector[0], c2=vector[1], c3=vector[2],
                              source_file_id=4, source_pointer='/reference')
        self.case = dict(id=10, native_case_id='SOURCE-CASE', source_file_id=3, source_pointer='/cases/0',
            origin='natural_observation', description=None, service='htts', method='post',
            path='/resistance/validation/file', contract_file_id=2, status_code=200,
            content_type='application/json', body_file_id=1)
        self.add(1, b'{"actual": true}', 'archived/body.json')
        self.add(2, b'{"openapi": "3.0.4"}', 'archived/contract.json')
        self.add(3, json.dumps({'cases': [self.source]}).encode(), 'archived/source.json')
        self.add(4, b'{"reference": {"diagnostics": [], "notes": "Stored explanation"}}', 'archived/reference.json')

    def add(self, file_id, raw, name):
        self.files[file_id] = dict(id=file_id, content=raw, sha256=sha256(raw).hexdigest(),
                                   size_bytes=len(raw), name=name)

    def _rows(self, sql, *params):
        assert sql.lstrip().startswith('SELECT ')
        self.calls.append((sql, params))
        assert 'FROM dbo.files WHERE sha256=?' in sql
        return [dict(id=row['id']) for row in self.files.values() if row['sha256'] == params[0]]

    def _one(self, sql, *params):
        assert sql.lstrip().startswith('SELECT ')
        self.calls.append((sql, params))
        if 'FROM dbo.files WHERE id=?' in sql:
            if params[0] not in self.files:
                raise NotFound('No stored file')
            return dict(self.files[params[0]])
        if 'FROM dbo.dataset_cases WHERE id=?' in sql:
            assert params == (20,)
            return dict(case_id=10, reference_id=30, case_code='V2-RES-TEST')
        if 'FROM dbo.test_cases tc' in sql:
            assert params == (10,)
            return dict(self.case)
        if 'FROM dbo.reference_results WHERE id=? AND case_id=?' in sql:
            assert params == (30, 10)
            return dict(self.reference)
        raise AssertionError(sql)


def output():
    stream = StringIO()
    console = terminal.console(plain=True, file=stream)
    console.width = 100
    return console, stream


def answers(*items):
    iterator = iter(items)
    return lambda _: next(iterator)


def test_only_real_associations_are_listed_and_bytes_stay_identical():
    query = Query(extra={'input_filename': '/made/up/file.txt', 'request_file': '/made/up/request.bin'})
    before = deepcopy(query.files)
    view, artifacts = evidence.load_case(query, {'id': 20})
    assert view['case_code'] == 'V2-RES-TEST'
    assert [a['label'] for a in artifacts] == ['Observed response body', 'OpenAPI contract',
                                              'Reference / explanation', 'Case provenance']
    assert artifacts[0]['content'] == '{"actual": true}'
    assert json.loads(artifacts[2]['content']) == {'diagnostics': [], 'notes': 'Stored explanation'}
    assert query.files == before
    assert all(sql.lstrip().startswith('SELECT ') for sql, _ in query.calls)


@pytest.mark.parametrize(('vector', 'overall'), [
    (('PASS', 'PASS', 'PASS'), '✓ CONFORMING'),
    (('PASS', 'PASS', 'FAIL'), '✗ INCONSISTENT'),
    (('FAIL', 'NOT_APPLICABLE', 'NOT_APPLICABLE'), '✗ INCONSISTENT'),
])
def test_case_panel_and_file_menu_hide_internal_locations(vector, overall):
    query = Query(vector=vector)
    console, stream = output()
    evidence.show_case_details(query, {'id': 20}, console, answers('q'))
    value = stream.getvalue()
    for expected in ('Case details', 'C1 Status', 'C2 Media Type', 'C3 Body Schema', overall,
                     'Files / evidence', 'Observed response body', 'OpenAPI contract', 'Resistance'):
        assert expected in value
    assert 'archived/' not in value and 'stored as htts' not in value and 'Source pointer' not in value
    assert 'Input validity' not in value  # A conforming response does not label the submitted input.


def test_file_view_and_explicit_details_are_available():
    query = Query()
    console, stream = output()
    evidence.show_case_details(query, {'id': 20}, console, answers('1', 'd 2', 'q'))
    value = stream.getvalue()
    assert '"actual": true' in value
    assert 'Archive name' in value and 'archived/contract.json' in value
    assert 'SHA-256' in value and query.files[2]['sha256'] in value
    assert 'archived/body.json' not in value


def test_final_input_and_request_require_explicit_hash_bound_archived_artifacts():
    raw = b'original input\n'
    digest = sha256(raw).hexdigest()
    candidate = dict(input_evidence_file='evidence/input.bin', input_sha256=digest,
                     request_evidence_file='evidence/request.bin', request_sha256=digest)
    query = Query(extra={'original_candidate': candidate})
    query.add(5, raw, 'candidate/evidence/input.bin')
    _, artifacts = evidence.load_case(query, {'case_id': 10, 'reference_id': 30, 'case_code': 'V2-RES-TEST'})
    assert [a['label'] for a in artifacts][2:4] == ['Original input file', 'Original API request body']
    assert artifacts[2]['content'] == raw.decode()
    del query.files[5]
    _, artifacts = evidence.load_case(query, {'id': 20})
    assert 'Original input file' not in [a['label'] for a in artifacts]


def test_capture_input_association_integrity_is_checked():
    raw = b'captured input'
    query = Query(extra=dict(format='service-capture-v1', source_input=dict(file_id=5, sha256=sha256(raw).hexdigest())))
    query.add(5, raw, 'captured-input.bin')
    _, artifacts = evidence.load_case(query, {'id': 20})
    assert any(a['label'] == 'Original input file' for a in artifacts)
    query.add(5, b'changed bytes', 'captured-input.bin')
    with pytest.raises(DataUnavailable, match='associated artifact failed'):
        evidence.load_case(query, {'id': 20})


def test_archived_corruption_is_not_shown_or_silently_ignored():
    query = Query()
    query.files[1]['content'] = b'corrupted bytes'
    with pytest.raises(DataUnavailable, match='integrity check'):
        evidence.load_case(query, {'id': 20})


def test_non_utf8_evidence_preserves_exact_bytes_as_base64():
    query = Query()
    query.add(1, b'\xff\x00\xfe', 'binary.bin')
    _, artifacts = evidence.load_case(query, {'id': 20})
    assert artifacts[0]['content'] == 'Non-UTF-8 bytes; exact base64:\n/wD+'


def test_run_case_files_list_raw_response_only_when_stored():
    query = Query()
    query.add(5, b'{"message":{"content":"unusable output"}}', 'raw-provider.bin')
    detail = dict(run=dict(case_id=10, reference_id=30, case='V2-RES-TEST'),
                  attempts=[dict(attempt=1, response_file_id=5), dict(attempt=2, response_file_id=None)])
    console, stream = output()
    evidence.show_run_case_files(query, detail, console, answers('q'))
    assert 'Raw model response · attempt 1' in stream.getvalue()
    assert 'Raw model response · attempt 2' not in stream.getvalue()


def test_readonly_query_surface_can_be_used_through_repository_connection(monkeypatch):
    query = Query()
    connection = object()
    class Repository:
        cn = connection
    monkeypatch.setattr(evidence, 'WebQueries', lambda cn: query if cn is connection else None)
    _, artifacts = evidence.load_case(Repository(), {'id': 20})
    assert artifacts[0]['label'] == 'Observed response body'



def test_explicit_archive_details_preserve_long_names_and_full_hash_at_width_80():
    query = Query()
    name = 'candidate/evidence/' + '0123456789abcdef' * 4 + '.bin'
    query.files[1]['name'] = name
    console, stream = output()
    console.width = 80
    evidence.show_case_details(query, {'id': 20}, console, answers('d 1', 'q'))
    text = stream.getvalue()
    # Strip only layout whitespace and borders; the archive identity stays complete.
    unwrapped = ''.join(text.split()).replace('│', '')
    assert name in unwrapped
    assert query.files[1]['sha256'] in unwrapped
    assert '…' not in text
    assert all(len(line) <= 80 for line in text.splitlines())
