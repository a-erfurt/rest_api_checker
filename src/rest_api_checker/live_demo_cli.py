"""Interactive selection and presentation over the existing live-demo runner."""
from contextlib import nullcontext
from pathlib import Path
import sys
from urllib.parse import urlsplit
import uuid

from . import terminal
from .persistence.database import require


def add_arguments(node):
    node.add_argument('--case-id', type=int, help='Existing eligible development dataset membership ID')
    node.add_argument('--dataset-id', type=int, help='Optional development dataset filter; never Dataset 3')
    node.add_argument('--model-id', type=int, action='append', help='Stored approved model ID; repeat for multiple models')
    node.add_argument('--repetitions', type=int, choices=(1, 2, 3), help='Runs per selected model (default: 1)')
    node.add_argument('--runtime-binding', type=Path, help='Exact qualified runtime-binding.json; no implicit latest')
    node.add_argument('--spool', type=Path, help='New durable demo directory; defaults to a unique local state directory')
    node.add_argument('--ui-url', default='http://127.0.0.1:8000', help='Existing Web UI base URL for result links')
    mode = node.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='Offline read-only plan: no runtime contact, writes or generation')
    mode.add_argument('--yes', action='store_true', help='Confirm explicit --case-id and --model-id selection without a prompt')


def _choose(console, title, items, label, read, *, multiple=False, explanation='', details=None, actions=None):
    from .interactive_menu import choose
    require(items, 'No eligible '+title.lower()+'.')
    return choose(console, title, items, label, read, multiple=multiple,
                  explanation=explanation, details=details, actions=actions)


def _unique(items, key):
    return list({item[key]: item for item in items}.values())


def _ui_url(value):
    target = urlsplit(value)
    require(target.scheme in ('http', 'https') and target.hostname and not target.query
            and not target.fragment and target.username is None and target.password is None,
            '--ui-url must be an HTTP(S) base URL without credentials, query or fragment.')
    return value.rstrip('/')


class _OtherCaseSet(Exception):
    pass


def _select_interactive_case(repo, data, cases, console, read, dataset_id=None):
    from .interactive_menu import Back
    from .interactive_evidence import show_case_details
    from .live_presenter import (CASE_TYPES, describe_case, filter_cases,
                                 operation_label, service_name)
    sets = _unique(cases, 'dataset_id')
    preferred = data.get('default_dataset_id')
    current = next((r for r in sets if r['dataset_id'] == (dataset_id or preferred)), sets[0])

    def other_sets():
        raise _OtherCaseSet

    while True:
        label = current.get('case_set_label') or current['dataset_name']
        suffix = ' (default)' if current['dataset_id'] == preferred else ''
        console.print(terminal.clean('Case set: '+label+suffix), style='dim')
        members = [row for row in cases if row['dataset_id'] == current['dataset_id']]
        try:
            service = _choose(console, 'Select service', _unique(members, 'service_id'),
                service_name, read, actions={'s': ('Other case sets', other_sets)} if len(sets)>1 else None)
        except _OtherCaseSet:
            try:
                current = _choose(console, 'Choose case set', sets,
                    lambda r: (r.get('case_set_label') or r['dataset_name'])+' · '+r['dataset_name']
                              + (' · '+str(r['dataset_version']) if r.get('dataset_version') else ''), read)
            except Back:
                pass
            continue
        while True:
            service_cases = [row for row in members if row['service_id'] == service['service_id']]
            try:
                operation = _choose(console, 'Select operation', _unique(service_cases, 'operation_id'),
                                    operation_label, read)
            except Back:
                break
            operation_cases = [row for row in service_cases if row['operation_id'] == operation['operation_id']]
            while True:
                try:
                    kind = _choose(console, 'Choose case type', CASE_TYPES,
                        lambda k: k[1]+'\n'+k[2], read)
                except Back:
                    break
                selected_cases = filter_cases(operation_cases, kind[0])
                if not selected_cases:
                    console.print('No cases of this type in this case set.', style='yellow')
                    continue
                def case_label(row):
                    description = describe_case(row)
                    return (f"{row['case_code']}   {description['title']}   {description['reference_vector']}"
                            f"\n{description['description']}")
                try:
                    return _choose(console, 'Select case', selected_cases, case_label, read,
                        details=lambda row: show_case_details(repo, row, console, read))
                except Back:
                    continue


