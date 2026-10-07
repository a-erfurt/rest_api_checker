"""RestApiChecker interactive application and compatible command launcher."""
import argparse
from contextlib import closing
import errno
import json
import os
import socket
import subprocess
import sys
import time
import webbrowser

import pyodbc

from . import cli, terminal
from .operator_config import ENV, OperatorError, credentials, for_command, load, save
from .persistence.database import connect
from .persistence.inspection import portable


def options():
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    for key in ENV:
        parser.add_argument('--'+key.replace('_', '-'), type=int if key == 'port' else str)
    parser.add_argument('--plain', action='store_true')
    parser.add_argument('--json', action='store_true')
    return parser


def help_parser():
    return argparse.ArgumentParser(prog='rac', description=__doc__, epilog='''
Commands: db start | db stop | web [--open] | preflight | configure.
No command: interactive menu (TTY only).
All existing commands also work, e.g. rac db status, rac evaluate list.
Defaults: CLI > RAC_* environment > ~/.config/rest-api-checker/config.toml > project defaults.
Use rest-api-checker --help for authoritative research/admin commands.
''', formatter_class=argparse.RawDescriptionHelpFormatter, parents=[options()])


def cli_args(config, command, *, plain=False, json_output=False):
    config = for_command(config, command)
    result = ['--root', str(config.root), '--research', str(config.research), '--database', config.database]
    # Offline preflight remains available without credentials, as in the original CLI.
    if command[0] != 'preflight' or config.env_file.exists():
        credentials(config)
        result += ['--env-file', str(config.env_file)]
    if plain:
        result.append('--plain')
    if json_output:
        result.append('--json')
    return result + command


def dispatch(config, command, console):
    return cli.dispatch(cli.arguments().parse_args(cli_args(config, command)), console)


def docker(*args, timeout=15):
    try:
        result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise OperatorError('SQL Server unavailable: Docker CLI not installed.') from None
    except subprocess.TimeoutExpired:
        raise OperatorError('SQL Server unavailable: Docker operation timed out. Check Docker Desktop.') from None
    if result.returncode:
        # Do not expose Docker stderr or inspect Env (which contains the password).
        raise OperatorError('SQL Server unavailable: Docker cannot access the configured container. '
                            'Check Docker Desktop, context and rac configuration.')
    return result.stdout.strip()


def container(config):
    template = ('{"id":{{json .Id}},"name":{{json .Name}},"state":{{json .State.Status}},'
                '"project":{{json (index .Config.Labels "com.docker.compose.project")}},'
                '"service":{{json (index .Config.Labels "com.docker.compose.service")}},'
                '"ports":{{json .HostConfig.PortBindings}}}')
    try:
        value = json.loads(docker('inspect', '--type', 'container', '--format', template, config.container))
        valid = (value['name'] == '/'+config.container and value['project'] == config.compose_project
                 and value['service'] == 'sqlserver' and isinstance(value['id'], str))
    except OperatorError:
        raise
    except (ValueError, KeyError, TypeError):
        raise OperatorError('Cannot verify the configured SQL Server container identity.') from None
    if not valid:
        raise OperatorError('Container identity/Compose labels do not match; refusing to start or stop it.')
    return value


def sql_error(exc):
    # Inspect SQLSTATE/native codes privately; never render raw driver messages.
    detail = str(exc)
    if '28000' in detail or '18456' in detail:
        return 'SQL credentials rejected. Check the private credentials file and SQL login.'
    if '4060' in detail:
        return 'Application database unavailable or access denied. Check database name and login permissions.'
    if 'IM002' in detail or '01000' in detail and "Can't open lib" in detail:
        return 'SQL Server unavailable: install/configure ODBC Driver 18 for SQL Server.'
    return 'SQL Server unavailable: check local SQL readiness, port and login permissions.'


def start_database(config, console, *, timeout=60):
    settings = credentials(config)  # Validate before any container mutation.
    state = container(config)
    bindings = (state.get('ports') or {}).get('1433/tcp') or []
    if not any(p.get('HostIp') == '127.0.0.1' and p.get('HostPort') == settings['RAC_SQL_PORT'] for p in bindings):
        raise OperatorError('Configured SQL port does not match the known container loopback binding; refusing start.')
    if state['state'] in ('exited', 'created'):
        docker('start', state['id'], timeout=30)
    elif state['state'] != 'running':
        raise OperatorError('SQL Server is '+state['state']+'; inspect the known container explicitly before starting.')
    deadline = time.monotonic() + timeout
    while True:
        try:
            with closing(connect(settings, 'master')) as cn:
                cn.timeout = 10
                exists = cn.execute('SELECT DB_ID(?)', config.database).fetchval()
            break
        except pyodbc.Error as exc:
            message = sql_error(exc)
            if 'credentials rejected' in message or 'ODBC Driver' in message or time.monotonic() >= deadline:
                raise OperatorError(message) from None
            time.sleep(min(1, max(0, deadline-time.monotonic())))
    if exists is None:
        raise OperatorError('Application database not initialized (or not visible to this login). '
                            'If absent, explicitly run: rac db init. Then inspect rac db status and '
                            'use rac db migrate --expected-current 0 as required. No changes were made to the database.')
    try:
        value, _ = dispatch(config, ['db', 'status'], console)
    except ValueError as exc:
        raise OperatorError('Schema mismatch: '+str(exc)+'. Inspect rac db version; migration remains explicit.') from None
    return dict(sql_server='running', database=value['database'], schema_version=value['version'], status='READY')


