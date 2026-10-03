"""Presentation-only checks: render existing events without scientific execution."""
from copy import deepcopy
from hashlib import sha256
import io
import json

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress

from rest_api_checker import batch_terminal as view, cli, evaluation_batch_v2 as v2, terminal


@pytest.fixture(autouse=True)
def terminal_capabilities(monkeypatch):
    # TERM=dumb forces Rich to 80 columns without styles even with force_terminal.
    monkeypatch.setenv('TERM', 'xterm-256color')


@pytest.mark.parametrize('simulated', [False, True])
@pytest.mark.parametrize('width', [80, 100, 120, 200])
def test_tty_components_and_readable_fields(monkeypatch, simulated, width):
    monkeypatch.delenv('NO_COLOR', raising=False)
    plan = v2.demo_plan()
    if not simulated:
        plan.summary['mode'] = 'Evaluation v2 Main'
    stream = io.StringIO()
    console = Console(file=stream, force_terminal=True, color_system=None, width=width)
    assert console.width == width
    monkeypatch.setattr(view.time, 'monotonic', lambda: 100)
    display = view.Display(console, plan.summary)
    state = dict(planned=27, completed=9, counts=dict(valid=8, parser_failure=1, technical_failure=0))
    display.event(dict(event='progress', state=state))
    display.event(dict(event='current', current=plan.labels[10]))
    before = deepcopy(state), deepcopy(plan.summary), deepcopy(plan.labels[10])
    monkeypatch.setattr(view.time, 'monotonic', lambda: 160)
    constrained, = display.__rich_console__(console, console.options)
    group = constrained.renderable
    assert any(isinstance(r, Progress) for r in group.renderables)
    assert any(isinstance(c, BarColumn) for c in display.progress.columns)
    panels = [r for r in group.renderables if isinstance(r, Panel)]
    assert [p.title.plain for p in panels] == ['▶ Current execution', 'Result counters']
    assert all(p.padding == (0, 2) for p in panels)
    assert display.progress.tasks[0].completed == 9
    console.print(display)
    text = stream.getvalue()
    for expected in ('Overall', '9 / 27', '33.3%', 'Elapsed 00:01:00', 'ETA (estimate) 00:02:00',
                     'Current execution', 'Case', 'SIM-002', 'API', 'SYNTHETIC', 'qwen3.6:27b',
                     'Repetition', '1 / 3', 'Seed', '101', 'State', 'Running',
                     'Result counters', 'Parser-valid', 'Parser failures', 'Technical failures', 'Remaining', '18'):
        assert expected in text
    bar_lines = [line for line in text.splitlines() if '█' in line or '░' in line]
    assert len(bar_lines) == 1 and '█' in bar_lines[0] and '░' in bar_lines[0]
    assert '9 / 27' in bar_lines[0] and '33.3%' in bar_lines[0]
    assert max(map(len, text.splitlines())) <= min(width, 120)
    assert not any(a == b == '' for a, b in zip(text.splitlines(), text.splitlines()[1:]))
    if simulated:
        assert 'SIMULATED' in text
        assert 'NO MODEL CALLS' not in text  # Warning belongs to plan and final summary only.
    assert (state, plan.summary, plan.labels[10]) == before


@pytest.mark.parametrize('mode', ['plain', 'redirected', 'no_color'])
def test_plain_redirected_no_color_have_no_panels_or_ansi(monkeypatch, mode):
    monkeypatch.delenv('NO_COLOR', raising=False)
    if mode == 'no_color':
        monkeypatch.setenv('NO_COLOR', '1')
    stream = io.StringIO()
    console = terminal.console(file=stream, plain=mode == 'plain')
    plan = v2.demo_plan()
    view.plan(console, plan.summary)
    with view.Display(console, plan.summary) as display:
        assert not display.live_enabled
        result = v2.simulate(plan, notify=display.event, delay=0)
    view.summary(console, result)
    text = stream.getvalue()
    assert '\x1b' not in text
    assert not any(c in text for c in '╭╮╰╯│─━█░▶✓✕◷')
    assert '27/27 complete (100.0%)' in text and 'ETA (estimate)' in text
    assert all(s in text for s in ('Simulated steps', 'Real executions', 'Model calls', 'Prediction writes'))
    assert 'Executed now' not in text and 'Completed total' not in text


