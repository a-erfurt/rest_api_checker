"""Read-only result presentation, using only fabricated stored records."""
import base64
from copy import deepcopy
import io
import json
from types import SimpleNamespace

import pytest
from rich.console import Console

from rest_api_checker import live_demo_inspection, terminal
from rest_api_checker.experiment import orchestration
from rest_api_checker.persistence import inspection


@pytest.fixture
def stored(monkeypatch):
    request = {'format': 'json', 'messages': [
        {'role': 'system', 'content': 'FABRICATED immutable prompt'},
        {'role': 'user', 'content': 'Exact previously stored evidence\n[red]literal'}]}
    envelope = b'\x00\xffexact provider envelope'
    tables = {
        'experiment_runs': {7: dict(id=7, experiment_id=8, dataset_case_id=9, model_id=10,
            prompt_id=11, request_file_id=12, repetition=1, seed=101, result='valid')},
        'dataset_cases': {9: dict(case_code='TEST-CASE', reference_id=13)},
        'reference_results': {13: dict(c1='PASS', c2='PASS', c3='FAIL')},
        'models': {10: dict(name='FABRICATED model')},
        'prompts': {11: dict(name='P2')},
        'predictions': {14: dict(run_id=7, c1='PASS', c2='PASS', c3='FAIL',
            c1_reason='stored reason', c2_reason='[red]literal', c3_reason='stored reason')},
        'run_attempts': {15: dict(id=15, run_id=7, attempt=1, result='valid', duration_ms=1234,
            response_file_id=16, error_kind=None, error_message=None)},
    }
    files = {12: json.dumps(request).encode(), 16: envelope}
    repo = SimpleNamespace(
        _row=lambda table, identifier: deepcopy(tables[table][identifier]),
        file=lambda identifier: files[identifier])
    monkeypatch.setattr(inspection, 'rows', lambda repository, table, **filters: [
        deepcopy(row) for row in tables[table].values()
        if all(row[key] == value for key, value in filters.items())])
    def forbidden(*args, **kwargs):
        pytest.fail('Result inspection must not prepare a request or execute a model')
    monkeypatch.setattr(orchestration, 'prepare', forbidden)
    monkeypatch.setattr(orchestration, 'execute_attempt', forbidden)
    return repo, tables, files, request, envelope


def test_verbose_reads_original_request_and_exact_provider_bytes(stored):
    repo, _, _, request, envelope = stored
    detail = live_demo_inspection.run_detail(repo, 7, raw=True)
    assert detail['raw']['request'] == request
    assert detail['raw']['evidence'] == request['messages'][1]['content']
    assert base64.b64decode(detail['raw']['provider_envelopes'][0]['base64']) == envelope
    assert detail['correctness'] == dict(c1=True, c2=True, c3=True)


def test_nonverbose_preserves_existing_projection_without_reading_files(stored):
    repo, *_ = stored
    repo.file = lambda identifier: pytest.fail('Nonverbose result does not need request bytes')
    assert live_demo_inspection.run_detail(repo, 7) == inspection.run_detail(repo, 7)


def test_unattempted_run_has_no_invented_request_or_prediction(stored):
    repo, tables, *_ = stored
    tables['experiment_runs'][7].update(request_file_id=None, result=None)
    tables['predictions'].clear()
    tables['run_attempts'].clear()
    detail = live_demo_inspection.run_detail(repo, 7, raw=True)
    assert detail['raw'] == dict(request=None, evidence=None, provider_envelopes=[])
    assert detail['prediction'] is None
    assert set(detail['correctness'].values()) == {None}


@pytest.mark.parametrize('result, prediction, correct, parser', [
    ('valid', True, True, 'VALID_OUTPUT'),
    ('valid', True, False, 'VALID_OUTPUT'),
    ('parser_failure', False, None, 'PARSER_FAILURE'),
    ('technical_failure', False, None, 'N/A (no final parsed output)'),
    (None, False, None, 'N/A (no final parsed output)'),
])
def test_human_result_shows_ids_parser_and_vector_without_false_failure(stored, result, prediction, correct, parser):
    repo, tables, *_ = stored
    tables['experiment_runs'][7]['result'] = result
    if not prediction:
        tables['predictions'].clear()
    elif not correct:
        tables['predictions'][14]['c3'] = 'PASS'
    stream = io.StringIO()
    console = Console(file=stream, width=160, color_system=None, markup=False, highlight=False)
    terminal.inspection(console, live_demo_inspection.run_detail(repo, 7))
    text = stream.getvalue()
    assert 'Parser: '+parser in text
    assert 'Vector correct? '+('yes' if correct else 'no' if correct is False else 'N/A (no semantic verdict)') in text
    assert 'Attempt ID' in text and 'Raw response file ID' in text
    assert '15' in text and '16' in text and '1234' in text
    assert 'provider_envelopes' not in text
    if not prediction:
        assert 'incorrect' not in text
