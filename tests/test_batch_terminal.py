"""Presentation-only checks: render existing events without scientific execution."""
from copy import deepcopy
import io
import json

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress

from rest_api_checker import batch_terminal as view, cli, evaluation_batch_v2 as v2, terminal


@pytest.mark.parametrize('simulated', [False, True])
@pytest.mark.parametrize('width', [80, 120])
def test_tty_components_and_readable_fields(monkeypatch, simulated, width):
    monkeypatch.delenv('NO_COLOR', raising=False)
    plan = v2.demo_plan()
    if not simulated:
        plan.summary['mode'] = 'Evaluation v2 Main'
    stream = io.StringIO()
    console = Console(file=stream, force_terminal=True, color_system=None, width=width)
    monkeypatch.setattr(view.time, 'monotonic', lambda: 100)
    display = view.Display(console, plan.summary)
    state = dict(planned=27, completed=9, counts=dict(valid=8, parser_failure=1, technical_failure=0))
    display.event(dict(event='progress', state=state))
    display.event(dict(event='current', current=plan.labels[10]))
    before = deepcopy(state), deepcopy(plan.summary), deepcopy(plan.labels[10])
    monkeypatch.setattr(view.time, 'monotonic', lambda: 160)
    group, = display.__rich_console__(console, console.options)
    assert any(isinstance(r, Progress) for r in group.renderables)
    assert any(isinstance(c, BarColumn) for c in display.progress.columns)
    panels = [r for r in group.renderables if isinstance(r, Panel)]
    assert [p.title.plain for p in panels] == ['Current execution', 'Result counters']
    assert display.progress.tasks[0].completed == 9
    console.print(display)
    text = stream.getvalue()
    for expected in ('Overall', '9 / 27', '33.3%', 'Elapsed 00:01:00', 'ETA (estimate) 00:02:00',
                     'Current execution', 'Case ID', 'SIM-002', 'API', 'SYNTHETIC', 'qwen3.6:27b',
                     'Repetition', 'Seed', '101', 'Operational state', 'Running',
                     'Result counters', 'Parser-valid', 'Parser failures', 'Technical failures', 'Remaining', '18'):
        assert expected in text
    assert '━' in text  # Actual rendered horizontal bar, not just a percentage.
    if simulated:
        assert all(s in text for s in ('DEMO / SIMULATION', 'NO MODEL CALLS', 'NO PREDICTION WRITES'))
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
    assert not any(c in text for c in '╭╮╰╯│─━')
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
