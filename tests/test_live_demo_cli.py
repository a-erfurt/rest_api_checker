"""Live wizard tests: fabricated collaborators only; no SQL or model calls."""
import io
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import rest_api_checker
from rest_api_checker import cli, live_demo_cli, terminal


def args(*extra):
    return cli.arguments().parse_args(['demo', 'run', '--root', '/demo-root', *extra])


@pytest.fixture
def core(monkeypatch):
    calls = []
    cases = [dict(id=11, dataset_id=1, dataset_name='development', case_code='DEV-01',
                  service_id=7, service='Dynamic service', operation_id=21, method='POST',
                  path='/validation', origin='natural_observation', reference=['PASS']*3)]
    models = [dict(id=4, name='qwen3.6:27b'), dict(id=8, name='gemma3:27b')]
    data = dict(cases=cases, models=models, prompts=[dict(id=2, name='P2')], configs=[])
    paths = [Path('/qualified/runtime-binding.json')]
    def plan(repo, **kwargs):
        calls.append(('plan', kwargs))
        return SimpleNamespace(summary={'prompt_id': 2, 'run_config_ids': [1]})
    def execute(repo, plan, **kwargs):
        calls.append(('execute', kwargs))
        kwargs['notify'](dict(event='current', current=dict(model='qwen3.6:27b', case='DEV-01',
            repetition=1, run_id=10004, attempt=1)))
        return dict(status='COMPLETED', exit_code=0, experiment_id=10004, run_ids=[999],
                    results=[], spool=str(kwargs['spool']), message=None)
    value = SimpleNamespace(catalog=lambda repo: data, runtime_paths=lambda root: paths,
                            plan=plan, execute=execute)
    monkeypatch.setattr(rest_api_checker, 'live_demo', value, raising=False)
    return SimpleNamespace(module=value, calls=calls, data=data, paths=paths)


def console():
    stream = io.StringIO()
    return terminal.console(plain=True, file=stream), stream


def no_input(prompt):
    pytest.fail('Unexpected input: '+prompt)


def test_help_exposes_safe_selection_and_modes(capsys):
    with pytest.raises(SystemExit) as exited:
        cli.arguments().parse_args(['demo', 'run', '--help'])
    assert exited.value.code == 0
    output = capsys.readouterr().out
    for flag in ('--case-id', '--model-id', '--repetitions', '--runtime-binding', '--dry-run', '--yes', '--ui-url'):
        assert flag in output


def test_readonly_dry_run_does_not_execute_or_create_spool(core, tmp_path):
    spool = tmp_path/'not-created'
    view, output = console()
    value, code = live_demo_cli.run(object(), args('--case-id', '11', '--model-id', '4', '--dry-run',
        '--spool', str(spool)), view, input_fn=no_input, interactive=False)
    assert code == 0 and value['writes'] == value['model_calls'] == 0
    assert value['runtime_contacted'] is False and not spool.exists()
    assert [name for name, _ in core.calls] == ['plan']
    assert 'Dynamic service' in output.getvalue() and 'P2 (unchanged)' in output.getvalue()


def test_interactive_dynamic_service_operation_case_models_and_repetitions(core):
    view, output = console()
    answers = iter(['1', '1', '1', '1,2', '2', 'yes'])
    value, code = live_demo_cli.run(object(), args(), view, input_fn=lambda _: next(answers), interactive=True)
    assert code == 0 and value['experiment_id'] == 10004
    assert core.calls[0][1]['case_id'] == 11
    assert core.calls[0][1]['model_ids'] == [4, 8] and core.calls[0][1]['repetitions'] == 2
    assert [name for name, _ in core.calls] == ['plan', 'execute']
    assert 'Select service' in output.getvalue() and 'Running qwen3.6:27b' in output.getvalue()


@pytest.mark.parametrize('answer', ['', 'n', 'no', 'anything'])
def test_default_no_never_dispatches(core, answer):
    view, _ = console()
    value, code = live_demo_cli.run(object(), args('--case-id', '11', '--model-id', '4', '--repetitions', '1'),
        view, input_fn=lambda _: answer, interactive=True)
    assert code == 0 and value['status'] == 'CANCELLED'
    assert [name for name, _ in core.calls] == ['plan']


@pytest.mark.parametrize('exception', [EOFError, KeyboardInterrupt])
def test_selection_interrupt_is_graceful_and_no_execution(core, exception):
    view, _ = console()
    def interrupt(_):
        raise exception()
    value, code = live_demo_cli.run(object(), args(), view, input_fn=interrupt, interactive=True)
    assert code == 130 and value['status'] == 'CANCELLED' and core.calls == []


@pytest.mark.parametrize('flags, message', [
    ([], 'Non-interactive demo needs'),
    (['--yes'], '--yes requires explicit'),
    (['--case-id', '11', '--model-id', '4'], 'requires --yes'),
    (['--case-id', '11', '--model-id', '4', '--model-id', '4', '--dry-run'], 'Duplicate'),
    (['--case-id', '999', '--model-id', '4', '--dry-run'], 'unavailable or protected'),
    (['--case-id', '11', '--model-id', '999', '--dry-run'], 'unavailable or unapproved'),
    (['--case-id', '11', '--model-id', '4', '--dataset-id', '3', '--dry-run'], 'No eligible development'),
])
def test_invalid_or_unconfirmed_requests_fail_before_plan(core, flags, message):
    view, _ = console()
    with pytest.raises(ValueError, match=message):
        live_demo_cli.run(object(), args(*flags), view, input_fn=no_input, interactive=False)
    assert core.calls == []


