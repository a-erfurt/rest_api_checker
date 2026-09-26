"""Small POSIX terminal launcher; no alternate screen, mouse or background work."""
from contextlib import closing, contextmanager
import os
import select
import sys

import pyodbc
from rich.console import Group
from rich.live import Live
from rich.text import Text

from . import cli, terminal
from .operator import cli_args, dispatch, show_gate, sql_error, start_database, stop_database, web
from .operator_config import OperatorError, credentials
from .persistence.database import connect
from .web.queries import WebQueries


@contextmanager
def keyboard():
    if os.name != 'posix':
        raise OperatorError('Interactive keys require a POSIX terminal. Use rac --help for direct commands.')
    import termios
    import tty
    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield fd
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original)


def read_key(fd):
    value = os.read(fd, 1)
    if value in (b'', b'\x03', b'\x04'):
        raise KeyboardInterrupt
    if value == b'\x1b':
        # Bare Escape and partial escape sequences must not hang the terminal.
        for _ in range(2):
            if not select.select([fd], [], [], 0.1)[0]:
                break
            value += os.read(fd, 1)
    return {b'\x1b[A': 'up', b'\x1bOA': 'up', b'\x1b[B': 'down', b'\x1bOB': 'down',
            b'\r': 'enter', b'\n': 'enter'}.get(value, value.decode('ascii', errors='ignore'))


def selection(key, index, count):
    """Pure keyboard transition, shared by numeric and arrow/Enter selection."""
    if key == 'up':
        return (index-1) % count, False
    if key == 'down':
        return (index+1) % count, False
    if key == 'enter':
        return index, True
    if key in tuple(str(i) for i in range(1, count+1)):
        return int(key)-1, True
    return index, False


def choose(console, title, items):
    index = 0
    def render():
        return Group(Text(title, style=terminal.ACCENT), Text('─'*40), Text(''),
            *(Text(f'{"❯" if i == index else " "} {i+1}  {label}',
                   style=terminal.ACCENT if i == index else '') for i, label in enumerate(items)),
            Text(f'\n↑ ↓ navigate   Enter select   1–{len(items)} quick select'))
    # Rich intentionally suppresses transient Live output on dumb/no-color terminals.
    # Keep those terminals usable with a plain, sequential menu instead.
    if not console.is_terminal or console.is_dumb_terminal:
        with keyboard() as fd:
            console.print(render())
            while True:
                index, selected = selection(read_key(fd), index, len(items))
                if selected:
                    return index
                console.print(render())
    with keyboard() as fd, Live(render(), console=console, auto_refresh=False, transient=True) as live:
        while True:
            index, selected = selection(read_key(fd), index, len(items))
            if selected:
                return index
            live.update(render(), refresh=True)


def invoke(config, console, command):
    code = cli.main(cli_args(config, command, plain=console.color_system is None))
    if code == 130:
        raise KeyboardInterrupt
    return code


def advanced(console, *, database=False):
    console.print('Exact commands remain preferable for scripted/reproducible work.', style=terminal.ACCENT)
    try:
        cli.main(['db', '--help'] if database else ['--help'])
    except SystemExit as exc:
        if exc.code != 0:
            raise
    console.print('Examples: rest-api-checker --env-file <private-file> db status\n'
                  '          rac preflight --json\n          rac evaluate list\n'
                  'Initialization, migration and imports are explicit administrative commands only.')


def database_menu(config, console):
    while True:
        item = choose(console, 'Database', ['Start / check database', 'Status', 'Version',
                      'Stop database', 'Advanced database commands', 'Back'])
        if item == 5:
            return
        if item == 0:
            console.print(terminal.table('Database', ('Setting', 'Value'), start_database(config, console).items()))
        elif item in (1, 2):
            invoke(config, console, ['db', 'status' if item == 1 else 'version'])
        elif item == 3:
            console.print(terminal.table('Database', ('Setting', 'Value'), stop_database(config).items()))
        else:
            advanced(console, database=True)


def experiments_menu(config, console):
    value, _ = dispatch(config, ['preflight'], console)
    while True:
        item = choose(console, 'Experiments', [f'Prompt Comparison — Gate B {value["status"]} (status only)',
                      'Sensitivity — Not available yet', 'Main Evaluation — Not available yet',
                      'Fabricated Demo', 'Back'])
        if item == 4:
            return
        if item == 0:
            show_gate(console, value)
            console.print('Real execution remains unavailable in the authoritative CLI. No experiment was dispatched.')
        elif item in (1, 2):
            console.print('Not available yet.')
        else:
            console.print('FABRICATED / TEST DATA\nNo real LLM inference will be performed.', style='yellow')
            if choose(console, 'Run isolated fabricated demo?', ['Cancel', 'Run fabricated demo']) == 1:
                invoke(config, console, ['experiment', 'demo'])


def identifier(prompt):
    value = input(prompt+' ID: ').strip()
    if not value.isdecimal() or not 1 <= int(value) <= 9223372036854775807:
        raise OperatorError('Enter a positive numeric record ID.')
    return value


def evaluation_menu(config, console):
    while True:
        item = choose(console, 'Evaluation', ['List reports', 'Inspect report', 'Export report', 'Back'])
        if item == 3:
            return
        command = ['evaluate', ('list', 'show', 'export')[item]]
        if item:
            command.append(identifier('Report'))
        if item == 2:
            path = input('New JSON output path (will not overwrite): ').strip()
            if not path:
                raise OperatorError('Output path is required.')
            command += ['--output', os.path.expanduser(path)]
        invoke(config, console, command)


def inspect_data(config, console, section):
    """Reuse the existing paginated SELECT-only web projections."""
    settings = credentials(config)
    page = 1
    while True:
        with closing(connect(settings, config.database)) as cn:
            try:
                queries = WebQueries(cn)
                value = queries.runs(page=page) if section == 'runs' else queries.data_list(
                    section if section in ('datasets', 'cases', 'references') else 'artifacts', page=page, kind=section)
            finally:
                cn.rollback()
        records = value['items']
        if records:
            console.print(terminal.table(section.title(), records[0].keys(), [r.values() for r in records]))
        console.print(f'Page {page}/{value["pages"]} · {value["total"]} records')
        if value['pages'] <= 1:
            return
        item = choose(console, 'Pages', ['Back', 'Next page', 'Previous page'])
        if item == 0:
            return
        page = min(page+1, value['pages']) if item == 1 else max(1, page-1)


def inspect_menu(config, console):
    sections = ('datasets', 'cases', 'references', 'prompts', 'models', 'experiments', 'runs')
    while True:
        item = choose(console, 'Inspect data', [s.title() for s in sections]+['Back'])
        if item == 7:
            return
        inspect_data(config, console, sections[item])


def launch(config, console):
    while True:
        item = choose(console, 'RestApiChecker', ['Database', 'Web UI', 'Preflight / Gate B',
                      'Experiments', 'Evaluation', 'Inspect data', 'Advanced CLI', 'Exit'])
        if item == 7:
            return 0
        try:
            if item == 0:
                database_menu(config, console)
            elif item == 1:
                web(config, console)
            elif item == 2:
                value, _ = dispatch(config, ['preflight'], console)
                show_gate(console, value)
            elif item == 3:
                experiments_menu(config, console)
            elif item == 4:
                evaluation_menu(config, console)
            elif item == 5:
                inspect_menu(config, console)
            else:
                advanced(console)
        except (ValueError, OSError, pyodbc.Error) as exc:
            message = sql_error(exc) if isinstance(exc, pyodbc.Error) else str(exc)
            console.print(terminal.clean(message), style='yellow')
        except EOFError:
            return 0
