"""Shared v2 operational presentation for real runs and memory-only simulation."""
from contextlib import nullcontext
import os
import time

from rich.console import Group
from rich.constrain import Constrain
from rich.live import Live
from rich.measure import Measurement
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.table import Table
from rich.text import Text

from . import terminal

MAX_WIDTH = 120


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
    return Panel(content, title=Text(title, style=terminal.ACCENT), border_style='dim',
                 padding=(0, 2), width=min(console.width, MAX_WIDTH)) if decorated(console) else content


def demo_notice():
    return Text('DEMO / SIMULATION\nNO MODEL CALLS · NO PREDICTION WRITES', style='yellow')


def value_text(value, style=''):
    return Text(terminal.clean(value), style=style, overflow='fold')


def field_grid(fields):
    """Two label/value pairs per row, shared by every compact TTY section."""
    table = Table.grid(expand=True, padding=(0, 1))
    for _ in range(2):
        table.add_column(no_wrap=True)
        table.add_column(ratio=1, overflow='fold')
    for i in range(0, len(fields), 2):
        cells = []
        for label, value in fields[i:i+2]:
            cells.extend([value_text(label), value if isinstance(value, Text) else value_text(value)])
        table.add_row(*(cells + [Text('')]*(4-len(cells))))
    return table


def failure_text(value, *, technical=False):
    return value_text(value, ('bold red' if technical else 'bold yellow') if value else 'dim')


def tty_plan(console, value):
    demo = value['mode'] == 'DEMO / SIMULATION'
    dataset = value['dataset']
    heading = demo_notice() if demo else value_text(value['mode'], 'bold')
    dataset_line = Text.assemble('Dataset  ', value_text(dataset['name'], 'bold'),
                                 value_text(' / '+dataset['version'], 'dim'))
    if dataset['id'] is not None:
        dataset_line.append(f" (ID {dataset['id']})", style='dim')
    fields = [('Cases', value['cases']), ('Models', len(value['models'])),
        ('Repetitions', value['repetitions']), ('Seeds', ', '.join(map(str, value['seeds']))),
        ('Planned executions', value_text(value['planned'], 'bold')), ('Output mode', value['output_mode']),
        ('Runtime', value['runtime']['ollama']['version']), ('Prompt', value['prompt']),
        ('Token limit', value['token_limit'])]
    if not demo:
        fields.extend((label, value[key]) for label, key in (
            ('Database', 'database'), ('Experiment', 'experiment_id'), ('Already complete', 'previously_complete'),
            ('Remaining', 'remaining'), ('Problematic', 'problematic'), ('To execute', 'to_execute'))
            if value.get(key) is not None)
    contents = [heading, Text(''), dataset_line, field_grid(fields), Text(''),
        Text.assemble('Models: ', value_text(' · '.join(m['name'] for m in value['models'])))]
    if not demo:
        contents.append(value_text('Identities (prefix): '+ ' · '.join(
            f"{m['name']} {short_hash(m['digest'])}" for m in value['models']), 'dim'))
        if value.get('problematic_run_ids'):
            contents.append(value_text('Problematic run IDs: '+', '.join(map(str, value['problematic_run_ids'])), 'bold yellow'))
        hashes = [f'{label}: {short_hash(value[key])}' for label, key in
                  [('P2 SHA-256', 'prompt_sha256'), ('Setup SHA-256', 'setup_sha256')] if value.get(key)]
        contents.append(value_text(' · '.join(hashes), 'dim'))
        contents.append(value_text('Preflight: '+value.get('preflight', 'Not performed (inspection only)'), 'dim'))
    console.print(section(console, 'Evaluation / execution plan', *contents))
    console.print()


class BlockBar:
    """One-row, width-aware full blocks; no pulse or background animation."""
    def __init__(self, fraction):
        self.fraction = fraction

    def __rich_measure__(self, console, options):
        return Measurement(1, options.max_width)

    def __rich_console__(self, console, options):
        width = options.max_width
        complete = min(width, max(0, int(width*self.fraction)))
        yield Text.assemble(('█'*complete, terminal.ACCENT), ('░'*(width-complete), 'dim'))