def _selection(repo, args, console, read, interactive):
    from . import live_demo
    from .live_presenter import describe_case, service_label, operation_label, model_label
    adhoc = getattr(args, "adhoc", False)
    explicit = args.case_id is not None and bool(args.model_id)
    require(not args.yes or explicit, '--yes requires explicit --case-id and at least one --model-id.')
    require(interactive or explicit,
            'Non-interactive demo needs --case-id and --model-id. Use --dry-run to preview or --yes to execute.')
    require(interactive or args.dry_run or args.yes,
            'Non-interactive execution requires --yes; use --dry-run for a read-only preview.')
    data = live_demo.catalog(repo, adhoc=True) if adhoc else live_demo.catalog(repo)
    cases = [row for row in data['cases'] if args.dataset_id is None or row['dataset_id'] == args.dataset_id]
    require(cases, 'No referenced cases are available for this case set.' if adhoc else
            'No eligible development cases for this selection. Evaluation datasets and Dataset 3 are excluded; inspect dataset list/cases.')
    require(data['models'], 'No stored approved models are available; inspect dataset inventory.')
    if args.case_id is not None:
        selected = next((row for row in cases if row['id'] == args.case_id), None)
        require(selected is not None, 'Case membership is unavailable or protected. Choose an eligible development membership ID.')
    elif adhoc:
        selected = _select_interactive_case(repo, data, cases, console, read, args.dataset_id)
    else:
        service = _choose(console, 'Select service', _unique(cases, 'service_id'), service_label, read,
            explanation='A service is the API system whose stored response and OpenAPI contract you want to inspect.')
        candidates = [row for row in cases if row['service_id'] == service['service_id']]
        operation = _choose(console, 'Select operation', _unique(candidates, 'operation_id'),
                            operation_label, read,
                            explanation='An operation is the concrete REST endpoint whose documented response contract will be used.')
        candidates = [row for row in candidates if row['operation_id'] == operation['operation_id']]
        def case_label(row):
            description = describe_case(row)
            return (f"{row['case_code']} — {description['title']}\n{description['description']}\n"
                    f"Reference: {description['reference_vector']} ({description['reference_text']})")
        def case_details(row):
            description = describe_case(row)
            console.print(terminal.clean(case_label(row)))
            for line in description['details']:
                console.print(terminal.clean(line))
        selected = _choose(console, 'Select case', candidates, case_label, read,
            explanation='Choose one stored response. C1 checks status, C2 media type and C3 body schema. '
                        'P = PASS, F = FAIL, N = not applicable in the stored reference.', details=case_details)
    if args.model_id:
        require(len(set(args.model_id)) == len(args.model_id), 'Duplicate --model-id selections are not allowed.')
        models = [next((row for row in data['models'] if row['id'] == model_id), None) for model_id in args.model_id]
        require(all(model is not None for model in models), 'Selected model is unavailable or unapproved; inspect dataset inventory.')
    else:
        if adhoc:
            from .live_adhoc_runtime import model_availability
            availability = model_availability()
        else:
            availability = {}
        chosen = _choose(console, 'Select model', data['models'],
            lambda row: model_label(row)+(' — '+availability.get(row['name'], 'not installed') if adhoc and availability is not None else ''),
            read, multiple=not adhoc,
            explanation=('Availability could not be checked.' if adhoc and availability is None else ''))
        models = [chosen] if adhoc else chosen
    repetitions = args.repetitions
    if repetitions is None:
        repetitions = 1
        if interactive and not args.yes:
            console.print('Repeat the same case/model configuration. For a quick check, 1 is enough.', style='dim')
            while True:
                value = read('Repetitions per model [1]: ').strip() or '1'
                if value.lower() in ('q', 'back'):
                    from .interactive_menu import Back
                    raise Back
                if value in ('1', '2', '3'):
                    repetitions = int(value)
                    break
                console.print('Enter 1, 2 or 3.')
    if adhoc:
        return selected, models, repetitions, None
    runtime = args.runtime_binding
    if runtime is None:
        paths = live_demo.runtime_paths(args.root)
        require(paths, 'No qualified runtime binding found. Supply --runtime-binding /absolute/path/runtime-binding.json.')
        if len(paths) == 1:
            runtime = paths[0]
        else:
            require(interactive and not args.yes, 'Multiple runtime bindings exist. Supply --runtime-binding explicitly.')
            runtime = _choose(console, 'Select qualified runtime binding', paths, str, read)
    return selected, models, repetitions, Path(runtime).expanduser().resolve()


