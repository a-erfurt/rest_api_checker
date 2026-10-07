"""Compact summaries of stored results; invalid outputs never become predictions."""
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import terminal

CATEGORIES = ('c1', 'c2', 'c3')
LABELS = ('C1 Status', 'C2 Media Type', 'C3 Body Schema')


def vector(value):
    return ''.join({'PASS': 'P', 'FAIL': 'F', 'NOT_APPLICABLE': 'N'}.get(value.get(c), '?')
                   for c in CATEGORIES) if value else '—'


def usable(detail):
    return detail['run'].get('result') == 'valid' and detail.get('prediction') is not None


def correct(detail):
    reference = detail.get('reference') or {}
    return usable(detail) and all(reference.get(c) in ('PASS', 'FAIL', 'NOT_APPLICABLE')
                                 and detail['prediction'].get(c) == reference[c] for c in CATEGORIES)


def _text(value, style=''):
    return Text(terminal.clean(value), style=style)


def _duration(detail):
    durations = [attempt['duration_ms'] for attempt in detail.get('attempts', [])
                 if attempt.get('duration_ms') is not None]
    return f'{sum(durations)/1000:.1f} s' if durations else '—'


def _name(detail, key):
    value = detail.get(key) or detail['run'].get(key) or ('Stored case' if key == 'case' else 'Stored model')
    if key == 'model':
        from .live_presenter import model_label
        return model_label({'name': value})
    return value


def _verdict(value):
    label = 'N/A' if value == 'NOT_APPLICABLE' else value or 'Unavailable'
    return _text(label, {'PASS': 'green', 'FAIL': 'red', 'NOT_APPLICABLE': 'dim'}.get(value, 'dim'))


def _outcome(detail):
    if not usable(detail):
        return '— NO PREDICTION', 'yellow'
    if not detail.get('reference') or '?' in vector(detail['reference']):
        return '— UNAVAILABLE', 'yellow'
    return ('✓ CORRECT', 'green') if correct(detail) else ('✗ INCORRECT', 'red')


def _table(columns):
    table = Table(box=box.SIMPLE, header_style='bold cyan', padding=(0, 1), expand=False)
    for column in columns:
        table.add_column(column)
    return table


def show(console, detail):
    """Render the default result without reasons, identifiers or recovery paths."""
    run, reference = detail['run'], detail.get('reference') or {}
    prediction = detail.get('prediction') if usable(detail) else None
    status = run.get('result')
    heading, heading_style = (('✓ Run completed', 'bold green') if status in ('valid', 'parser_failure') else
                              ('✗ Run failed', 'bold red') if status == 'technical_failure' else
                              ('⚠ Run pending / interrupted', 'bold yellow'))
    title = _text(heading, heading_style)
    if _duration(detail) != '—':
        title.append('   ' + _duration(detail), style='dim')
    names = Text.assemble(('Case: ', 'bold'), _text(_name(detail, 'case')),
                          ('    Model: ', 'bold'), _text(_name(detail, 'model')))
    comparison = _table(('Check', 'Reference', 'Prediction', ''))
    for category, label in zip(CATEGORIES, LABELS):
        known = reference.get(category) in ('PASS', 'FAIL', 'NOT_APPLICABLE')
        match = prediction is not None and known and prediction.get(category) == reference[category]
        comparison.add_row(_text(label), _verdict(reference.get(category)),
                           _verdict(prediction.get(category)) if prediction is not None else _text('—', 'dim'),
                           _text('✓' if match else '✗', 'green' if match else 'red')
                           if prediction is not None and known else _text('—', 'dim'))
    vectors = Text.assemble(('Reference: ', 'bold'), vector(reference),
                            ('   Prediction: ', 'bold'), vector(prediction))
    outcome, style = _outcome(detail)
    footer = Text.assemble(('Overall: ', 'bold'), (outcome, style), ('   Parser: ', 'bold'),
                           ('✓ VALID', 'green') if prediction is not None else ('✗ NO USABLE OUTPUT', 'red'))
    parts = [names, comparison, vectors, footer]
    if prediction is None:
        parts.append(_text('No prediction was inferred.', 'dim'))
    console.print(Panel(Group(*parts), title=title, title_align='left', border_style='cyan',
                        padding=(0, 1), width=min(console.width, 96)))