def stop_database(config):
    state = container(config)
    if state['state'] in ('exited', 'created'):
        return dict(sql_server='stopped', status='STOPPED', data='preserved')
    if state['state'] != 'running':
        raise OperatorError('SQL Server is '+state['state']+'; inspect the known container explicitly before stopping.')
    docker('stop', '--time', '30', state['id'], timeout=45)
    if container(config)['state'] != 'exited':
        raise OperatorError('SQL Server stop was not confirmed; inspect the known container.')
    return dict(sql_server='stopped', status='STOPPED', data='preserved')


def show_gate(console, value):
    console.print(terminal.table('Gate B', ('Status', 'Checks'),
        [(status, sum(c['status'] == status for c in value['checks'])) for status in ('PASS', 'BLOCKED', 'FAIL')]))
    console.print('Overall: '+value['status'])
    for check in value['checks']:
        if check['status'] != 'PASS':
            console.print(terminal.clean(f'{check["status"]}: {check["check"]} — {check["detail"]}'))


def web(config, console, *, open_browser=False, open_path="", opened_message=None):
    if open_path and open_path != "/runs/latest" and not (open_path.startswith("/runs/") and open_path[6:].isdecimal()):
        raise OperatorError("Only a stored run page can be opened directly.")
    import uvicorn
    from .web.app import create_app

    family = socket.AF_INET6 if config.host == '::1' else socket.AF_INET
    # Reserve the port before starting SQL. Pass this exact socket to Uvicorn.
    with socket.socket(family, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((config.host, config.port))
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                raise OperatorError('Web server address already in use; choose --port or stop its current owner.') from None
            raise OperatorError('Cannot bind the configured local web address.') from None
        start_database(config, console)
        url = f'http://{"[::1]" if config.host == "::1" else config.host}:{config.port}'
        previous = {key: os.environ.get(key) for key in ('RAC_WEB_ENV_FILE', 'RAC_WEB_DATABASE')}
        os.environ.update(RAC_WEB_ENV_FILE=str(config.env_file), RAC_WEB_DATABASE=config.database)

        class LocalServer(uvicorn.Server):
            async def startup(self, sockets=None):
                await super().startup(sockets=sockets)
                if self.started:
                    if opened_message is None:
                        console.print('RestApiChecker Web UI', style=terminal.ACCENT)
                        console.print('Database   ✓ ready\nURL        '+url+'\n\nPress Ctrl-C to stop.')
                    if open_browser:
                        try:
                            opened = webbrowser.open(url+open_path)
                        except webbrowser.Error:
                            opened = False
                        if opened and opened_message is not None:
                            console.print(opened_message, style='dim')
                        elif not opened:
                            console.print('Browser could not be opened; open: '+url+open_path)
                            if opened_message is not None:
                                console.print('Ctrl-C returns to the menu.', style='dim')

        try:
            LocalServer(uvicorn.Config(create_app(), host=config.host, port=config.port, log_level='warning')).run(sockets=[sock])
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    common, command = options().parse_known_args(argv)
    console = terminal.console(plain=common.plain or common.json)
    if command in (['--help'], ['-h']):
        help_parser().print_help()
        return 0
    if not command and (common.json or not sys.stdin.isatty() or not sys.stdout.isatty()):
        help_parser().print_help()
        return 0
    try:
        config = load(common)
        if not command:
            from .operator_menu import launch
            return launch(config, console)
        if command[:2] in (['db', 'start'], ['db', 'stop']) or command[0] in ('web', 'configure'):
            parser = argparse.ArgumentParser(prog='rac '+' '.join(command[:2] if command[0] == 'db' else command[:1]))
            if command[0] == 'web':
                parser.add_argument('--open', action='store_true')
            args = parser.parse_args(command[2:] if command[0] == 'db' else command[1:])
            if command[0] == 'web':
                if common.json:
                    raise OperatorError('rac web is a long-running server; use --plain, not --json.')
                return web(config, console, open_browser=args.open)
            value = save(config) if command[0] == 'configure' else (
                start_database(config, console) if command[1] == 'start' else stop_database(config))
            code = 0
        elif command[0] == 'preflight':
            value, code = dispatch(config, command, console)
            if not common.json:
                show_gate(console, value)
                return code
        else:
            # Help must work even before credentials are configured.
            if '--help' in command or '-h' in command:
                return cli.main(command)
            return cli.main(cli_args(config, command, plain=common.plain, json_output=common.json))
    except KeyboardInterrupt:
        value, code = dict(status='INTERRUPTED', error='Interrupted.'), 130
    except (ValueError, pyodbc.Error, OSError) as exc:
        message = sql_error(exc) if isinstance(exc, pyodbc.Error) else (
            str(exc) if isinstance(exc, OperatorError) else 'Local operation unavailable; check file access and configuration.')
        value, code = dict(status='BLOCKED', error=message), 3
    if common.json:
        print(json.dumps(portable(value), ensure_ascii=True, sort_keys=True))
    elif 'error' in value:
        console.print(terminal.clean(value['error']))
    else:
        console.print(terminal.table('Database' if command[0] == 'db' else 'Configuration', ('Setting', 'Value'), value.items()))
    return code


def entrypoint():
    raise SystemExit(main())


if __name__ == '__main__':
    entrypoint()