@pytest.mark.parametrize('simulated', [False, True])
def test_plan_and_summary_panels_share_components(monkeypatch, simulated):
    monkeypatch.delenv('NO_COLOR', raising=False)
    console = Console(file=io.StringIO(), force_terminal=True, width=100)
    plan = v2.demo_plan()
    result = v2.simulate(plan, notify=lambda e: None, delay=0)
    if not simulated:
        plan.summary['mode'] = 'Evaluation v2 Main'
        result['simulated'] = False
    objects = []
    monkeypatch.setattr(console, 'print', lambda *items, **kwargs: objects.extend(items))
    view.plan(console, plan.summary)
    view.summary(console, result)
    assert [p.title.plain for p in objects if isinstance(p, Panel)] == ['Evaluation / execution plan', 'Final summary']


def test_json_receipt_is_unchanged_by_presentation(monkeypatch, capsys):
    result = v2.simulate(v2.demo_plan(), notify=lambda e: None, delay=0)
    before = deepcopy(result)
    monkeypatch.setattr(v2, 'simulate', lambda *a, **k: result)
    def forbidden(*a, **k): pytest.fail('JSON mode must not render human panels or access scientific state')
    for name in ('plan', 'summary'):
        monkeypatch.setattr(view, name, forbidden)
    for name in ('connect', 'read_settings', 'Repository'):
        monkeypatch.setattr(cli, name, forbidden)
    monkeypatch.setattr(v2, 'OllamaClient', forbidden)
    monkeypatch.setattr(v2, 'execute', forbidden)
    assert cli.main(['experiment', 'demo-batch', '--delay', '0', '--json']) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == before == result
    assert captured.err == '' and '\x1b' not in captured.out
    assert result['model_calls'] == result['prediction_writes'] == 0


def test_resumed_progress_uses_overall_completion_but_session_eta(monkeypatch):
    monkeypatch.delenv('NO_COLOR', raising=False)
    console = Console(file=io.StringIO(), force_terminal=True, width=120)
    plan = v2.demo_plan()
    plan.summary['previously_complete'] = 9
    monkeypatch.setattr(view.time, 'monotonic', lambda: 100)
    display = view.Display(console, plan.summary)
    display.event(dict(event='progress', state=dict(completed=18, counts={})))
    monkeypatch.setattr(view.time, 'monotonic', lambda: 160)
    console.print(display)
    text = console.file.getvalue()
    assert '18 / 27' in text and '66.7%' in text and 'ETA (estimate) 00:01:00' in text


@pytest.mark.parametrize('width', [80, 100, 120, 200])
def test_compact_demo_plan_and_final_summary(monkeypatch, width):
    monkeypatch.delenv('NO_COLOR', raising=False)
    stream = io.StringIO()
    console = Console(file=stream, force_terminal=True, color_system=None, width=width)
    plan = v2.demo_plan()
    before = deepcopy(plan.summary)
    view.plan(console, plan.summary)
    text = stream.getvalue()
    assert len(text.splitlines()) <= 17
    assert max(map(len, text.splitlines())) <= min(width, 120)
    for field in ('Dataset', 'Cases', 'Models', 'Repetitions', 'Seeds', 'Planned executions',
                  'Output mode', 'Runtime', 'Prompt', 'Token limit'):
        assert field in text
    for noise in ('Database', 'Experiment', 'None', 'SHA-256', 'Problematic', 'NOT QUALIFIED'):
        assert noise not in text
    assert 'qwen3.6:27b · gemma3:27b · mistral-small3.2:24b' in text
    assert text.count('NO MODEL CALLS') == text.count('NO PREDICTION WRITES') == 1
    stream.seek(0); stream.truncate()
    result = v2.simulate(plan, notify=lambda e: None, delay=0)
    result_before = deepcopy(result)
    view.summary(console, result)
    text = stream.getvalue()
    assert len(text.splitlines()) <= 10
    for field in ('Status', 'Simulated steps', 'Parser-valid', 'Parser failures', 'Technical failures',
                  'Real model calls', 'Prediction writes', 'Elapsed', 'Average simulated step'):
        assert field in text
    assert not any(field in text for field in ('Dataset', 'Models', 'Repetitions', 'SHA-256', 'Executed now', 'Completed total'))
    assert text.count('NO MODEL CALLS') == 1 and text.count('NO PREDICTION WRITES') == 1
    assert max(map(len, text.splitlines())) <= min(width, 120)
    assert plan.summary == before and result == result_before