def show_plan(console, selection, summary, spool, *, adhoc=False):
    case, models, repetitions, runtime = selection
    if adhoc:
        from rich import box
        from .live_presenter import service_name, operation_label, model_label
        console.print('Ready to run', style=terminal.ACCENT)
        table = terminal.table('', ('Setting', 'Value'), [
            ('Service', service_name(case)),
            ('Operation', case['method'].upper()+' '+case['path']),
            ('Case', case['case_code']),
            ('Model', ', '.join(model_label(m) for m in models)),
            ('Prompt', 'P2'),
            ('Repetitions', repetitions),
        ])
        table.box = box.ROUNDED
        table.width = min(console.width, 96)
        console.print(table)
        console.print('The run will be stored separately and will not modify existing evaluation results.', style='dim')
        return
    console.print('RestApiChecker — Live Run', style=terminal.ACCENT)
    console.print('Separate interactive experiment; real LLM calls after confirmation.')
    console.print(terminal.table('Selection', ('Setting', 'Value'), [
        ('Service', case['service']), ('Operation', case['method'].upper()+' '+case['path']),
        ('Case', f"{case['case_code']} (membership {case['id']})"),
        ('Dataset', f"{case['dataset_name']} (ID {case['dataset_id']}; development)"),
        ('Models', ', '.join(f"{m['name']} (ID {m['id']})" for m in models)),
        ('Repetitions per model', repetitions), ('Planned runs', repetitions*len(models)),
        ('Prompt', 'P2 (unchanged)'), ('Output interface', 'format_json'),
        ('Runtime binding', runtime), ('Recovery directory', spool),
    ]))
    fields = [('Prompt ID', summary.get('prompt_id')), ('Run config IDs by model', summary.get('run_config_ids')),
              ('Seeds', summary.get('seeds')), ('Qualified runtime', summary.get('runtime')),
              ('Timeout seconds', summary.get('timeout_seconds')), ('Context proof', summary.get('context'))]
    fields.extend((name, value) for name, value in summary.get('options', {}).items())
    console.print(terminal.table('Stored configuration', ('Setting', 'Value'),
                                [(name, value) for name, value in fields if value is not None]))
    console.print('Dataset 3 and Experiment 10003 are protected. No retries are automatic.')


