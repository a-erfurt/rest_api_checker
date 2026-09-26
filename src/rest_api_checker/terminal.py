"""Restrained human presentation; machine mode never writes here."""
from contextlib import nullcontext
import json
import os
import time

from rich.console import Console, Group
from rich.live import Live
from rich.progress import Progress, BarColumn, TextColumn
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

ACCENT = 'cyan'


def clean(value):
    """Never interpret provider markup or terminal control sequences."""
    return ''.join(c if c in '\n\t' or ord(c)>=32 and ord(c)!=127 else f'\\x{ord(c):02x}' for c in str(value))


def console(*, plain=False, file=None):
    no_color = plain or 'NO_COLOR' in os.environ
    return Console(file=file,force_terminal=False if no_color else None,color_system=None if no_color else 'auto',
                   markup=False,highlight=False)


def table(title, columns, records):
    t = Table(title=clean(title),title_style=ACCENT,header_style=ACCENT,box=None,padding=(0,1))
    for column in columns:
        t.add_column(column)
    for record in records:
        t.add_row(*(Text(clean(v)) for v in record))
    return t


def metric(value, verbose=False):
    if value['value'] is None:
        return f'N/A ({value["numerator"]}/{value["denominator"]})'
    text = f'{value["numerator"]}/{value["denominator"]}'
    return text + (f' ({100*value["numerator"]/value["denominator"]:.2f}%)' if verbose else '')


def report(console, value, verbose=False):
    if value['fabricated']:
        console.print('FABRICATED / TEST DATA — no study prompt winner',style='yellow')
    names = ('Score','Robust','StableCorrect','Reliability','FullCase')
    console.print(table('Prompt comparison',('Prompt','Score','Robust','Stable','Reliable','Full case'),
        [[p,*(metric(value['metrics'][p][c],verbose) for c in names)] for p in value['ranking']]))
    console.print(f'Selected prompt{ " (fabricated demo only)" if value["fabricated"] else ""}: {value["selected_prompt"]}',style=ACCENT)
    console.print(f'Selection decided by: {value["selection_decided_by"]}')
    for step in value['tie_break_trace']:
        console.print(f'  {step["criterion"]}: '+', '.join(f'{p}={v}' for p,v in step['values'].items())+' → '+', '.join(step['remaining']))
    for p in value['ranking']:
        console.print(table(f'{p} · model × category',('Model','C1','C2','C3'),
            [[m,*(metric(v,verbose) for v in cells.values())] for m,cells in value['metrics'][p]['cells'].items()]))
        console.print(table(f'{p} · terminal outcomes',('Model','Valid','Parser','Technical'),
            [[m,*(str(d['outcomes'].get(k,0)) for k in ('valid','parser_failure','technical_failure'))]
             for m,d in value['diagnostics'][p].items()]))
        if verbose:
            console.print(table(f'{p} · per repetition correctness',('Model','Repetition','C1','C2','C3'),
                [[m,rep,*(metric(values[c],True) for c in ('c1','c2','c3'))]
                 for m,d in value['diagnostics'][p].items() for rep,values in d['per_repetition'].items()]))
            console.print(table(f'{p} · valid-output confusion',('Model','Category','Reference','PASS','FAIL','NOT_APPLICABLE'),
                [[m,c.upper(),ref,*(counts[v] for v in ('PASS','FAIL','NOT_APPLICABLE'))]
                 for m,d in value['diagnostics'][p].items() for c,matrix in d['confusion'].items() for ref,counts in matrix.items()]))
            console.print(table(f'{p} · repeat disagreement (valid triples only)',('Model','Coverage','Vector','C1','C2','C3'),
                [[m,metric(d['valid_triple_coverage'],True),*(metric(d['repeat_disagreement'][c],True)
                 for c in ('vector','c1','c2','c3'))] for m,d in value['diagnostics'][p].items()]))
            console.print(table(f'{p} · valid-only correctness',('Model','Valid coverage','C1','C2','C3'),
                [[m,metric(d['valid_coverage'],True),*(metric(d['valid_only'][c],True) for c in ('c1','c2','c3'))]
                 for m,d in value['diagnostics'][p].items()]))