def show_details(console, detail):
    """Expose stored explanations and technical provenance only on request."""
    show(console, detail)
    prediction = detail.get('prediction') if usable(detail) else None
    if prediction is not None:
        console.print('\nCategory explanations', style='bold cyan')
        for category, label in zip(CATEGORIES, LABELS):
            console.print(_text(label, 'bold'))
            console.print(_text(prediction.get(category + '_reason') or 'No stored explanation.'))
    rows = []
    run = detail['run']
    for key, label in (('id', 'Run ID'), ('experiment_id', 'Experiment ID'),
                       ('dataset_case_id', 'Dataset case ID'), ('reference_id', 'Reference ID'),
                       ('repetition', 'Repetition'), ('seed', 'Seed'), ('result', 'Stored status')):
        if run.get(key) is not None:
            rows.append((label, run[key]))
    for key, label in (('prompt', 'Prompt'), ('spool', 'Recovery directory')):
        value = detail.get(key, run.get(key))
        if value is not None:
            rows.append((label, value))
    for key, value in (detail.get('technical') or {}).items():
        if value is not None:
            rows.append((key, value))
    table = _table(('Details', 'Value'))
    for label, value in rows:
        table.add_row(_text(label, 'bold'), _text(value))
    console.print(table)
    for attempt in detail.get('attempts', []):
        table = _table(('Attempt details', 'Value'))
        for key, label in (('attempt', 'Attempt'), ('id', 'Attempt ID'),
                           ('response_file_id', 'Raw response file ID'),
                           ('diagnostics_file_id', 'Diagnostics file ID'), ('result', 'Stored status'),
                           ('duration_ms', 'Duration (ms)'), ('error_kind', 'Error kind'),
                           ('error_message', 'Error')):
            if attempt.get(key) is not None:
                table.add_row(_text(label, 'bold'), _text(attempt[key]))
        console.print(table)


def repetitions(console, details):
    """Show one bounded table per model instead of repeated full result panels."""
    if len(details) < 2:
        return
    groups = {}
    for detail in details:
        groups.setdefault(_name(detail, 'model'), []).append(detail)
    for model, group in groups.items():
        table = _table(('#', 'Reference', 'Prediction', 'Overall', 'Parser', 'Time'))
        for detail in group:
            prediction = detail.get('prediction') if usable(detail) else None
            outcome, style = _outcome(detail)
            table.add_row(_text(detail['run'].get('repetition', '—')), _text(vector(detail.get('reference'))),
                          _text(vector(prediction)), _text(outcome, style),
                          _text('✓ VALID', 'green') if prediction is not None else _text('✗ NO OUTPUT', 'red'),
                          _text(_duration(detail)))
        valid = [detail for detail in group if usable(detail)]
        vectors = [vector(detail['prediction']) for detail in valid]
        agreement = ('vectors differ' if len(set(vectors)) > 1 else 'vectors identical' if len(vectors) > 1
                     else 'one usable vector' if vectors else 'no usable vectors')
        summary = _text(f'Usable output {len(valid)}/{len(group)} · correct '
                        f'{sum(correct(detail) for detail in group)}/{len(group)} · {agreement}')
        case_names = ', '.join(dict.fromkeys(str(_name(detail, 'case')) for detail in group))
        console.print(Panel(Group(_text('Case: ' + case_names), table, summary),
                            title=_text('Repetitions · ' + str(model), 'bold cyan'), title_align='left',
                            border_style='cyan', padding=(0, 1), width=min(console.width, 96)))
