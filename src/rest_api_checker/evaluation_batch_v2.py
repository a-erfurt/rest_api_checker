"""Operational adapter for an explicitly materialized v2 SQL experiment.

No dataset selection, planning, reference creation, retry attribution or scoring.
The existing attempt runner owns reservation, transport, parsing and persistence.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from . import freeze, runtime_evidence
from .experiment import batch, parser, renderer, request_v2
from .experiment.encoding import digest
from .experiment.provider import OllamaClient
from .experiment.request import ContextProof, MODELS, OPTIONS, SEEDS
from .persistence.database import require, utc_now
from .persistence.importer import PROMPT_HASHES
from .persistence.inspection import bindings, rows, status
from .main_v2_authorization import require_execution


@dataclass
class Plan:
    summary: dict
    state: dict
    setup: dict
    requests: dict
    labels: dict


def prepare(repo, run_id):
    inputs = repo.execution_inputs(run_id)
    setup, run = inputs['setup'], inputs['run']
    require(setup['parser_sha256'] == parser.artifact_hash(), 'Parser artifact drift')
    require(setup['renderer_sha256'] == renderer.artifact_hash(), 'Renderer artifact drift')
    require(run['seed'] == SEEDS.get(run['repetition']), 'Run seed drift')
    require(inputs['prompt_name'] == 'P2', 'Main requires the frozen P2 prompt')
    rendered = renderer.render(inputs['evidence'], contract_identity=inputs['contract_identity'],
                               body_identity=inputs['body_identity'])
    req = request_v2.build_request_v2(rendered,
        interface=request_v2.OutputInterfaceV2(**setup['output_interface']),
        prompt=inputs['prompt'], model=inputs['model']['name'],
        model_digest=inputs['model']['digest'], repetition=run['repetition'])
    request_v2.validate_request_v2(req)
    return inputs, req


def inspect_plan(repo, dataset_id, experiment_id, *, database):
    """SELECT-only inspection; includes reserved/ambiguous work, never retries it."""
    dataset = repo._row('datasets', dataset_id)
    members = rows(repo, 'dataset_cases', dataset_id=dataset_id)
    require(members, 'Dataset is empty')
    require(all(m['reference_id'] is not None for m in members), 'Required final reference is missing')
    state = status(repo, experiment_id)
    exp = state['experiment']
    require(exp['dataset_id'] == dataset_id, 'Explicit dataset/experiment mismatch')
    require(exp['kind'] == 'evaluation', 'An explicitly materialized evaluation experiment is required')
    setup_raw = repo.file(exp['setup_file_id'])
    setup = json.loads(setup_raw)
    require(setup.get('format') == 'main-evaluation-setup-v2',
            'A separately materialized main-evaluation-setup-v2 is required; v1 cannot be upgraded')
    require(setup.get('fabricated') is not True, 'Scientific batch refuses fabricated SQL experiments')
    require(setup.get('bindings') == bindings(repo, dataset_id, setup['schedule']),
            'Frozen dataset/reference/configuration bindings drift')
    repo.verify_closure(setup['files'])
    interface = request_v2.OutputInterfaceV2(**setup['output_interface'])
    # A second experiment can represent the same scientific tuples. Do not guess
    # equivalence across setups or claim cross-experiment idempotency.
    require(len(rows(repo, 'experiments', dataset_id=dataset_id)) == 1,
            'Multiple experiments target this dataset; resolve duplicate-execution ambiguity separately')
    member_by_id = {m['id']: m for m in members}
    for member in members:
        require(member['reference_id'] is not None, 'Required final reference is missing')
        ref = repo._row('reference_results', member['reference_id'])
        require(ref['case_id'] == member['case_id'], 'Reference/case identity mismatch')
        repo.source(ref['source_file_id'], ref['source_pointer'])
    labels, model_ids, prompt_ids, config_ids, tuples = {}, {}, set(), {}, []
    problematic = []
    for run in state['runs']:
        member = member_by_id[run['dataset_case_id']]
        model = repo._row('models', run['model_id'])
        name = model['name']
        require(name in MODELS, 'Unapproved model')
        require(name not in model_ids or model_ids[name] == model['id'], 'Multiple identities for one model')
        model_ids[name] = model['id']
        require(name not in config_ids or config_ids[name] == run['run_config_id'], 'Multiple configurations for one model')
        config_ids[name] = run['run_config_id']
        repo.require_d07(run['run_config_id'], name)
        prompt_ids.add(run['prompt_id'])
        require(run['seed'] == SEEDS.get(run['repetition']), 'Run seed drift')
        tuples.append((member['id'], name, run['repetition']))
        case = repo._row('test_cases', member['case_id'])
        operation = repo._row('api_operations', case['operation_id'])
        contract = repo._row('api_contracts', operation['contract_id'])
        api = repo._row('apis', contract['api_id'])
        labels[run['id']] = dict(case=member['case_code'], api=api['name'], model=name,
                                repetition=run['repetition'], seed=run['seed'])
        attempts = rows(repo, 'run_attempts', run_id=run['id'])
        require(run['result'] in (None, 'valid', 'parser_failure', 'technical_failure'), 'Unknown run result')
        predictions = rows(repo, 'predictions', run_id=run['id'])
        if run['result'] is not None:
            terminal_attempts = [a for a in attempts if a['result'] == run['result']]
            require(terminal_attempts and run['request_file_id'] is not None,
                    'Completed run lacks canonical attempt/request evidence')
            last = max(attempts, key=lambda a: a['attempt'])
            require(last['result'] == run['result'], 'Terminal attempt/run disagreement')
            require((len(predictions) == 1 and predictions[0]['attempt_id'] == last['id'])
                    if run['result'] == 'valid' else not predictions,
                    'Prediction/terminal result disagreement')
        else:
            require(not predictions, 'Pending run has a prediction')
        if run['result'] is None and (attempts or run['request_file_id'] is not None):
            problematic.append(run['id'])
    expected = {(m['id'], name, rep) for m in members for name in MODELS for rep in SEEDS}
    require(len(tuples) == len(expected) and set(tuples) == expected,
            'Schedule must cover every dataset case/model/repetition exactly once')
    require([r['run_order'] for r in state['runs']] == list(range(1, len(tuples)+1)), 'Run order must be contiguous')
    require(len(prompt_ids) == 1, 'Exactly one frozen P2 identity required')
    prompt = repo._row('prompts', next(iter(prompt_ids)))
    require(prompt['name'] == 'P2' and digest(repo.file(prompt['file_id'])) == PROMPT_HASHES['P2'], 'P2 identity drift')
    summary = dict(mode='Evaluation v2 Main', dataset=dataset, database=database,
        experiment_id=experiment_id, cases=len(members), models=[repo._row('models', model_ids[n]) for n in MODELS],
        repetitions=len(SEEDS), seeds=list(SEEDS.values()), planned=state['planned'],
        previously_complete=state['completed'], remaining=state['pending'], problematic=len(problematic),
        problematic_run_ids=problematic, to_execute=0 if problematic else state['pending'],
        missing_unattempted=state['pending']-len(problematic), counts=state['counts'],
        output_mode=interface.mode, prompt='P2', prompt_sha256=PROMPT_HASHES['P2'],
        setup_sha256=digest(setup_raw), runtime=setup['runtime'], token_limit=OPTIONS['num_predict'],
        execution_authorized=setup.get('execution_authorized') is True,
        model_breakdown=[], repetition_breakdown=[])
    for field, values, key in [('model', MODELS, 'model_breakdown'), ('repetition', SEEDS, 'repetition_breakdown')]:
        for value in values:
            selected = [r for r in state['runs'] if labels[r['id']][field] == value]
            summary[key].append(dict(identity=value, planned=len(selected),
                **{k: sum(r['result'] == k for r in selected) for k in state['counts']},
                missing=sum(r['result'] is None for r in selected)))
    return Plan(summary, state, setup, {}, labels)


def preflight(repo, dataset_id, experiment_id, *, database, root, live_check=freeze.verify_live):
    plan = inspect_plan(repo, dataset_id, experiment_id, database=database)
    setup = plan.setup
    require(setup.get('plan_authorized') is True and setup.get('gate_b_complete') is True,
            'Separate v2 plan/runtime authorization is required in the materialized setup')
    if setup.get('execution_authorized') is True:
        require_execution(repo, plan)
    require(plan.summary['dataset']['purpose'] == 'evaluation', 'Main requires an evaluation dataset')
    require(setup['request_builder_sha256'] == request_v2.artifact_hash(), 'V2 request builder drift')
    identities = setup['models']
    require([m['name'] for m in identities] == list(MODELS), 'Exact configured model roster required')
    native = {}
    for identity in identities:
        path = Path(identity['show'])
        require(not path.is_absolute() and '..' not in path.parts, 'Unsafe native metadata path')
        raw = (Path(root)/runtime_evidence.DIRECTORY/path).read_bytes()
        require(digest(json.loads(raw)['template'].encode()) == identity['template_sha256'], 'Native template drift')
        native[identity['name']] = identity
    inventory = setup['request_inventory']
    require(len(inventory) == plan.summary['planned'], 'Exact request inventory required')
    require(set(setup['context_proofs']) == {str(r['run_order']) for r in plan.state['runs']}, 'Complete context proof coverage required')
    for run, item in zip(plan.state['runs'], inventory, strict=True):
        _, req = prepare(repo, run['id'])
        if run['request_file_id'] is not None:
            require(repo.file(run['request_file_id']) == req.body, 'Persisted request differs from v2 plan')
        require(item['run_order'] == run['run_order'] and item['sha256'] == digest(req.body)
                and item['request_identity_sha256'] == req.metadata['request_identity_sha256'], 'Frozen v2 request identity drift')
        identity = native[req.metadata['model']]
        require(identity['digest'] == req.metadata['model_digest'].removeprefix('sha256:'), 'Model digest drift')
        proof = ContextProof(**setup['context_proofs'][str(run['run_order'])])
        proof.verify(req)
        require(proof.template_sha256 == identity['template_sha256'], 'Context/template drift')
        plan.requests[run['id']] = req
    repo.cn.commit()  # End read transaction before metadata-only runtime I/O.
    require(live_check(dict(runtime=setup['runtime'], models=identities), Path(root)) is True,
            'Runtime identity unverified')
    plan.summary['preflight'] = 'PASS (SQL, references, requests, context, models, runtime)'
    return plan


def require_continuation(plan, resume):
    require(not plan.summary['problematic'], 'NEEDS RECONCILIATION: pending reserved attempts; no automatic retry')
    require(resume or not plan.summary['previously_complete'], 'Completed executions exist; use --resume for this exact experiment')


def prepare_spool(path):
    """Check recovery storage before dispatch; only an operational probe is written."""
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=path) as stream:
        stream.write(b'recovery-storage-probe')
        stream.flush()
        os.fsync(stream.fileno())


def execute(repo, plan, *, root, spool, resume, notify, client=None, live_check=freeze.verify_live, stop=None):
    """One shared scientific executor; conservative attribution never grants retry."""
    require_execution(repo, plan)
    require_continuation(plan, resume)
    started, clock = utc_now(), time.monotonic()
    finished_now, scheduled_now, current = [], [], None
    def event(value):
        nonlocal current
        if value['event'] == 'current':
            current = value['current']['run_id']
            scheduled_now.append(current)
            value = {**value, 'current': {**value['current'], **plan.labels[current]}}
        if value['event'] == 'progress' and current is not None:
            finished_now.append(current)
        notify(value)
    def frozen_prepare(repository, run_id):
        require_execution(repository, plan)
        inputs, req = prepare(repository, run_id)
        require(inputs['setup_sha256'] == plan.summary['setup_sha256'], 'Setup changed after preflight')
        require(req == plan.requests[run_id], 'Request changed after preflight')
        return inputs, req
    def verify_runtime(req, proof):
        proof.verify(req)
        return live_check(dict(runtime=plan.setup['runtime'], models=plan.setup['models']), Path(root))
    try:
        result = batch.run(repo, plan.summary['experiment_id'],
            client=client or OllamaClient(request_validator=request_v2.validate_request_v2),
            spool_directory=spool, prepare_request=frozen_prepare, verify_runtime=verify_runtime,
            review_failure=lambda receipt, provider: 'ambiguous', notify=event, stop=stop)
        code, state, message = result['exit_code'], result['state'], result['message']
    except Exception:
        # A failed DB connection may prevent even a status query. Do not claim
        # settlement or expose driver credentials. Durable attempts/spools win.
        code, state, message = 3, None, 'Technical interruption; persisted state may be unknown. Inspect attempts and spool before continuation.'
    elapsed = time.monotonic()-clock
    counts = ({k: state['counts'][k]-plan.state['counts'][k] for k in plan.state['counts']}
              if state is not None else None)
    dispatched = None
    if state is not None:
        try:
            dispatched = sum(any(a['started_at'] is not None for a in rows(repo, 'run_attempts', run_id=run_id))
                             for run_id in scheduled_now)
            repo.cn.commit()
        except Exception:
            code, message = 3, 'Dispatch count unavailable; inspect persisted attempts before continuation.'
    return dict(plan=plan.summary, status='COMPLETED' if code == 0 else 'INTERRUPTED' if code == 130 else 'BLOCKED',
        exit_code=code, started_at=started, ended_at=utc_now(), elapsed_seconds=elapsed,
        executed_now=dispatched, scheduled_now=len(scheduled_now), settled_now=len(finished_now), counts_now=counts,
        completed=state['completed'] if state else None,
        technical_problems=int(code != 0 and (code != 130 or message is not None)),
        average_execution_seconds=elapsed/len(finished_now) if finished_now else None,
        interrupted=code == 130, message=message, simulated=False)


def demo_plan():
    """Synthetic labels and events only; no scientific truth or database objects."""
    labels, runs = {}, []
    for case in ('SIM-001', 'SIM-002', 'SIM-003'):
        for model in MODELS:
            for repetition, seed in SEEDS.items():
                run_id = len(runs)+1
                labels[run_id] = dict(case=case, api='SYNTHETIC', model=model, repetition=repetition, seed=seed)
                runs.append(dict(id=run_id, result=None))
    state = dict(planned=len(runs), completed=0, pending=len(runs),
                 counts=dict(valid=0, parser_failure=0, technical_failure=0), runs=runs)
    summary = dict(mode='DEMO / SIMULATION', dataset=dict(id='demo-dataset-v2-001', name='SYNTHETIC DEMO', version='presentation-only'),
        database='NONE', experiment_id='demo-main-v2-001', cases=3, models=[dict(name=m, digest='NOT QUALIFIED / SIMULATION') for m in MODELS],
        repetitions=len(SEEDS), seeds=list(SEEDS.values()), planned=len(runs), previously_complete=0,
        remaining=len(runs), problematic=0, to_execute=len(runs), output_mode='format_json · SIMULATED',
        runtime={'ollama': {'version': '0.35.0 · SIMULATED / NOT CONTACTED'}}, prompt='P2', prompt_sha256='DEMO-PROMPT-HASH',
        token_limit=OPTIONS['num_predict'], setup_sha256='DEMO-SETUP-HASH')
    return Plan(summary, state, {}, {}, labels)


def simulate(plan, *, notify, delay=0.5, sleep=time.sleep):
    require(0 <= delay <= 2, 'Demo delay must be between 0 and 2 seconds')
    started, clock = utc_now(), time.monotonic()
    state = {**plan.state, 'counts': dict(plan.state['counts'])}
    code = 0
    notify(dict(event='start', state=state))
    try:
        for n, run in enumerate(state['runs']):
            notify(dict(event='current', current={**plan.labels[run['id']], 'run_id': run['id']}))
            sleep(delay)
            state['counts']['parser_failure' if n % 7 == 6 else 'valid'] += 1
            state['completed'] += 1
            state['pending'] -= 1
            notify(dict(event='progress', state=state))
    except KeyboardInterrupt:
        code = 130
    elapsed = time.monotonic()-clock
    notify(dict(event='finish', state=state, status='SIMULATED' if code == 0 else 'INTERRUPTED'))
    return dict(plan=plan.summary, status='SIMULATED' if code == 0 else 'INTERRUPTED', exit_code=code,
        started_at=started, ended_at=utc_now(), elapsed_seconds=elapsed, executed_now=0,
        simulated_steps=state['completed'], model_calls=0, prediction_writes=0, counts_now=state['counts'],
        completed=state['completed'], technical_problems=0, interrupted=code == 130, simulated=True,
        average_execution_seconds=elapsed/state['completed'] if state['completed'] else None)


def repository_commit(root):
    return subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