def inspection(console, value, verbose=False):
    run = value['run']
    console.print(table('Run',('Field','Value'),[(k,v) for k,v in dict(ID=run['id'],Case=value['case'],
        Model=value['model'],Prompt=value['prompt'],Repetition=run['repetition'],Seed=run['seed'],Status=run['result'] or 'PENDING').items()]))
    pred = value['prediction']
    console.print(table('Reference and prediction',('Category','Reference','Prediction','Correctness'),
        [(c.upper(),value['reference'][c],pred[c] if pred else 'No semantic verdict',
          'correct' if value['correctness'][c] else 'incorrect' if pred else 'N/A') for c in ('c1','c2','c3')]))
    if pred:
        for c in ('c1','c2','c3'):
            console.print(Text(clean(f'{c.upper()} reason: {pred[c+"_reason"]}')))
    console.print(table('Attempts',('Attempt','Status','Duration ms','Error'),
        [(a['attempt'],a['result'] or 'NEEDS RECONCILIATION',a['duration_ms'] if a['duration_ms'] is not None else 'N/A',
          a['error_message'] or a['error_kind'] or '—') for a in value['attempts']]))
    if verbose and 'raw' in value:
        console.print(Text(clean(json.dumps(value['raw'],ensure_ascii=True,indent=2))))


class RunDisplay:
    """Only a compact live panel refreshes; plain mode emits bounded milestones."""
    def __init__(self, console, *, enabled=True):
        self.console, self.enabled = console, enabled
        self.live_enabled = enabled and console.is_terminal and 'NO_COLOR' not in os.environ
        self.started = time.monotonic()
        self.state, self.current, self.message = None, {}, 'Preparing'
        self.last_bucket = -1
        self.last_model = None
        self.progress = Progress(TextColumn('Progress'),BarColumn(complete_style=ACCENT),
            TextColumn('{task.completed:.0f} / {task.total:.0f}  {task.percentage:.0f}%'),auto_refresh=False)
        self.task = self.progress.add_task('Logical runs',total=324)
        self.spinner = Spinner('dots',text='Waiting for current attempt',style=ACCENT)
        self.live = Live(self,console=console,refresh_per_second=4,transient=False) if self.live_enabled else nullcontext()

    def __enter__(self):
        self.live.__enter__()
        return self

    def __exit__(self,*args):
        return self.live.__exit__(*args)

    def __rich_console__(self, console, options):
        elapsed = int(time.monotonic()-self.started)
        s = self.state or dict(planned=324,completed=0,pending=324,counts={})
        yield Group(Text('Prompt comparison'+(' · FABRICATED / TEST DATA' if s.get('fabricated') else ''),style=ACCENT),
            self.progress,Text(f'Elapsed  {elapsed//3600:02}:{elapsed//60%60:02}:{elapsed%60:02}'),self.spinner,
            table('Current',('Model','Prompt','Case','Repetition','Attempt'),[[self.current.get('model','—'),
                self.current.get('prompt','—'),self.current.get('case','—'),f'{self.current.get("repetition","—")} / 3',
                f'{self.current.get("attempt","—")} / 2']]),
            table('Results',('Valid','Parser failures','Technical failures','Pending'),[[s['counts'].get('valid',0),
                s['counts'].get('parser_failure',0),s['counts'].get('technical_failure',0),s['pending']]]),Text(clean(self.message)))

    def event(self,event):
        if not self.enabled:
            return
        kind = event['event']
        if 'state' in event:
            self.state = event['state']
            self.progress.update(self.task,total=self.state['planned'],completed=self.state['completed'])
        if 'current' in event:
            self.current = event['current']
        if kind in ('retry','interrupt_requested'):
            self.message = event['message']
            self.console.print(clean(self.message),style='yellow')
        elif kind=='current':
            self.message = 'Running; awaiting provider response (timeout 300 seconds per attempt)'
            if not self.live_enabled and self.current['model']!=self.last_model:
                self.last_model = self.current['model']
                self.console.print('Current: '+clean(f'{self.current["model"]} · {self.current["prompt"]} · '
                    f'{self.current["case"]} · repetition {self.current["repetition"]}/3 · attempt {self.current["attempt"]}/2'))
        if kind=='finish':
            self.message = event['status']
            self.spinner.update(text=event['status'])
            if event['message']:
                self.console.print(clean(event['message']),style='yellow')
            if event['exit_code']:
                self.console.print(f'Experiment incomplete. Inspect: {event["inspect"]}. Resume: {event["resume"]}',style='yellow')
        if not self.live_enabled and self.state:
            bucket = self.state['completed']//36
            if kind in ('start','finish') or bucket!=self.last_bucket:
                self.last_bucket = bucket
                s = self.state
                elapsed = int(time.monotonic()-self.started)
                percent = 100*s['completed']/s['planned'] if s['planned'] else 0
                self.console.print(f'{s["completed"]}/{s["planned"]} logical runs ({percent:.0f}%); elapsed {elapsed}s; '
                    f'valid={s["counts"]["valid"]} parser={s["counts"]["parser_failure"]} '
                    f'technical={s["counts"]["technical_failure"]} pending={s["pending"]}')