def test_multiple_runtime_bindings_require_explicit_noninteractive_choice(core):
    core.paths.append(Path('/another/runtime-binding.json'))
    view, _ = console()
    with pytest.raises(ValueError, match='Multiple runtime bindings'):
        live_demo_cli.run(object(), args('--case-id', '11', '--model-id', '4', '--dry-run'),
            view, input_fn=no_input, interactive=False)
    assert core.calls == []


def test_explicit_runtime_and_yes_execute_with_no_prompts(core):
    core.paths[:] = []
    view, _ = console()
    value, code = live_demo_cli.run(object(), args('--case-id', '11', '--model-id', '4', '--yes',
        '--runtime-binding', '/chosen/runtime-binding.json', '--ui-url', 'http://localhost:9000'),
        view, input_fn=no_input, interactive=False)
    assert code == 0 and value['ui_url'] == 'http://localhost:9000'
    assert core.calls[0][1]['runtime_path'] == Path('/chosen/runtime-binding.json')


def test_empty_eligible_case_inventory_reports_boundaries(core):
    core.data['cases'] = []
    view, _ = console()
    with pytest.raises(ValueError, match='Evaluation datasets and Dataset 3 are excluded'):
        live_demo_cli.run(object(), args(), view, interactive=True)


def test_invalid_menu_and_repetition_answers_can_be_corrected(core):
    view, output = console()
    answers = iter(['garbage', '1', '1', '1', '1,1', '2', '4', '1', 'n'])
    value, code = live_demo_cli.run(object(), args(), view, input_fn=lambda _: next(answers), interactive=True)
    assert code == 0 and value['status'] == 'CANCELLED'
    assert core.calls[0][1]['model_ids'] == [8]
    assert 'Enter 1, 2 or 3' in output.getvalue()


def test_json_mode_emits_only_json_and_never_prompts(core, monkeypatch, capsys):
    monkeypatch.setattr(cli, 'dispatch', lambda parsed, view: live_demo_cli.run(object(), parsed, view,
        input_fn=no_input, interactive=True))
    assert cli.main(['demo', 'run', '--case-id', '11', '--model-id', '4', '--yes', '--json']) == 0
    captured = capsys.readouterr()
    value = json.loads(captured.out)
    assert value['status'] == 'COMPLETED' and captured.err == ''
    assert '\x1b' not in captured.out and 'Running ' not in captured.out


def test_plain_result_links_and_existing_inspection_renderer(monkeypatch):
    view, output = console()
    shown = []
    monkeypatch.setattr(terminal, 'inspection', lambda *a: shown.append(a[1]))
    detail = dict(run={'id': 101}, response_id=42)
    live_demo_cli.present(view, dict(status='COMPLETED', experiment_id=10004,
        results=[detail], ui_url='http://localhost:9000', spool='/new/demo'))
    assert shown == [detail]
    for phrase in ('rac inspect run 101', 'http://localhost:9000/runs/101', 'rac experiment show 10004',
                   'Observed API response ID: 42'):
        assert phrase in output.getvalue()
    assert '\x1b' not in output.getvalue()


def test_dry_run_and_yes_cannot_be_combined():
    with pytest.raises(SystemExit):
        args('--dry-run', '--yes')


@pytest.mark.parametrize('url', ['file:///tmp/output', 'http://user:secret@localhost:8000', 'http://localhost:8000?token=secret'])
def test_ui_urls_cannot_expose_credentials_or_nonweb_schemes(core, url):
    view, _ = console()
    with pytest.raises(ValueError, match='--ui-url must'):
        live_demo_cli.run(object(), args('--case-id', '11', '--model-id', '4', '--dry-run', '--ui-url', url),
            view, input_fn=no_input, interactive=False)
    assert core.calls == []


@pytest.mark.parametrize('failure', [
    TypeError('private metadata detail'), IndexError('private metadata detail'),
    AttributeError('private metadata detail'),
    subprocess.CalledProcessError(1, ['private-runtime-command'], output='private metadata detail'),
    subprocess.TimeoutExpired(['private-runtime-command'], timeout=15),
])
def test_demo_dispatch_handles_malformed_or_unavailable_runtime_without_traceback(monkeypatch, capsys, failure):
    monkeypatch.setattr(cli, 'read_settings', lambda path: {})
    monkeypatch.setattr(cli, 'connect', lambda settings, database: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(cli, 'Repository', lambda connection: object())
    def broken(*unused):
        raise failure
    monkeypatch.setattr(live_demo_cli, 'run', broken)
    code = cli.main(['demo', 'run', '--env-file', '/private/unused.env', '--case-id', '11',
                     '--model-id', '4', '--dry-run', '--json'])
    output = capsys.readouterr()
    value = json.loads(output.out)
    assert code == 3 and value['status'] == 'BLOCKED'
    assert 'runtime' in value['error'] and 'Traceback' not in output.err
    assert 'private metadata detail' not in output.out + output.err
    assert 'private-runtime-command' not in output.out + output.err
