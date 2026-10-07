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


def _choose(console, title, items, label, read, *, multiple=False):
    require(items, 'No eligible '+title.lower()+'.')
    console.print(terminal.clean(title+':'), style=terminal.ACCENT)
    for index, item in enumerate(items, 1):
        console.print(terminal.clean(f'  {index}) {label(item)}'))
    prompt = 'Selection (comma-separated for multiple models) [1]: ' if multiple else 'Selection [1]: '
    while True:
        value = read(prompt).strip() or '1'
        try:
            indices = [int(part.strip()) for part in value.split(',')]
            if not multiple and len(indices) != 1:
                raise ValueError
            if len(set(indices)) != len(indices) or not all(1 <= i <= len(items) for i in indices):
                raise ValueError
            selected = [items[i-1] for i in indices]
            return selected if multiple else selected[0]
        except ValueError:
            console.print(f'Enter {"distinct numbers" if multiple else "one number"} from 1 to {len(items)}.')


def _unique(items, key):
    return list({item[key]: item for item in items}.values())


def _ui_url(value):
    target = urlsplit(value)
    require(target.scheme in ('http', 'https') and target.hostname and not target.query
            and not target.fragment and target.username is None and target.password is None,
            '--ui-url must be an HTTP(S) base URL without credentials, query or fragment.')
    return value.rstrip('/')


def _selection(repo, args, console, read, interactive):
    from . import live_demo
    explicit = args.case_id is not None and bool(args.model_id)
    require(not args.yes or explicit, '--yes requires explicit --case-id and at least one --model-id.')
    require(interactive or explicit,
            'Non-interactive demo needs --case-id and --model-id. Use --dry-run to preview or --yes to execute.')
    require(interactive or args.dry_run or args.yes,
            'Non-interactive execution requires --yes; use --dry-run for a read-only preview.')
    data = live_demo.catalog(repo)
    cases = [row for row in data['cases'] if args.dataset_id is None or row['dataset_id'] == args.dataset_id]
    require(cases, 'No eligible development cases for this selection. Evaluation datasets and Dataset 3 are excluded; inspect dataset list/cases.')
    require(data['models'], 'No stored approved models are available; inspect dataset inventory.')
    if args.case_id is not None:
        selected = next((row for row in cases if row['id'] == args.case_id), None)
        require(selected is not None, 'Case membership is unavailable or protected. Choose an eligible development membership ID.')
    else:
        service = _choose(console, 'Select service', _unique(cases, 'service_id'), lambda r: r['service'], read)
        candidates = [row for row in cases if row['service_id'] == service['service_id']]
        operation = _choose(console, 'Select operation', _unique(candidates, 'operation_id'),
                            lambda r: f"{r['method']} {r['path']} (ID {r['operation_id']})", read)
        candidates = [row for row in candidates if row['operation_id'] == operation['operation_id']]
        selected = _choose(console, 'Select case', candidates,
            lambda r: f"{r['case_code']} — {r['origin']} / {'/'.join(r['reference'])} "
                      f"[membership {r['id']}; dataset {r['dataset_id']}: {r['dataset_name']}]", read)
    if args.model_id:
        require(len(set(args.model_id)) == len(args.model_id), 'Duplicate --model-id selections are not allowed.')
        models = [next((row for row in data['models'] if row['id'] == model_id), None) for model_id in args.model_id]
        require(all(model is not None for model in models), 'Selected model is unavailable or unapproved; inspect dataset inventory.')
    else:
        models = _choose(console, 'Select model', data['models'], lambda r: f"{r['name']} (ID {r['id']})", read, multiple=True)
    repetitions = args.repetitions
    if repetitions is None:
        repetitions = 1
        if interactive and not args.yes:
            while True:
                value = read('Repetitions per model [1]: ').strip() or '1'
                if value in ('1', '2', '3'):
                    repetitions = int(value)
                    break
                console.print('Enter 1, 2 or 3; existing seeds are 101, 202 and 303.')
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


def show_plan(console, selection, summary, spool):
    case, models, repetitions, runtime = selection
    console.print('RestApiChecker — Live Run', style=terminal.ACCENT)
    console.print('Separate LIVE DEMO experiment; real LLM calls after confirmation.')
    console.print(terminal.table('Selection', ('Setting', 'Value'), [
        ('Service', case['service']), ('Operation', case['method']+' '+case['path']),
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
    """No write or runtime call before explicit confirmation; JSON never prompts."""
    from . import live_demo
    read = input_fn or input
    interactive = (sys.stdin.isatty() and sys.stdout.isatty()) if interactive is None else interactive
    interactive = interactive and not args.json
    ui_url = _ui_url(args.ui_url)
    try:
        selection = _selection(repo, args, console, read, interactive)
        case, models, repetitions, runtime = selection
        plan = live_demo.plan(repo, case_id=case['id'], model_ids=[m['id'] for m in models],
                              repetitions=repetitions, runtime_path=runtime, root=args.root)
        spool = (args.spool or Path.home()/'.local/state/rest-api-checker/live-demo'/uuid.uuid4().hex).expanduser().resolve()
        if not args.json:
            show_plan(console, selection, plan.summary, spool)
        if args.dry_run:
            return dict(status='DRY RUN', exit_code=0, plan=plan.summary, model_calls=0,
                        writes=0, runtime_contacted=False, spool=str(spool), ui_url=ui_url), 0
        if not args.yes and read('Execute real LLM run(s)? [y/N]: ').strip().lower() not in ('y', 'yes'):
            return dict(status='CANCELLED', exit_code=0, message='No experiment created and no model called.'), 0
    except (EOFError, KeyboardInterrupt):
        return dict(status='CANCELLED', exit_code=130, message='Selection cancelled; no experiment created and no model called.'), 130

    def notify(event):
        if args.json:
            return
        if event.get('event') == 'current':
            current = event['current']
            console.print(terminal.clean(f"Running {current['model']} · {current['case']} · "
                f"repetition {current['repetition']} · run {current['run_id']} · attempt {current['attempt']}"))
        elif event.get('event') == 'context':
            console.print(terminal.clean(f"Native context {event['run_order']}/{event['planned']}: {event['model']}"))
        elif event.get('event') == 'created':
            console.print(terminal.clean(f"Created demo experiment {event['experiment_id']}; "
                f"run IDs: {', '.join(map(str, event['run_ids']))}"))
            console.print(terminal.clean('Recovery evidence: '+event['spool']))
        elif event.get('event') == 'interrupt_requested':
            console.print(terminal.clean(event['message']))

    with console.status('Preparing native context and executing demo', spinner_style=terminal.ACCENT) \
            if console.is_terminal and not args.json else nullcontext():
        result = live_demo.execute(repo, plan, root=args.root, spool=spool, notify=notify)
    result = {**result, 'ui_url': ui_url}
    return result, result['exit_code']


def present(console, value, *, verbose=False):
    console.print(terminal.clean('Live demo: '+value['status']), style=terminal.ACCENT)
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