def test_real_plan_keeps_meaningful_identity_and_continuation_fields(monkeypatch):
    monkeypatch.delenv('NO_COLOR', raising=False)
    console = Console(file=io.StringIO(), force_terminal=True, color_system=None, width=120)
    value = v2.demo_plan().summary
    value.update(mode='Evaluation v2 Main', database='TEST DATABASE', experiment_id=42,
        previously_complete=9, problematic=1, problematic_run_ids=[99], setup_sha256='a'*64, preflight='TEST PASS')
    value['dataset']['id'] = 7
    for model in value['models']:
        model['digest'] = 'b'*64
    before = deepcopy(value)
    view.plan(console, value)
    text = console.file.getvalue()
    for field in ('ID 7', 'Database', 'TEST DATABASE', 'Experiment', '42', 'Already complete', 'Remaining',
                  'Problematic', 'To execute', 'Problematic run IDs: 99', 'P2 SHA-256', 'Setup SHA-256',
                  'aaaaaaaaaaaaaaaa', 'bbbbbbbbbbbbbbbb', 'TEST PASS'):
        assert field in text
    assert value == before


def test_failure_styles_distinct_and_presentation_does_not_mutate_counts(monkeypatch):
    monkeypatch.delenv('NO_COLOR', raising=False)
    assert view.failure_text(1).style == 'bold yellow'
    assert view.failure_text(1, technical=True).style == 'bold red'
    assert view.failure_text(0, technical=True).style == 'dim'
    console = Console(file=io.StringIO(), force_terminal=True, width=100)
    plan = v2.demo_plan()
    result = v2.simulate(plan, notify=lambda e: None, delay=0)
    result.update(simulated=False, counts_now=dict(valid=20, parser_failure=5, technical_failure=2))
    original = deepcopy(result)
    view.summary(console, result)
    assert result == original
    assert '\x1b[1;31m' in console.file.getvalue()


def test_bold_current_values_and_dim_secondary_metadata(monkeypatch):
    monkeypatch.delenv('NO_COLOR', raising=False)
    console = Console(file=io.StringIO(), force_terminal=True, width=120)
    plan = v2.demo_plan()
    display = view.Display(console, plan.summary)
    display.event(dict(event='current', current=plan.labels[10]))
    console.print(display)
    text = console.file.getvalue()
    for value in ('SIM-002', 'qwen3.6:27b', '1 / 3', '101'):
        assert f'\x1b[1m{value}' in text
    assert '\x1b[2m◷ Elapsed' in text


@pytest.mark.parametrize('plain', [False, True])
def test_non_tty_text_matches_previous_presentation_bytes(monkeypatch, plain):
    """Recorded from commit 9264f49 at 80 columns with fixed presentation times."""
    console = terminal.console(file=io.StringIO(), plain=plain)
    console.width = 80
    plan = v2.demo_plan()
    result = v2.simulate(plan, notify=lambda e: None, delay=0)
    result.update(elapsed_seconds=13.5, average_execution_seconds=0.5)
    view.plan(console, plan.summary)
    monkeypatch.setattr(view.time, 'monotonic', lambda: 100)
    display = view.Display(console, plan.summary)
    display.event(dict(event='progress', state=dict(completed=13,
        counts=dict(valid=12, parser_failure=1, technical_failure=0))))
    display.event(dict(event='current', current=plan.labels[14]))
    monkeypatch.setattr(view.time, 'monotonic', lambda: 160)
    console.print(display)
    view.summary(console, result)
    assert sha256(console.file.getvalue().encode()).hexdigest() == '8fb2a4c387f058e88d1e19eb176ec09c5c6efd4a185459455fb9011abc347139'
