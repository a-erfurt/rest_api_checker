"""Root result output boundaries over fabricated runs; no SQL or model access."""
from copy import deepcopy
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from rest_api_checker import interactive_app as app, live_result, operator, terminal
from rest_api_checker.persistence import repository


INTERNAL = ('9835101', '9835102', '9835103', '9845101', '9855101', '9875101',
            '/private/internal/recovery-evidence', 'INTERNAL-DIAGNOSTIC-MESSAGE')


def answer(*values):
    choices = iter(values)
    return lambda _: next(choices)


def detail(repetition):
    reference = dict(c1='PASS', c2='PASS', c3='FAIL')
    return dict(case='V2-EDX-TEST', model='gemma3:27b', prompt='P2',
        run=dict(id=9835100+repetition, experiment_id=9845101, repetition=repetition,
                 result='valid', seed=101), reference=reference,
        prediction=dict(reference, c1_reason='Stored reason.', c2_reason='Stored reason.', c3_reason='Stored reason.'),
        attempts=[dict(id=9855101, attempt=1, response_file_id=9875101, duration_ms=1234)],
        spool='/private/internal/recovery-evidence')


@pytest.fixture
def setup(monkeypatch):
    console = terminal.console(plain=True, file=StringIO())
    console.width = 96
    config = SimpleNamespace(host='127.0.0.1', port=8000, database='FABRICATED')
    connection = Mock()
    repo = object()
    monkeypatch.setattr(operator, 'cli_args', lambda *args, **kwargs: ['demo', 'run'])
    monkeypatch.setattr(app, 'credentials', lambda _: {})
    monkeypatch.setattr(app, 'connect', lambda *args: connection)
    monkeypatch.setattr(repository, 'Repository', lambda _: repo)
    return config, console, connection


def result_value(records, *, status='COMPLETED', displayed=None):
    return dict(status=status, results=records, displayed_run_ids=displayed or [],
                message='INTERNAL-DIAGNOSTIC-MESSAGE', experiment_id=9845101,
                run_ids=[r['run']['id'] for r in records] or [9835101],
                spool='/private/internal/recovery-evidence')


def assert_readonly_cleanup(connection):
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()
    connection.commit.assert_not_called()
    connection.execute.assert_not_called()


def assert_clean_default(text):
    for forbidden in (*INTERNAL, 'Run ID', 'Attempt ID', 'Recovery evidence', 'live demo',
                      'live/ad-hoc', 'live-ad-hoc', 'live-adhoc'):
        assert forbidden.casefold() not in text.casefold()


@pytest.mark.parametrize('already_displayed', [False, True])
def test_completed_repetitions_render_only_one_compact_summary(setup, monkeypatch, already_displayed):
    config, console, connection = setup
    records = [detail(1), detail(2), detail(3)]
    value = result_value(records, displayed=[r['run']['id'] for r in records] if already_displayed else [])
    before = deepcopy(value)
    monkeypatch.setattr(app.live_demo_cli, 'run', lambda *args, **kwargs: (value, 0))
    individual = Mock(wraps=live_result.show)
    repeated = Mock(wraps=live_result.repetitions)
    monkeypatch.setattr(app.live_result, 'show', individual)
    monkeypatch.setattr(app.live_result, 'repetitions', repeated)
    assert app.run_check(config, console, answer('6')) == 'main'
    text = console.file.getvalue()
    individual.assert_not_called()
    repeated.assert_called_once_with(console, records)
    assert text.count('Repetitions · Gemma 3 27B') == 1
    assert text.count('Usable output 3/3') == 1
    assert 'Run completed' not in text
    assert_clean_default(text)
    assert value == before
    assert_readonly_cleanup(connection)


def test_single_result_already_shown_by_runner_is_not_printed_twice(setup, monkeypatch):
    config, console, connection = setup
    record = detail(1)
    value = result_value([record], displayed=[record['run']['id']])
    def completed(*args, **kwargs):
        live_result.show(console, record)
        return value, 0
    monkeypatch.setattr(app.live_demo_cli, 'run', completed)
    assert app.run_check(config, console, answer('6')) == 'main'
    text = console.file.getvalue()
    assert text.count('✓ Run completed') == 1
    assert 'Repetitions' not in text
    assert_clean_default(text)
    assert_readonly_cleanup(connection)


@pytest.mark.parametrize('status', ['BLOCKED', 'INTERRUPTED'])
def test_no_result_default_hides_internal_provenance_and_diagnostic_message(setup, monkeypatch, status):
    config, console, connection = setup
    value = result_value([], status=status)
    # Internal legacy wording must not enter the normal result menu through diagnostics.
    value['message'] += ' live demo / Live/ad-hoc internal context'
    monkeypatch.setattr(app.live_demo_cli, 'run', lambda *args, **kwargs: (value, 1))
    assert app.run_check(config, console, answer('2')) == 'main'
    text = console.file.getvalue()
    assert f'Run {status.lower()}. No result is available.' in text
    assert 'View details' in text and 'Main menu' in text
    assert_clean_default(text)
    assert_readonly_cleanup(connection)


def test_no_result_explicit_details_expose_provenance(setup, monkeypatch):
    config, console, connection = setup
    value = result_value([], status='BLOCKED')
    monkeypatch.setattr(app.live_demo_cli, 'run', lambda *args, **kwargs: (value, 1))
    assert app.run_check(config, console, answer('1')) == 'main'
    text = console.file.getvalue()
    for expected in ('INTERNAL-DIAGNOSTIC-MESSAGE', '9845101', '9835101',
                     '/private/internal/recovery-evidence', 'Run context'):
        assert expected in text
    assert 'live demo' not in text.casefold() and 'live/ad-hoc' not in text.casefold()
    assert_readonly_cleanup(connection)


def test_completed_explicit_details_receive_hidden_recovery_path(setup, monkeypatch):
    config, console, connection = setup
    record = detail(1)
    value = result_value([record])
    monkeypatch.setattr(app.live_demo_cli, 'run', lambda *args, **kwargs: (value, 0))
    monkeypatch.setattr(app, 'stored_detail', lambda *args: record)
    assert app.run_check(config, console, answer('1', '6')) == 'main'
    text = console.file.getvalue()
    assert 'Run ID' in text and '9835101' in text
    assert 'Recovery directory' in text and '/private/internal/recovery-evidence' in text
    assert 'Category explanations' in text
    assert 'INTERNAL-DIAGNOSTIC-MESSAGE' not in text
    assert_readonly_cleanup(connection)
