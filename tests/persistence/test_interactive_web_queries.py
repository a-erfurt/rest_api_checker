"""Interactive query contracts over fabricated SELECT-only collaborators."""
from hashlib import sha256
import json

import pytest

from rest_api_checker.web.queries import DataUnavailable, INTERACTIVE_CONTEXT, WebQueries


class RecordedQueries(WebQueries):
    def __init__(self, rows):
        super().__init__(None)
        self.responses = iter(rows)
        self.statements = []

    def _rows(self, statement, *parameters):
        assert statement.lstrip().upper().startswith('SELECT ')
        self.statements.append((statement, parameters))
        return next(self.responses)


@pytest.mark.parametrize('rows', [[], [dict(id=20440, case='V2-EDX-002', is_interactive=True)]])
def test_latest_interactive_is_bounded_select_with_safe_pending_order(rows):
    query = RecordedQueries([rows])
    assert query.latest_interactive_run() == (rows[0] if rows else None)
    statement, parameters = query.statements[0]
    assert 'SELECT TOP (1)' in statement and parameters == ()
    assert 'WHERE '+INTERACTIVE_CONTEXT in statement
    assert 'e.id<>10003' in statement and 'e.dataset_id<>3' in statement
    assert "e.name LIKE 'LIVE-ADHOC %'" in statement and "e.name LIKE 'LIVE-DEMO %'" in statement
    order = statement.split(' ORDER BY\n')[-1]
    assert 'r.result IS NOT NULL OR r.started_at IS NOT NULL' in order
    assert 'last_attempt.attempt IS NOT NULL THEN 0 ELSE 1 END,r.id DESC' in order


@pytest.mark.parametrize('interactive', [True, False])
def test_adjacent_scope_and_endpoints_are_parameterized(interactive):
    query = RecordedQueries([[dict(id=50, experiment_id=10003, is_interactive=interactive)],
                             [dict(id=49)], []])
    assert query.adjacent_runs(50) == dict(previous=dict(id=49), next=None)
    previous, following = query.statements[1:]
    if interactive:
        assert 'WHERE '+INTERACTIVE_CONTEXT in previous[0]
        assert previous[1] == following[1] == (50,)
    else:
        assert 'WHERE r.experiment_id=?' in previous[0]
        assert previous[1] == following[1] == (10003, 50)
    assert 'r.id<? ORDER BY r.id DESC' in previous[0]
    assert 'r.id>? ORDER BY r.id ASC' in following[0]


def test_detail_reuses_bound_cli_case_evidence_and_exact_provider_bytes(monkeypatch):
    from rest_api_checker import interactive_evidence
    run = dict(id=20440, experiment_id=9000, case_id=22, reference_id=44,
               request_file_id=11, model='gemma3:27b')
    reference = dict(c1='PASS', c2='PASS', c3='FAIL')
    prediction = dict(c1='PASS', c2='PASS', c3='PASS')
    attempt = dict(id=30, attempt=1, response_file_id=12, diagnostics_file_id=None)
    view = dict(service='edx', method='post', path='/stream', reference=reference)
    raw = ' {"message": {"content": " exact \\ncontent "}}\n'
    files = [dict(label='Observed response body', content='{}'), dict(label='OpenAPI contract', content='{}')]
    def load_case(query, selected):
        assert selected is run and selected['reference_id'] == 44
        return view, files
    def artifact(query, identifier, label):
        assert identifier == 12
        return dict(label=label, content=raw)
    monkeypatch.setattr(interactive_evidence, 'load_case', load_case)
    monkeypatch.setattr(interactive_evidence, '_artifact', artifact)
    query = RecordedQueries([[run], [reference], [prediction], [attempt]])
    monkeypatch.setattr(query, '_runtime_evidence', lambda *args: dict(parser_diagnostics=None))
    detail = query.run_detail(20440)
    assert detail['case_details'] is view
    assert detail['reference'] is reference and detail['prediction'] is prediction
    assert detail['raw_model_response'] == raw
    assert detail['files'][-1] == dict(label='Raw model response', content=raw)
    assert not any('model request' in file['label'] for file in detail['files'])
    assert detail['evidence'] == []


def runtime_query(*, setup=None, provenance=None, provenance_hash=None, started=True):
    provenance = provenance or dict(model='gemma3:27b', model_digest='b'*64)
    raw = json.dumps(provenance).encode()
    documents = {1: json.dumps(setup or dict(runtime={'ollama': {'version': '0.40.0'}},
                                            models=[dict(name='gemma3:27b', digest='a'*64)])).encode(),
                 2: json.dumps(dict(parser={'status': 'INVALID_OUTPUT', 'code': 'CATEGORY_FIELDS',
                                            'path': '$.c1', 'unexpected_secret': 'not exposed'},
                                    transport={'request_provenance_file_id': 3,
                                               'request_provenance_sha256': provenance_hash or sha256(raw).hexdigest()},
                                    recovery_path='/private/fabricated/secret')).encode(), 3: raw}
    query = RecordedQueries([[dict(setup_file_id=1)]])
    query._file = documents.__getitem__
    attempt = dict(diagnostics_file_id=2, started_at='2026-10-07' if started else None)
    return query, dict(model='gemma3:27b', experiment_id=9000), attempt


def test_runtime_uses_hash_bound_actual_provenance_and_allowlisted_diagnostics():
    query, run, attempt = runtime_query()
    result = query._runtime_evidence(run, [attempt])
    assert result == dict(model_digest='b'*64, ollama_version='0.40.0',
                          parser_diagnostics=dict(status='INVALID_OUTPUT', code='CATEGORY_FIELDS', path='$.c1'))
    assert 'secret' not in json.dumps(result) and '/private' not in json.dumps(result)


def test_prepared_but_never_dispatched_attempt_does_not_claim_model_used():
    query, run, attempt = runtime_query(started=False)
    assert query._runtime_evidence(run, [attempt])['model_digest'] is None


def test_runtime_sidecar_mismatch_fails_closed():
    query, run, attempt = runtime_query(provenance_hash='0'*64)
    with pytest.raises(DataUnavailable, match='integrity check'):
        query._runtime_evidence(run, [attempt])


def test_absent_optional_runtime_setup_stays_unavailable():
    query = RecordedQueries([[dict(setup_file_id=None)]])
    assert query._runtime_evidence(dict(experiment_id=1, model='fixture'), []) == dict(
        model_digest=None, ollama_version=None, parser_diagnostics=None)
