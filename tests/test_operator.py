"""Operator-only tests: fabricated SQL/containers, never study inference."""
from contextlib import nullcontext
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import tomllib

import pyodbc
import pytest

from rest_api_checker import cli, operator as op, operator_config as cfg, operator_menu as menu, terminal

ROOT = Path(__file__).resolve().parents[1]
SECRET = 'NEVER-PRINT-fabricated-password'


@pytest.fixture
def config(tmp_path, monkeypatch):
    for name in (*cfg.ENV.values(), 'RAC_WEB_ENV_FILE', 'RAC_WEB_DATABASE'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('RAC_CONFIG', str(tmp_path/'config.toml'))
    path = tmp_path/'credentials.env'
    path.write_text(f'RAC_SQL_PASSWORD={SECRET}\nRAC_SQL_PORT=14339\n')
    path.chmod(0o600)
    return cfg.load(SimpleNamespace())


@pytest.fixture
def console():
    return terminal.console(plain=True, file=io.StringIO())


@pytest.fixture
def sql(monkeypatch):
    cn = Mock()
    cn.execute.return_value.fetchval.return_value = 1
    monkeypatch.setattr(op, 'connect', Mock(return_value=cn))
    dispatch = Mock(return_value=({'database': 'rest_api_checker', 'version': 2}, 0))
    monkeypatch.setattr(op.cli, 'dispatch', dispatch)
    return cn, dispatch


def state(config, status='running', **extra):
    return dict(id='a'*64, name='/'+config.container, project=config.compose_project,
                service='sqlserver', state=status,
                ports={'1433/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '14339'}]}, **extra)


def mock_docker(monkeypatch, config, status='running'):
    calls = []
    current = status
    def docker(*args, **kwargs):
        nonlocal current
        calls.append(args)
        if args[0] == 'inspect':
            return json.dumps(state(config, current))
        if args[0] == 'start':
            current = 'running'
        if args[0] == 'stop':
            current = 'exited'
        return ''
    monkeypatch.setattr(op, 'docker', docker)
    return calls


def test_entry_points_preserved():
    scripts = tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['scripts']
    assert scripts == {'rac': 'rest_api_checker.operator:entrypoint',
                       'rest-api-checker': 'rest_api_checker.cli:entrypoint',
                       'rest-api-checker-web': 'rest_api_checker.web.app:main'}


def test_non_tty_never_loads_config_or_reads_input(monkeypatch, capsys):
    monkeypatch.setattr(op.sys.stdin, 'isatty', lambda: False)
    monkeypatch.setattr(op, 'load', Mock(side_effect=AssertionError('must not load')))
    assert op.main([]) == 0
    assert 'TTY only' in capsys.readouterr().out


@pytest.mark.parametrize('key,index,expected', [('1', 4, (0, True)), ('8', 0, (7, True)),
    ('down', 0, (1, False)), ('up', 0, (7, False)), ('down', 7, (0, False)),
    ('enter', 3, (3, True)), ('x', 2, (2, False))])
def test_selection(key, index, expected):
    assert menu.selection(key, index, 8) == expected


@pytest.mark.parametrize('raw,key', [(b'\x1b[A', 'up'), (b'\x1b[B', 'down'), (b'\r', 'enter'), (b'6', '6')])
def test_key_reader(monkeypatch, raw, key):
    values = iter(bytes([v]) for v in raw)
    monkeypatch.setattr(menu.os, 'read', lambda *a: next(values))
    monkeypatch.setattr(menu.select, 'select', lambda *a: ([1], [], []))
    assert menu.read_key(1) == key


def test_partial_escape_does_not_block(monkeypatch):
    monkeypatch.setattr(menu.os, 'read', lambda *a: b'\x1b')
    monkeypatch.setattr(menu.select, 'select', lambda *a: ([], [], []))
    assert menu.read_key(1) == '\x1b'


def test_plain_menu_is_visible_and_arrows_select(console, monkeypatch):
    keys = iter(['down', 'enter'])
    monkeypatch.setattr(menu, 'keyboard', lambda: nullcontext(1))
    monkeypatch.setattr(menu, 'read_key', lambda fd: next(keys))
    assert menu.choose(console, 'Test menu', ['One', 'Two']) == 1
    output = console.file.getvalue()
    assert 'Test menu' in output and '❯ 2  Two' in output and '\x1b' not in output


def test_ctrl_c_clean_exit(config, monkeypatch, capsys):
    monkeypatch.setattr(op.sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr(op.sys.stdout, 'isatty', lambda: True)
    monkeypatch.setattr(menu, 'launch', Mock(side_effect=KeyboardInterrupt))
    assert op.main([]) == 130
    assert 'Interrupted' in capsys.readouterr().out


@pytest.mark.parametrize('status,starts', [('running', 0), ('exited', 1), ('created', 1)])
def test_start_only_checks_existing_database(config, console, sql, monkeypatch, status, starts):
    calls = mock_docker(monkeypatch, config, status)
    value = op.start_database(config, console)
    assert value['status'] == 'READY' and value['schema_version'] == 2
    assert sum(call[0] == 'start' for call in calls) == starts
    assert {call[0] for call in calls} <= {'inspect', 'start'}
    args = sql[1].call_args.args[0]
    assert (args.group, args.command) == ('db', 'status')
    sql[0].execute.assert_called_once_with('SELECT DB_ID(?)', 'rest_api_checker')
    sql[0].close.assert_called_once()


def test_stop_preserves_all_resources(config, monkeypatch):
    calls = mock_docker(monkeypatch, config)
    assert op.stop_database(config)['data'] == 'preserved'
    assert [c for c in calls if c[0] != 'inspect'] == [('stop', '--time', '30', 'a'*64)]


def test_stop_without_credentials_and_already_stopped(config, monkeypatch):
    config.env_file.unlink()
    calls = mock_docker(monkeypatch, config, 'exited')
    assert op.stop_database(config)['status'] == 'STOPPED'
    assert all(c[0] == 'inspect' for c in calls)


@pytest.mark.parametrize('field,value', [('name', '/unrelated'), ('project', 'other'), ('service', 'other')])
def test_wrong_identity_no_mutation(config, console, monkeypatch, field, value):
    record = state(config)
    record[field] = value
    docker = Mock(return_value=json.dumps(record))
    monkeypatch.setattr(op, 'docker', docker)
    for action in (lambda: op.start_database(config, console), lambda: op.stop_database(config)):
        with pytest.raises(cfg.OperatorError, match='identity'):
            action()
    assert all(c.args[0] == 'inspect' for c in docker.call_args_list)


def test_wrong_port_does_not_start(config, console, monkeypatch):
    calls = mock_docker(monkeypatch, config, 'exited')
    config.env_file.write_text(f'RAC_SQL_PASSWORD={SECRET}\nRAC_SQL_PORT=14340\n')
    with pytest.raises(cfg.OperatorError, match='port'):
        op.start_database(config, console)
    assert all(c[0] == 'inspect' for c in calls)


def test_docker_diagnostic_is_preserved(config, monkeypatch):
    monkeypatch.setattr(op, 'docker', Mock(side_effect=cfg.OperatorError('SQL Server unavailable: Docker CLI not installed.')))
    with pytest.raises(cfg.OperatorError, match='Docker CLI not installed'):
        op.container(config)


def test_explicit_missing_credentials_never_become_offline_preflight(config, capsys):
    assert op.main(['preflight', '--env-file', str(config.root/'absent.env'), '--json']) == 3
    value = json.loads(capsys.readouterr().out)
    assert 'credentials file is missing' in value['error']


def test_missing_credentials_help_before_docker(config, console, monkeypatch):
    config.env_file.unlink()
    docker = Mock(side_effect=AssertionError)
    monkeypatch.setattr(op, 'docker', docker)
    with pytest.raises(cfg.OperatorError, match='rac configure'):
        op.start_database(config, console)
    docker.assert_not_called()


@pytest.mark.parametrize('mode', [0o644, 0o640, 0o400, 0o700])
def test_credentials_require_0600(config, mode):
    config.env_file.chmod(mode)
    with pytest.raises(cfg.OperatorError, match='0600'):
        cfg.credentials(config)


def test_invalid_credentials_are_redacted(config, monkeypatch, capsys):
    mock_docker(monkeypatch, config)
    monkeypatch.setattr(op, 'connect', Mock(side_effect=pyodbc.Error('28000', SECRET)))
    assert op.main(['db', 'start', '--json']) == 3
    out = capsys.readouterr()
    assert SECRET not in out.out+out.err
    assert 'credentials rejected' in json.loads(out.out)['error']


@pytest.mark.parametrize('contents', [f'RAC_SQL_PASSWORD={SECRET}\nRAC_SQL_PORT={SECRET}', SECRET, 'RAC_SQL_PORT=14339'])
def test_malformed_credential_file_never_leaks(config, capsys, contents):
    config.env_file.write_text(contents)
    assert op.main(['db', 'status', '--json']) == 3
    out = capsys.readouterr()
    assert SECRET not in out.out+out.err
    assert 'invalid' in json.loads(out.out)['error']


def test_missing_database_is_explicit_only(config, console, sql, monkeypatch):
    mock_docker(monkeypatch, config)
    sql[0].execute.return_value.fetchval.return_value = None
    with pytest.raises(cfg.OperatorError, match='Application database not initialized.*rac db init'):
        op.start_database(config, console)
    sql[1].assert_not_called()


def test_schema_mismatch_preserves_diagnostic(config, console, sql, monkeypatch):
    mock_docker(monkeypatch, config)
    sql[1].side_effect = ValueError('Migration history/checksum mismatch')
    with pytest.raises(cfg.OperatorError, match='Schema mismatch: Migration history/checksum mismatch'):
        op.start_database(config, console)


def test_readiness_timeout_is_bounded(config, console, monkeypatch):
    mock_docker(monkeypatch, config)
    monkeypatch.setattr(op, 'connect', Mock(side_effect=pyodbc.Error('08001', SECRET)))
    with pytest.raises(cfg.OperatorError, match='SQL Server unavailable'):
        op.start_database(config, console, timeout=0)
    assert op.connect.call_count == 1


def test_config_precedence_and_web_alias(config, monkeypatch):
    cfg.config_path().write_text('database = "from_config"\nport = 8001\n')
    assert cfg.load(SimpleNamespace()).database == 'from_config'
    monkeypatch.setenv('RAC_WEB_DATABASE', 'from_web_env')
    assert cfg.load(SimpleNamespace()).database == 'from_web_env'
    monkeypatch.setenv('RAC_DATABASE', 'from_env')
    assert cfg.load(SimpleNamespace()).database == 'from_env'
    assert cfg.load(SimpleNamespace(database='from_cli')).database == 'from_cli'
    assert cfg.load(SimpleNamespace()).port == 8001
    with pytest.raises(cfg.OperatorError):
        cfg.load(SimpleNamespace(port=0))


def test_configure_never_copies_secrets_or_overwrites(config):
    before = config.env_file.read_bytes()
    cfg.save(config)
    text = cfg.config_path().read_text()
    assert SECRET not in text
    assert str(config.env_file) in text
    assert cfg.load(SimpleNamespace()) == config
    with pytest.raises(cfg.OperatorError, match='Nothing was overwritten'):
        cfg.save(config)
    assert config.env_file.read_bytes() == before
    assert cfg.config_path().read_text() == text


@pytest.mark.parametrize('raw', [f'password = "{SECRET}"', f'port = "{SECRET}"', f'BROKEN {SECRET}'])
def test_bad_config_never_echoes_values(config, raw, capsys):
    cfg.config_path().write_text(raw)
    assert op.main(['db', 'start', '--json']) == 3
    out = capsys.readouterr()
    assert SECRET not in out.out+out.err


@pytest.mark.parametrize('open_browser', [False, True])
def test_web_reuses_app_opens_after_start_restores_environment(config, console, monkeypatch, open_browser):
    import asyncio
    import uvicorn
    from rest_api_checker.web import app
    application = object()
    monkeypatch.setattr(app, 'create_app', Mock(return_value=application))
    monkeypatch.setattr(op, 'start_database', Mock())
    browser = Mock(return_value=True)
    monkeypatch.setattr(op.webbrowser, 'open', browser)
    sock = Mock()
    sock.__enter__ = Mock(return_value=sock)
    sock.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(op, 'socket', SimpleNamespace(socket=Mock(return_value=sock),
                        AF_INET=2, AF_INET6=30, SOCK_STREAM=1))
    async def startup(server, sockets=None):
        assert sockets == [sock]
        assert server.config.app is application
        browser.assert_not_called()
        server.started = True
    def run(server, sockets=None):
        assert op.os.environ['RAC_WEB_ENV_FILE'] == str(config.env_file)
        asyncio.run(server.startup(sockets))
    monkeypatch.setattr(uvicorn.Server, 'startup', startup)
    monkeypatch.setattr(uvicorn.Server, 'run', run)
    monkeypatch.setenv('RAC_WEB_DATABASE', 'previous')
    assert op.web(config, console, open_browser=open_browser) == 0
    assert browser.call_count == int(open_browser)
    if open_browser:
        browser.assert_called_once_with('http://127.0.0.1:8000')
    assert op.os.environ['RAC_WEB_DATABASE'] == 'previous'
    assert 'RAC_WEB_ENV_FILE' not in op.os.environ
    op.start_database.assert_called_once()


def test_web_address_in_use_before_database_start(config, console, monkeypatch):
    sock = Mock()
    sock.__enter__ = Mock(return_value=sock)
    sock.__exit__ = Mock(return_value=False)
    sock.bind.side_effect = OSError(op.errno.EADDRINUSE, 'occupied')
    monkeypatch.setattr(op, 'socket', SimpleNamespace(socket=Mock(return_value=sock),
                        AF_INET=2, AF_INET6=30, SOCK_STREAM=1))
    start = Mock()
    monkeypatch.setattr(op, 'start_database', start)
    with pytest.raises(cfg.OperatorError, match='already in use'):
        op.web(config, console)
    start.assert_not_called()


def test_preflight_actual_backend_stays_blocked(config, capsys):
    config.env_file.unlink()
    assert op.main(['preflight', '--json']) == 3
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'BLOCKED'
    assert not result['inference_performed']
    assert sum(c['status'] == 'PASS' for c in result['checks']) == 8


def test_gate_summary_preserves_fail_and_blocked(console):
    value = dict(status='FAIL', checks=[dict(status=s, check=s+' check', detail='actual evidence')
                                      for s in ('PASS', 'BLOCKED', 'FAIL')])
    op.show_gate(console, value)
    text = console.file.getvalue()
    assert 'Overall: FAIL' in text and 'BLOCKED check' in text and 'FAIL check' in text


def test_real_experiment_menu_has_no_execution_path(config, console, monkeypatch):
    choices = iter([0, 1, 2, 4])
    monkeypatch.setattr(menu, 'choose', lambda *a: next(choices))
    monkeypatch.setattr(menu, 'dispatch', lambda *a: (dict(status='BLOCKED', checks=[]), 3))
    invoke = Mock()
    monkeypatch.setattr(menu, 'invoke', invoke)
    menu.experiments_menu(config, console)
    invoke.assert_not_called()
    assert 'BLOCKED' in console.file.getvalue()


@pytest.mark.parametrize('confirmation', [0, 1])
def test_demo_requires_explicit_confirmation_and_label(config, console, monkeypatch, confirmation):
    choices = iter([3, confirmation, 4])
    monkeypatch.setattr(menu, 'choose', lambda *a: next(choices))
    monkeypatch.setattr(menu, 'dispatch', lambda *a: (dict(status='BLOCKED', checks=[]), 3))
    def invoke(*args):
        assert 'FABRICATED / TEST DATA' in console.file.getvalue()
        assert 'No real LLM inference will be performed.' in console.file.getvalue()
        assert args[-1] == ['experiment', 'demo']
    called = Mock(side_effect=invoke)
    monkeypatch.setattr(menu, 'invoke', called)
    menu.experiments_menu(config, console)
    assert called.call_count == confirmation


def test_forwarded_execution_retains_existing_gate(config, monkeypatch, capsys):
    # Original dispatcher retains its own guard; convenience never supplies --fabricated.
    observed = []
    def dispatch(args, console):
        observed.append(args)
        return cli._execute(None, args, None)
    monkeypatch.setattr(cli, 'dispatch', dispatch)
    assert op.main(['experiment', 'run', '1', '--spool', '/tmp/unused', '--json']) == 3
    assert observed[0].fabricated is False
    assert 'BLOCKED' in json.loads(capsys.readouterr().out)['error']


def test_evaluation_menu_only_reads_or_exports(config, console, monkeypatch):
    choices = iter([0, 1, 2, 3])
    monkeypatch.setattr(menu, 'choose', lambda *a: next(choices))
    monkeypatch.setattr(menu, 'identifier', lambda *a: '7')
    monkeypatch.setattr('builtins.input', lambda *a: '/tmp/new-report.json')
    invoke = Mock()
    monkeypatch.setattr(menu, 'invoke', invoke)
    menu.evaluation_menu(config, console)
    assert [c.args[-1] for c in invoke.call_args_list] == [
        ['evaluate', 'list'], ['evaluate', 'show', '7'],
        ['evaluate', 'export', '7', '--output', '/tmp/new-report.json']]


def test_inspection_reuses_queries_and_rolls_back(config, console, monkeypatch):
    cn = Mock()
    query = Mock()
    query.data_list.return_value = dict(items=[], total=0, pages=1)
    monkeypatch.setattr(menu, 'connect', Mock(return_value=cn))
    monkeypatch.setattr(menu, 'WebQueries', Mock(return_value=query))
    menu.inspect_data(config, console, 'references')
    query.data_list.assert_called_once_with('references', page=1, kind='references')
    cn.rollback.assert_called_once()
    cn.close.assert_called_once()
    cn.commit.assert_not_called()


def test_help_available_without_credentials(config, capsys):
    config.env_file.unlink()
    with pytest.raises(SystemExit) as exc:
        op.main(['db', 'migrate', '--help'])
    assert exc.value.code == 0
    assert '--expected-current' in capsys.readouterr().out


@pytest.mark.parametrize('database', [False, True])
def test_advanced_help_returns_to_menu(console, capsys, database):
    menu.advanced(console, database=database)
    assert 'usage: rest-api-checker' in capsys.readouterr().out
    assert 'Examples:' in console.file.getvalue()
