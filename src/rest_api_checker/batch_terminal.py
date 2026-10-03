"""Shared v2 operational presentation for real runs and memory-only simulation."""
from contextlib import nullcontext
import os
import time

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text

from . import terminal


def duration(seconds):
    if seconds is None:
        return 'N/A'
    value = int(seconds)
    return f'{value//3600:02}:{value//60%60:02}:{value%60:02}'


def short_hash(value):
    return str(value)[:16]+'…' if value and len(str(value)) == 64 else value


def decorated(console):
    return console.is_terminal and 'NO_COLOR' not in os.environ


def section(console, title, *contents):
    content = Group(*contents)
    return Panel(content, title=Text(title, style=terminal.ACCENT), border_style='dim', padding=(0, 1)) if decorated(console) else content


def demo_notice():
    return Text('DEMO / SIMULATION\nNO MODEL CALLS · NO PREDICTION WRITES', style='yellow')


def plan(console, value):
    heading = demo_notice() if value['mode'] == 'DEMO / SIMULATION' else Text(terminal.clean(value['mode']), style=terminal.ACCENT)
    dataset = value['dataset']
    fields = terminal.table('Execution plan', ('Field', 'Resolved value'), [
        ('Dataset', f"{dataset['name']} / {dataset['version']} (ID {dataset['id']})"),
        ('Database', value['database']), ('Experiment', value['experiment_id']),
        ('Cases', value['cases']), ('Models', len(value['models'])),
        ('Repetitions', value['repetitions']), ('Seeds', ', '.join(map(str, value['seeds']))),
        ('Planned executions', value['planned']), ('Already complete', value['previously_complete']),
        ('Remaining', value['remaining']), ('Problematic', value['problematic']),
        ('Problematic run IDs', ', '.join(map(str, value.get('problematic_run_ids', []))) or 'None'),
        ('To execute', value['to_execute']), ('Output mode', value['output_mode']),
        ('Runtime / Ollama', value['runtime']['ollama']['version']),
        ('Prompt', value['prompt']), ('Prompt SHA-256 prefix', short_hash(value['prompt_sha256'])),
        ('Setup SHA-256 prefix', short_hash(value['setup_sha256'])), ('Token limit', value['token_limit']),
        ('Preflight', value.get('preflight', 'Not performed (inspection/simulation)'))])
    models = terminal.table('Models', ('Model', 'Digest (prefix; full in JSON)'),
                            [(m['name'], short_hash(m['digest'])) for m in value['models']])
    console.print(section(console, 'Evaluation / execution plan', heading, fields, models))