class BlockBarColumn(BarColumn):
    def render(self, task):
        return BlockBar(task.completed/task.total if task.total else 0)


def plan(console, value):
    if decorated(console):
        tty_plan(console, value)
        return
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
        self.progress = Progress(TextColumn('Overall'), BlockBarColumn(bar_width=None),
            TextColumn('{task.completed:.0f} / {task.total:.0f}', style='bold'),
            TextColumn('{task.percentage:>5.1f}%', style='bold'), auto_refresh=False, expand=True)
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
        state_label = {'current': 'Running', 'progress': 'Execution settled', 'start': 'Ready'}.get(self.message, self.message)
        if self.summary['mode'] == 'DEMO / SIMULATION' and state_label != 'SIMULATED':
            state_label = 'SIMULATED · '+state_label
        current = field_grid([
            ('Case', value_text(c.get('case', '—'), 'bold')), ('API', c.get('api', '—')),
            ('Model', value_text(c.get('model', '—'), 'bold')),
            ('Repetition', value_text(f"{c.get('repetition', '—')} / {self.summary['repetitions']}", 'bold')),
            ('Seed', value_text(c.get('seed', '—'), 'bold')), ('State', value_text(state_label, 'bold'))])
        counters = field_grid([
            ('✓ Parser-valid', s['counts'].get('valid', 0)),
            ('! Parser failures', failure_text(s['counts'].get('parser_failure', 0))),
            ('✕ Technical failures', failure_text(s['counts'].get('technical_failure', 0), technical=True)),
            ('Remaining', self.summary['planned']-s['completed'])])
        yield Constrain(Group(self.progress, value_text('◷ '+self.lines()[4], 'dim'), Text(''),
            section(console, '▶ Current execution', current), Text(''),
            section(console, 'Result counters', counters)), MAX_WIDTH)

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
    if decorated(console):
        tty_summary(console, result)
        return
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


def tty_summary(console, result):
    value = result['plan']
    demo = result.get('simulated')
    counts = result.get('counts_now')
    fields = [('Status', value_text(result['status'], 'bold'))]
    if demo:
        fields.append(('Simulated steps', value_text(result['simulated_steps'], 'bold')))
    else:
        fields.extend([('Planned', value['planned']), ('Executed now', result.get('executed_now', 0)),
            ('Completed total', result.get('completed', value['previously_complete'])),
            ('Previously complete', value['previously_complete'])])
    fields.extend([
        ('✓ Parser-valid', counts['valid'] if counts is not None else 'N/A'),
        ('! Parser failures', failure_text(counts['parser_failure']) if counts is not None else 'N/A'),
        ('✕ Technical failures', failure_text(counts['technical_failure'], technical=True) if counts is not None else 'N/A')])
    if demo:
        fields.extend([('Real model calls', result['model_calls']), ('Prediction writes', result['prediction_writes'])])
    else:
        fields.append(('Unsettled problems', failure_text(result.get('technical_problems', 0), technical=True)))
    fields.extend([('◷ Elapsed', duration(result.get('elapsed_seconds'))),
        ('Average simulated step' if demo else 'Average execution',
         f"{result['average_execution_seconds']:.2f} s" if result.get('average_execution_seconds') is not None else 'N/A')])
    contents = [field_grid(fields)]
    if demo:
        contents.append(value_text('SIMULATED · NO MODEL CALLS · NO PREDICTION WRITES', 'dim'))
    else:
        contents.append(value_text(f"{value['dataset']['name']} / {value['dataset']['version']} · "
            f"{value['output_mode']} · Ollama {value['runtime']['ollama']['version']}", 'dim'))
        contents.append(value_text(f"P2 SHA-256: {short_hash(value['prompt_sha256'])} · "
            f"Setup SHA-256: {short_hash(value['setup_sha256'])}", 'dim'))
    if result.get('message'):
        contents.append(value_text(result['message']))
    if result.get('exit_code') and not demo:
        contents.append(value_text('Inspect batch-status and attempts; reconcile ambiguous attempts before --resume.', 'dim'))
    console.print()
    console.print(section(console, 'Final summary', *contents))
