"""Input-view navigation with fabricated collaborators; no SQL or inference."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from rest_api_checker import interactive_app as app, interactive_llm_input as inputs
from rest_api_checker import live_adhoc_runtime, live_demo_cli
from rest_api_checker.experiment.encoding import encode
from test_live_demo import PROMPT
from test_live_demo_cli import args, console, core  # noqa: F401


@pytest.fixture(autouse=True)
def metadata(monkeypatch):
    monkeypatch.setattr(live_adhoc_runtime, 'probe_runtime', lambda: dict(
        available=True, version='0.40.0', thesis_version='0.40.0'))


def configured(*flags):
    options = args('--case-id', '11', '--model-id', '4', '--repetitions', '1', *flags)
    options.adhoc = True
    return options


@pytest.mark.parametrize('cancel', ['', 'n', 'q', 'back'])
def test_preview_then_cancel_never_dispatches(core, monkeypatch, tmp_path, cancel):
    view, output = console()
    seen = []
    def preview(console, plan, read):
        assert not any(name == 'execute' for name, _ in core.calls)
        seen.append(plan)
        assert read('Preview navigation: ') == 'q'
    monkeypatch.setattr(inputs, 'show_plan_input', preview)
    answers = iter(['p', 'q', cancel])
    prompts = []
    def read(prompt):
        prompts.append(prompt)
        return next(answers)
    spool = tmp_path/'not-created'
    result, code = live_demo_cli.run(object(), configured('--spool', str(spool)), view,
                                    input_fn=read, interactive=True)
    assert code == 0 and result['status'] == 'CANCELLED'
    assert [name for name, _ in core.calls] == ['plan']
    assert len(seen) == 1 and not spool.exists()
    assert prompts.count('Run now? [y/N]: ') == 2
    assert 'p Preview LLM input' in output.getvalue()


def test_repeated_preview_uses_the_same_plan_that_execution_receives(core, monkeypatch):
    view, output = console()
    prepared = SimpleNamespace(summary=dict(prompt='P2'), requests={1: object()})
    planner = Mock(return_value=prepared)
    execute = Mock(return_value=dict(status='COMPLETED', exit_code=0, results=[]))
    preview = Mock()
    monkeypatch.setattr(core.module, 'plan', planner)
    monkeypatch.setattr(core.module, 'execute', execute)
    monkeypatch.setattr(inputs, 'show_plan_input', preview)
    answers = iter(['invalid', 'p', 'preview', 'yes'])
    read = lambda _: next(answers)
    repo = object()
    result, code = live_demo_cli.run(repo, configured(), view, input_fn=read, interactive=True)
    assert code == 0 and result['status'] == 'COMPLETED'
    planner.assert_called_once()
    assert preview.call_count == 2
    assert all(call.args == (view, prepared, read) for call in preview.call_args_list)
    execute.assert_called_once()
    assert execute.call_args.args == (repo, prepared)
    assert 'Enter y to run, n to cancel, or p to preview' in output.getvalue()


def test_real_input_sections_return_to_confirmation_without_executing(core, monkeypatch):
    view, output = console()
    payload = encode(dict(messages=[
        dict(role='system', content=PROMPT.decode('utf-8')),
        dict(role='user', content=encode(dict(operation=dict(method='POST', path='/validation'),
            openapi={}, observed_response=dict(status=201, content_type='application/json',
                                               body='{"message":"FABRICATED response"}'))).decode()),
    ], model='qwen3.6:27b', format='json', stream=False, options={}))
    prepared = SimpleNamespace(summary=dict(prompt='P2'), requests={1: SimpleNamespace(body=payload)})
    monkeypatch.setattr(core.module, 'plan', Mock(return_value=prepared))
    execute = Mock(side_effect=AssertionError('Preview must not execute'))
    monkeypatch.setattr(core.module, 'execute', execute)
    choices = iter(['p', '1', '2', '3', 'q', 'n'])
    prompts = []
    def read(prompt):
        prompts.append(prompt)
        return next(choices)
    result, code = live_demo_cli.run(object(), configured(), view, input_fn=read, interactive=True)
    assert code == 0 and result['status'] == 'CANCELLED'
    execute.assert_not_called()
    assert prompts.count('Run now? [y/N]: ') == 2
    text = output.getvalue()
    for phrase in ('TASK POLICY', 'FABRICATED response', 'Recorded API Response', 'OpenAPI Contract'):
        assert phrase in text
    assert prompts == ['Run now? [y/N]: ']+['Selection [1]: ']*4+['Run now? [y/N]: ']
    assert 'Request SHA-256:' not in text and 'not yet sent' not in text
    assert 'The run will be stored separately' not in text


@pytest.mark.parametrize('flag,status', [('--yes', 'COMPLETED'), ('--dry-run', 'DRY RUN')])
def test_explicit_noninteractive_modes_do_not_offer_preview(core, monkeypatch, flag, status):
    view, output = console()
    preview = Mock(side_effect=AssertionError('Unexpected preview'))
    monkeypatch.setattr(inputs, 'show_plan_input', preview)
    def forbidden(prompt):
        pytest.fail('Unexpected input: '+prompt)
    result, code = live_demo_cli.run(object(), configured(flag), view,
                                    input_fn=forbidden, interactive=False)
    assert code == 0 and result['status'] == status
    assert 'Preview LLM input' not in output.getvalue()
    preview.assert_not_called()


def test_strict_demo_confirmation_stays_unchanged(core, monkeypatch):
    view, output = console()
    preview = Mock(side_effect=AssertionError('Unexpected ad-hoc preview'))
    monkeypatch.setattr(inputs, 'show_plan_input', preview)
    options = configured()
    options.adhoc = False
    result, code = live_demo_cli.run(object(), options, view,
                                    input_fn=lambda _: 'p', interactive=True)
    assert code == 0 and result['status'] == 'CANCELLED'
    assert 'Preview LLM input' not in output.getvalue()
    preview.assert_not_called()


@pytest.mark.parametrize('exception', [EOFError, KeyboardInterrupt])
def test_interruption_inside_preview_cancels_without_execution(core, monkeypatch, exception):
    view, _ = console()
    monkeypatch.setattr(inputs, 'show_plan_input', Mock(side_effect=exception))
    result, code = live_demo_cli.run(object(), configured(), view,
                                    input_fn=lambda _: 'p', interactive=True)
    assert code == 130 and result['status'] == 'CANCELLED'
    assert [name for name, _ in core.calls] == ['plan']


@pytest.mark.parametrize('browsing,expected', [(False, 'another'), (True, 'back')])
def test_result_input_action_returns_to_same_menu(monkeypatch, browsing, expected):
    view, output = console()
    config, query = object(), object()
    seen = []
    @contextmanager
    def queries(current):
        assert current is config
        seen.append('open')
        try:
            yield query
        finally:
            seen.append('close')
    def show(current, run_id, console, read):
        assert (current, run_id, console) == (query, 20440, view)
        assert read('Input view: ') == 'q'
    monkeypatch.setattr(app, 'queries', queries)
    viewer = Mock(side_effect=show)
    monkeypatch.setattr(inputs, 'show_run_input', viewer)
    answers = iter(['5', 'q', '6'])
    result = app.result_actions(config, view, [dict(run=dict(id=20440, repetition=1))],
                                lambda _: next(answers), browsing=browsing)
    assert result == expected and seen == ['open', 'close']
    viewer.assert_called_once()
    assert output.getvalue().count('Next action') == 2
    assert 'View LLM input' in output.getvalue()


def test_input_action_uses_selected_repetition_not_latest_run(monkeypatch):
    view, _ = console()
    query = object()
    @contextmanager
    def queries(unused):
        yield query
    monkeypatch.setattr(app, 'queries', queries)
    viewer = Mock()
    monkeypatch.setattr(inputs, 'show_run_input', viewer)
    results = [dict(case='V2-EDX-001', run=dict(id=20440+i, repetition=i+1)) for i in range(2)]
    answers = iter(['5', '2', '7'])
    read = lambda _: next(answers)
    assert app.result_actions(object(), view, results, read) == 'main'
    viewer.assert_called_once_with(query, 20441, view, read)


@pytest.mark.parametrize('choice,expected', [('7', 'main'), ('8', 'exit')])
def test_result_navigation_after_added_input_action(choice, expected):
    view, _ = console()
    assert app.result_actions(object(), view, [], lambda _: choice) == expected
