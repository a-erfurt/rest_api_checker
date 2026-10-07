"""Supervisor flow over fabricated read-only collaborators; no SQL or inference."""
from contextlib import contextmanager
from copy import deepcopy
import io
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from rest_api_checker import interactive_app as app, interactive_menu as menu
from rest_api_checker import operator, operator_menu, terminal


@pytest.fixture
def console():
    return terminal.console(plain=True, file=io.StringIO())


@pytest.fixture
def config():
    return SimpleNamespace(host='127.0.0.1', port=8000, database='FABRICATED')


def answers(*values):
    sequence = iter(values)
    def read(prompt):
        assert ' ID' not in prompt and '_id' not in prompt
        return next(sequence)
    return read


def test_bare_rac_opens_four_choice_application(monkeypatch, config, console):
    monkeypatch.setattr(operator.sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr(operator.sys.stdout, 'isatty', lambda: True)
    monkeypatch.setattr(operator, 'load', lambda unused: config)
    monkeypatch.setattr(operator.terminal, 'console', lambda **unused: console)
    monkeypatch.setattr('builtins.input', answers('4'))
    assert operator.main([]) == 0
    text = console.file.getvalue()
    for phrase in ('RestApiChecker', 'Choose an action:', 'Run API response check',
                   'Browse previous results', 'Open Web UI', 'Exit'):
        assert phrase in text
    assert 'database IDs' not in text
    assert 'live demo' not in text.lower()


def test_root_help_does_not_load_config_or_start_wizard(monkeypatch, capsys):
    def forbidden(*unused):
        pytest.fail('Help must not load configuration or enter the application')
    monkeypatch.setattr(operator, 'load', forbidden)
    monkeypatch.setattr(operator_menu, 'launch', forbidden)
    assert operator.main(['--help']) == 0
    assert 'usage: rac' in capsys.readouterr().out


@pytest.mark.parametrize('command', [
    ['db', 'status'], ['inspect', 'run', '77'], ['experiment', 'list'], ['dataset', 'list'],
])
def test_existing_commands_keep_direct_dispatch(monkeypatch, config, command):
    monkeypatch.setattr(operator, 'load', lambda unused: config)
    forwarded = Mock(return_value=0)
    monkeypatch.setattr(operator.cli, 'main', forwarded)
    monkeypatch.setattr(operator, 'cli_args', lambda current, selected, **unused: selected)
    monkeypatch.setattr(operator_menu, 'launch', lambda *unused: pytest.fail('Unexpected wizard'))
    assert operator.main(command) == 0
    forwarded.assert_called_once_with(command)


@pytest.mark.parametrize(('selection', 'handler'), [('1', 'run_check'), ('2', 'browse')])
def test_root_routes_workflows_and_returns_to_menu(monkeypatch, config, console, selection, handler):
    action = Mock(return_value='main')
    monkeypatch.setattr(app, handler, action)
    assert app.launch(config, console, input_fn=answers(selection, '4')) == 0
    action.assert_called_once()
    assert console.file.getvalue().count('Choose an action:') == 2


@pytest.mark.parametrize(('latest', 'path', 'message'), [
    (dict(id=20440), '/runs/20440', 'latest run'), (None, '', 'overview'),
])
def test_root_web_option_uses_existing_web_logic(monkeypatch, config, console, latest, path, message):
    lookup = Mock(return_value=latest)
    @contextmanager
    def queries(unused):
        yield SimpleNamespace(latest_interactive_run=lookup)
    launch_web = Mock(return_value=0)
    monkeypatch.setattr(app, 'queries', queries)
    monkeypatch.setattr(operator, 'web', launch_web)
    assert app.launch(config, console, input_fn=answers('3', '4')) == 0
    lookup.assert_called_once_with()
    launch_web.assert_called_once_with(config, console, open_browser=True, open_path=path,
                                      opened_message='Web UI opened: '+message)
    assert 'Web UI opened:' not in console.file.getvalue()


def test_direct_web_command_remains_supported(monkeypatch, config):
    monkeypatch.setattr(operator, 'load', lambda unused: config)
    launch_web = Mock(return_value=0)
    monkeypatch.setattr(operator, 'web', launch_web)
    assert operator.main(['web', '--open']) == 0
    assert launch_web.call_args.kwargs == {'open_browser': True}


@pytest.mark.parametrize('answer', ['q', 'back'])
def test_root_cancel_exits_without_work(monkeypatch, config, console, answer):
    monkeypatch.setattr(app, 'run_check', lambda *unused: pytest.fail('Unexpected run'))
    assert app.launch(config, console, input_fn=answers(answer)) == 0


def test_paged_menu_selects_case_by_page_number_not_database_id(console):
    items = [dict(id=900001+i, case=f'CASE-{i+1:02}') for i in range(18)]
    selected = menu.choose(console, 'Select case', items, lambda item: item['case'], answers('n', '2'))
    assert selected is items[9]
    text = console.file.getvalue()
    assert 'Page 1/3' in text and 'Page 2/3' in text
    assert '2  CASE-10' in text and '900010' not in text


def test_search_details_and_numbered_selection(console):
    items = [dict(id=5000+i, name=f'Option {i}') for i in range(12)]
    details = Mock()
    selected = menu.choose(console, 'Select case', items, lambda item: item['name'],
        answers('/option 10', 'd 1', '1'), details=details)
    assert selected is items[10]
    details.assert_called_once_with(items[10])
    assert '1  Option 10' in console.file.getvalue()
    assert '5010' not in console.file.getvalue()


def test_empty_search_can_be_cleared_and_bad_number_corrected(console):
    selected = menu.choose(console, 'Select case', list(range(10)), lambda value: f'Case {value}',
        answers('/absent', '1', '/', '99', '1'))
    assert selected == 0
    assert 'No matching options' in console.file.getvalue()
    assert 'Enter one number from this page.' in console.file.getvalue()


def test_multiple_selection_rejects_duplicates_and_uses_visible_page(console):
    selected = menu.choose(console, 'Models', list(range(12)), str,
        answers('n', '1,1', '1,2'), multiple=True)
    assert selected == [8, 9]
    assert 'Enter distinct numbers' in console.file.getvalue()


def test_menu_neutralizes_terminal_control_sequences(console):
    menu.choose(console, 'Select', ['literal [red]\x1b[2J'], str, answers('1'))
    text = console.file.getvalue()
    assert '\x1b' not in text and '[red]' in text and '\\x1b[2J' in text


def test_query_context_rolls_back_and_closes_on_error(monkeypatch, config):
    cn = Mock()
    query = object()
    monkeypatch.setattr(app, 'credentials', lambda unused: {})
    monkeypatch.setattr(app, 'connect', lambda *unused: cn)
    monkeypatch.setattr(app, 'WebQueries', lambda current: query)
    with pytest.raises(RuntimeError, match='test'):
        with app.queries(config) as current:
            assert current is query
            raise RuntimeError('test')
    cn.rollback.assert_called_once()
    cn.close.assert_called_once()
    cn.commit.assert_not_called()
    cn.execute.assert_not_called()


@pytest.fixture
def stored(monkeypatch):
    calls = []
    runs = [dict(id=81000+i, case=f'CASE-{i+1:02}', model='Fabricated model', prompt='P2',
                 repetition=1, result='parser_failure', finished_at='2026-10-07') for i in range(11)]
    category = dict(c1='PASS', c2='FAIL', c3='NOT_APPLICABLE')
    class Queries:
        def experiments(self):
            calls.append(('experiments',))
            return [dict(id=10003, name='Final thesis evaluation', dataset_name='Frozen dataset',
                         completed=738, planned=738)]
        def runs(self, **filters):
            calls.append(('runs', filters))
            assert filters['experiment_id'] == 10003
            return dict(items=deepcopy(runs), pages=1)
        def run_detail(self, run_id, tab):
            calls.append(('detail', run_id, tab))
            run = next(deepcopy(row) for row in runs if row['id'] == run_id)
            return dict(run=run, reference=category, prediction=None, attempts=[], evidence=[
                dict(title='Exact provider response', content=json.dumps({'message': {'content': 'unusable [red]\x1b[2J'}}))
            ] if tab == 'raw-output' else [])
    @contextmanager
    def queries(unused):
        calls.append(('open',))
        try:
            yield Queries()
        finally:
            calls.append(('rollback-close',))
    monkeypatch.setattr(app, 'queries', queries)
    return calls


def test_browse_final_context_details_raw_and_back_without_ids(monkeypatch, config, console, stored):
    detailed = Mock()
    monkeypatch.setattr(app.live_result, 'show_details', detailed)
    assert app.browse(config, console, answers('1', '/case-10', '1', '1', '2', '5', 'q')) == 'main'
    assert ('detail', 81009, 'reasons') in stored
    assert ('detail', 81009, 'raw-output') in stored
    assert [call for call in stored if call[0] == 'open'] == [('open',)]*5
    assert sum(call[0]=='open' for call in stored) == sum(call[0]=='rollback-close' for call in stored)
    detailed.assert_called_once()
    text = console.file.getvalue()
    for phrase in ('Previous results · read-only', 'Final thesis evaluation', 'CASE-10', 'NO USABLE OUTPUT', 'Raw model response'):
        assert phrase in ' '.join(text.split())
    assert '\x1b' not in text and '[red]' in text


def test_browse_empty_context_returns_to_main(monkeypatch, config, console):
    @contextmanager
    def queries(unused):
        yield SimpleNamespace(experiments=lambda: [])
    monkeypatch.setattr(app, 'queries', queries)
    assert app.browse(config, console, answers()) == 'main'
    assert 'No stored run contexts' in console.file.getvalue()


def test_result_deep_link_is_passed_to_existing_server(monkeypatch, config, console):
    web = Mock()
    monkeypatch.setattr(operator, 'web', web)
    app.open_web(config, console, 81234)
    web.assert_called_once_with(config, console, open_browser=True, open_path='/runs/81234',
                                opened_message='Web UI opened: stored run')
    assert app.ui_url(config, 81234) == 'http://127.0.0.1:8000/runs/81234'
    config.host = '::1'
    assert app.ui_url(config, 81234) == 'http://[::1]:8000/runs/81234'


def test_web_existing_port_never_opens_unknown_listener(monkeypatch, config, console):
    web = Mock(side_effect=operator.OperatorError('Web server address already in use'))
    browser = Mock()
    monkeypatch.setattr(operator, 'web', web)
    monkeypatch.setattr(app.webbrowser, 'open', browser)
    monkeypatch.setattr(app, '_existing_web_ui', lambda url: False)
    app.open_web(config, console, 81234)
    browser.assert_not_called()
    assert 'Web UI opened:' not in console.file.getvalue()
    assert 'http://127.0.0.1:8000/runs/81234' in console.file.getvalue()


def test_run_check_delegates_to_shared_adhoc_flow_and_cancels_readonly(monkeypatch, config, console):
    from rest_api_checker.persistence import repository
    cn, repo = Mock(), object()
    monkeypatch.setattr(operator, 'cli_args', lambda *args, **kwargs: ['demo', 'run'])
    monkeypatch.setattr(app, 'credentials', lambda unused: {})
    monkeypatch.setattr(app, 'connect', lambda *unused: cn)
    monkeypatch.setattr(repository, 'Repository', lambda connection: repo)
    def shared(current, args, view, **kwargs):
        assert current is repo and args.adhoc is True
        assert args.ui_url == 'http://127.0.0.1:8000'
        assert kwargs['interactive'] is True
        return dict(status='CANCELLED'), 0
    monkeypatch.setattr(app.live_demo_cli, 'run', shared)
    assert app.run_check(config, console, answers()) == 'main'
    cn.rollback.assert_called_once()
    cn.close.assert_called_once()
    cn.commit.assert_not_called()
    assert 'No run created or model called' in console.file.getvalue()


def test_post_run_web_action_uses_exact_created_run_without_latest_lookup(monkeypatch, config, console):
    current = dict(run=dict(id=20440, repetition=1), case='V2-EDX-002')
    opened = Mock()
    monkeypatch.setattr(app, 'open_web', opened)
    monkeypatch.setattr(app, 'queries', lambda *args: pytest.fail('Must not substitute latest for selected run'))
    assert app.result_actions(config, console, [current], answers('4', '6')) == 'main'
    opened.assert_called_once_with(config, console, 20440)


def test_known_existing_web_ui_reopens_exact_run(monkeypatch, config, console):
    monkeypatch.setattr(operator, 'web', Mock(side_effect=operator.OperatorError('address already in use')))
    monkeypatch.setattr(app, '_existing_web_ui', lambda url: url.endswith('/runs/20440'))
    opened = Mock(return_value=True)
    monkeypatch.setattr(app.webbrowser, 'open', opened)
    app.open_web(config, console, 20440)
    opened.assert_called_once_with('http://127.0.0.1:8000/runs/20440')
    assert console.file.getvalue().strip() == 'Web UI opened: stored run'


@pytest.mark.parametrize(('marker', 'redirected', 'expected'), [
    ('read-only', False, True), (None, False, False), ('read-only', True, False),
])
def test_existing_ui_probe_requires_marker_and_same_url(monkeypatch, marker, redirected, expected):
    url = 'http://127.0.0.1:8000/runs/20440'
    response = Mock(headers={'X-RestApiChecker-UI': marker})
    response.geturl.return_value = 'http://elsewhere.invalid/' if redirected else url
    @contextmanager
    def urlopen(request, timeout):
        assert request.full_url == url and timeout == 2
        yield response
    monkeypatch.setattr(app, 'build_opener', lambda handler: SimpleNamespace(open=urlopen))
    assert app._existing_web_ui(url) is expected


def test_root_web_defers_latest_until_existing_database_start(monkeypatch, config, console):
    @contextmanager
    def queries(unused):
        raise app.DataUnavailable('Database unavailable')
        yield
    monkeypatch.setattr(app, 'queries', queries)
    web = Mock()
    monkeypatch.setattr(operator, 'web', web)
    app.open_web(config, console)
    web.assert_called_once_with(config, console, open_browser=True, open_path='/runs/latest',
                                opened_message='Web UI opened: latest run')


@pytest.mark.parametrize(('target', 'expected'), [
    ('http://127.0.0.1:8000/runs/20440', True), ('http://127.0.0.1:8000/runs', True),
    ('http://127.0.0.1:8001/runs/20440', False), ('http://elsewhere.invalid/runs/20440', False),
    ('http://127.0.0.1:8000/data', False), ('http://127.0.0.1:8000/runs/20440?next=elsewhere', False),
])
def test_latest_probe_only_follows_same_origin_run_redirect(monkeypatch, target, expected):
    url = 'http://127.0.0.1:8000/runs/latest'
    response = Mock(headers={'X-RestApiChecker-UI': 'read-only'})
    response.geturl.return_value = target
    @contextmanager
    def open(request, timeout):
        yield response
    def build_opener(handler):
        if not expected:
            with pytest.raises(app.URLError):
                handler.redirect_request(app.Request(url), None, 302, 'Found', {}, target)
        return SimpleNamespace(open=open)
    monkeypatch.setattr(app, 'build_opener', build_opener)
    assert app._existing_web_ui(url) is expected


def test_known_ui_browser_failure_does_not_claim_opened(monkeypatch, config, console):
    monkeypatch.setattr(operator, 'web', Mock(side_effect=operator.OperatorError('address already in use')))
    monkeypatch.setattr(app, '_existing_web_ui', lambda url: True)
    monkeypatch.setattr(app.webbrowser, 'open', Mock(return_value=False))
    app.open_web(config, console, 20440)
    assert 'Web UI opened:' not in console.file.getvalue()
    assert 'Open the Web UI: http://127.0.0.1:8000/runs/20440' in console.file.getvalue()