def run(repo, args, console, *, input_fn=None, interactive=None):
    """No write/generation before confirmation; optional metadata probes never load models."""
    from . import live_demo
    from .interactive_menu import Back
    adhoc = getattr(args, 'adhoc', False)
    read = input_fn or input
    interactive = (sys.stdin.isatty() and sys.stdout.isatty()) if interactive is None else interactive
    interactive = interactive and not args.json
    ui_url = _ui_url(args.ui_url)
    try:
        selection = _selection(repo, args, console, read, interactive)
        case, models, repetitions, runtime = selection
        planning = dict(case_id=case['id'], model_ids=[m['id'] for m in models],
                        repetitions=repetitions, runtime_path=runtime, root=args.root)
        if adhoc:
            planning['adhoc'] = True
        plan = live_demo.plan(repo, **planning)
        spool = (args.spool or Path.home()/'.local/state/rest-api-checker/live-demo'/uuid.uuid4().hex).expanduser().resolve()
        if not args.json:
            if adhoc:
                from .live_adhoc_runtime import probe_runtime
                runtime_status = probe_runtime()
                if not runtime_status['available'] or runtime_status.get('version') != runtime_status.get('thesis_version'):
                    console.print(terminal.clean(runtime_status['notice']), style='dim')
            show_plan(console, selection, plan.summary, spool, adhoc=adhoc)
        if args.dry_run:
            return dict(status='DRY RUN', exit_code=0, plan=plan.summary, model_calls=0,
                        writes=0, runtime_contacted=False, spool=str(spool), ui_url=ui_url), 0
        if not args.yes and read('Run now? [y/N]: ' if adhoc else 'Execute real LLM run(s)? [y/N]: ').strip().lower() not in ('y', 'yes'):
            return dict(status='CANCELLED', exit_code=0, message='No experiment created and no model called.'), 0
    except Back:
        return dict(status='CANCELLED', exit_code=0, message='Selection cancelled; no experiment created and no model called.'), 0
    except (EOFError, KeyboardInterrupt):
        return dict(status='CANCELLED', exit_code=130, message='Selection cancelled; no experiment created and no model called.'), 130

    displayed = []
    def notify(event):
        if args.json:
            return
        if event.get('event') == 'result' and adhoc:
            from .live_result import show
            if repetitions == 1:
                show(console, event['detail'])
            displayed.append(event['detail']['run']['id'])
        elif event.get('event') == 'runtime' and adhoc:
            pass  # A compact optional notice was already shown before confirmation.
        elif event.get('event') == 'current':
            current = event['current']
            from .live_presenter import model_label
            label = model_label({'name': current['model']}) if adhoc else current['model']
            suffix = '' if adhoc else f" · run {current['run_id']} · attempt {current['attempt']}"
            console.print(terminal.clean(f"→ {label} · {current['case']} · repetition {current['repetition']}"+suffix))
        elif event.get('event') == 'context' and not adhoc:
            console.print(terminal.clean(f"Native context {event['run_order']}/{event['planned']}: {event['model']}"))
        elif event.get('event') == 'created' and not adhoc:
            console.print(terminal.clean(f"Created demo experiment {event['experiment_id']}; "
                f"run IDs: {', '.join(map(str, event['run_ids']))}"))
            console.print(terminal.clean('Recovery evidence: '+event['spool']))
        elif event.get('event') == 'interrupt_requested':
            console.print('⚠ Stopping after the current attempt.' if adhoc else terminal.clean(event['message']))

    with console.status('Waiting for local model' if adhoc else
                        'Preparing native context and executing demo', spinner_style=terminal.ACCENT) \
            if console.is_terminal and not args.json else nullcontext():
        result = live_demo.execute(repo, plan, root=args.root, spool=spool, notify=notify)
    result = {**result, 'ui_url': ui_url, 'displayed_run_ids': displayed}
    return result, result['exit_code']


def present(console, value, *, verbose=False):
    console.print(terminal.clean('Interactive run: '+value['status']), style=terminal.ACCENT)
    if value.get('message'):
        console.print(terminal.clean(value['message']))
    if value['status'] == 'DRY RUN':
        console.print('Read-only preview complete. Runtime not contacted; zero writes and model calls.')
    for detail in value.get('results', []):
        terminal.inspection(console, detail, verbose)
        run_id = detail['run']['id']
        if detail.get('response_id') is not None:
            console.print(f"Observed API response ID: {detail['response_id']}")
        console.print(f'Inspect: rac inspect run {run_id}')
        console.print(terminal.clean(f"Open in UI: {value['ui_url']}/runs/{run_id}"))
    displayed = {detail['run']['id'] for detail in value.get('results', [])}
    for run_id in value.get('run_ids', []):
        if run_id not in displayed:
            console.print(f'Inspect: rac inspect run {run_id}')
            console.print(terminal.clean(f"Open in UI: {value['ui_url']}/runs/{run_id}"))
    if value.get('experiment_id') is not None:
        console.print(f"Experiment summary: rac experiment show {value['experiment_id']}")
    if value.get('spool') and value['status'] != 'DRY RUN':
        console.print(terminal.clean('Recovery evidence: '+str(value['spool'])))