class Display:
    def __init__(self, console, summary, *, enabled=True):
        self.console, self.summary, self.enabled = console, summary, enabled
        self.started = time.monotonic()
        self.current_started = None
        self.current, self.state = {}, None
        self.message = 'Preparing'
        self.live_enabled = enabled and decorated(console)
        self.progress = Progress(TextColumn('Overall'), BarColumn(bar_width=None, complete_style=terminal.ACCENT,
            finished_style=terminal.ACCENT), TextColumn('{task.completed:.0f} / {task.total:.0f}'),
            TextColumn('{task.percentage:>5.1f}%'), auto_refresh=False, expand=True)
        self.task = self.progress.add_task('Executions', total=summary['planned'], completed=summary['previously_complete'])
        self.live = Live(self, console=console, refresh_per_second=2, transient=False) if self.live_enabled else nullcontext()

    def __enter__(self):
        self.live.__enter__()
        return self

    def __exit__(self, *args):
        return self.live.__exit__(*args)

    def lines(self):
        s = self.state or dict(completed=self.summary['previously_complete'], counts={})
        elapsed = time.monotonic()-self.started
        complete, total = s['completed'], self.summary['planned']
        now = complete-self.summary['previously_complete']
        eta = elapsed/now*(total-complete) if now else None
        c = self.current
        return [self.summary['mode'],
            f"{complete}/{total} complete ({100*complete/total if total else 0:.1f}%) · {self.message}",
            f"Case {c.get('case', '—')} · API {c.get('api', '—')} · {c.get('model', '—')}",
            f"Repetition {c.get('repetition', '—')} · Seed {c.get('seed', '—')}",
            f"Elapsed {duration(elapsed)} · Current {duration(time.monotonic()-self.current_started if self.current_started else None)} · ETA (estimate) {duration(eta)}",
            f"Parser-valid {s['counts'].get('valid', 0)} · Parser failures {s['counts'].get('parser_failure', 0)} · Technical failures {s['counts'].get('technical_failure', 0)}"]

    def __rich_console__(self, console, options):
        if not self.live_enabled:
            yield Group(*(Text(terminal.clean(line)) for line in self.lines()))
            return
        s = self.state or dict(completed=self.summary['previously_complete'], counts={})
        self.progress.update(self.task, completed=s['completed'])
        c = self.current
        heading = demo_notice() if self.summary['mode'] == 'DEMO / SIMULATION' else Text(terminal.clean(self.summary['mode']), style=terminal.ACCENT)
        current = terminal.table('', ('Case ID', 'API', 'Model'),
            [[c.get('case', '—'), c.get('api', '—'), c.get('model', '—')]])
        state_label = {'current': 'Running', 'progress': 'Execution settled', 'start': 'Ready'}.get(self.message, self.message)
        details = terminal.table('', ('Repetition', 'Seed', 'Operational state'),
            [[c.get('repetition', '—'), c.get('seed', '—'), state_label]])
        counters = terminal.table('', ('Parser-valid', 'Parser failures', 'Technical failures', 'Remaining'),
            [[s['counts'].get('valid', 0), s['counts'].get('parser_failure', 0),
              s['counts'].get('technical_failure', 0), self.summary['planned']-s['completed']]])
        yield Group(heading, self.progress, Text(terminal.clean(self.lines()[4])),
            section(console, 'Current execution', current, details),
            section(console, 'Result counters', counters))

    def event(self, value):
        if 'state' in value:
            self.state = value['state']
        if 'current' in value:
            self.current = value['current']
            self.current_started = time.monotonic()
        self.message = value.get('status', value.get('message', value['event']))
        if not self.enabled or self.live_enabled:
            return
        if value['event'] == 'current':
            self.console.print(terminal.clean(' · '.join(self.lines()[2:4])))
        elif value['event'] in ('start', 'progress', 'finish', 'interrupt_requested'):
            lines = self.lines()
            self.console.print(terminal.clean(' · '.join([lines[1], lines[4], lines[5]])))


def summary(console, result):
    value = result['plan']
    title = 'DEMO / SIMULATION — simulated operational events' if result.get('simulated') else 'Evaluation v2 Main — execution summary'
    counts = result.get('counts_now')
    execution_counts = ([('Real executions', result.get('executed_now', 0)),
        ('Simulated steps', result['simulated_steps']), ('Model calls', result['model_calls']),
        ('Prediction writes', result['prediction_writes'])] if result.get('simulated') else [
        ('Executed now', result.get('executed_now', 0)),
        ('Completed total', result.get('completed', value['previously_complete']))])
    fields = terminal.table(title, ('Field', 'Value'), [
        ('Status', result['status']), ('Dataset', f"{value['dataset']['name']} / {value['dataset']['version']}"),
        ('Cases / models / repetitions', f"{value['cases']} / {len(value['models'])} / {value['repetitions']}"),
        ('Planned', value['planned']), ('Previously complete', value['previously_complete']),
        *execution_counts,
        ('Parser-valid now', counts['valid'] if counts is not None else 'N/A'),
        ('Parser failures now', counts['parser_failure'] if counts is not None else 'N/A'),
        ('Technical failures now (settled)', counts['technical_failure'] if counts is not None else 'N/A'),
        ('Technical problems / unsettled', result.get('technical_problems', 0)),
        ('Elapsed', duration(result.get('elapsed_seconds'))),
        ('Average execution (estimate)', f"{result['average_execution_seconds']:.2f} s" if result.get('average_execution_seconds') is not None else 'N/A'),
        ('Output mode', value['output_mode']), ('Runtime / Ollama', value['runtime']['ollama']['version']),
        ('Prompt SHA-256 prefix', short_hash(value['prompt_sha256'])), ('Setup SHA-256 prefix', short_hash(value['setup_sha256']))])
    contents = [demo_notice(), fields] if result.get('simulated') else [fields]
    console.print(section(console, 'Final summary', *contents))
    if result.get('message'):
        console.print(terminal.clean(result['message']))
    if result.get('exit_code') and not result.get('simulated'):
        console.print('Inspect experiment batch-status and inspect attempts; reconcile ambiguous attempts before --resume.')
