"""Isolated development-only live demos through the canonical experiment runner.

No new detector, parser, metric, reference, dataset, configuration or retry policy.
Selection/preparation is read-only; execute is called only after CLI confirmation.
"""
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from uuid import uuid4

from . import evaluation_batch_v2, freeze, main_v2_context, runtime_evidence
from .experiment import batch, parser, renderer, request_v2
from .experiment.encoding import digest, encode
from .experiment.provider import OllamaClient
from .experiment.request import ContextProof, MODELS, SEEDS, OPTIONS, TIMEOUT
from .persistence.database import require
from .persistence.importer import PROMPT_HASHES
from .persistence.inspection import bindings, rows, run_detail

FORMAT = 'live-demo-setup-v1'
PROTECTED_DATASET = 3
PROTECTED_EXPERIMENT = 10003


def catalog(repo):
    """Discover generic domain entities; never offer final/evaluation cases."""
    datasets = {r['id']: r for r in rows(repo, 'datasets')}
    members = rows(repo, 'dataset_cases')
    final_cases = {m['case_id'] for m in members if m['dataset_id'] == PROTECTED_DATASET
                   or datasets[m['dataset_id']]['purpose'] == 'evaluation'}
    incomplete = {m['dataset_id'] for m in members if m['reference_id'] is None}
    cases, operations, contracts, apis = (
        {r['id']: r for r in rows(repo, t)}
        for t in ('test_cases', 'api_operations', 'api_contracts', 'apis'))
    references = {r['id']: r for r in rows(repo, 'reference_results')}
    eligible = []
    for member in members:
        dataset = datasets[member['dataset_id']]
        if (dataset['id'] == PROTECTED_DATASET or dataset['purpose'] != 'development'
                or dataset['id'] in incomplete or member['case_id'] in final_cases):
            continue
        case = cases[member['case_id']]
        reference = references.get(member['reference_id'])
        if not reference or reference['case_id'] != case['id']:
            continue
        operation = operations[case['operation_id']]
        api = apis[contracts[operation['contract_id']]['api_id']]
        eligible.append(dict(id=member['id'], dataset_id=dataset['id'], dataset_name=dataset['name'],
            case_code=member['case_code'], service_id=api['id'], service=api['name'],
            operation_id=operation['id'], method=operation['http_method'], path=operation['path_template'],
            origin=case['origin'], reference=[reference[c] for c in ('c1', 'c2', 'c3')]))
    prompts = [p for p in rows(repo, 'prompts') if p['name'] == 'P2'
               and digest(repo.file(p['file_id'])) == PROMPT_HASHES['P2']]
    return dict(cases=eligible, models=[m for m in rows(repo, 'models') if m['name'] in MODELS],
                prompts=prompts, configs=rows(repo, 'run_configs'))


def runtime_paths(root):
    """Explicit available identities; sorted for display, never choose latest."""
    return sorted((Path(root)/runtime_evidence.DIRECTORY).glob('*/runtime-binding.json'))


def load_runtime(path, root, models):
    raw = Path(path).read_bytes()
    binding = json.loads(raw)
    require(set(binding) == {'runtime', 'models'}, 'Explicit runtime and model bindings required')
    host = binding['runtime']
    require(host.get('format') == 'evaluation-v2-runtime-identity-v1'
            and host.get('runtime_identity', '').startswith('evaluation_v2_'),
            'Qualified Evaluation-v2 render-only runtime required')
    selected, sources = [], {'runtime-binding.json': raw}
    for model in models:
        matches = [m for m in binding['models'] if m['name'] == model['name']
                   and m['digest'] == model['digest'].removeprefix('sha256:')]
        require(len(matches) == 1, 'Selected DB model does not match the explicit runtime binding')
        identity = matches[0]
        require(identity['runtime_identity'] == host['runtime_identity'], 'Model/runtime binding drift')
        for key in ('show', 'manifest'):
            relative = Path(identity[key])
            require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe native metadata path')
            location = Path(root)/runtime_evidence.DIRECTORY/relative
            require(location.resolve().is_relative_to((Path(root)/runtime_evidence.DIRECTORY).resolve()),
                    'Native metadata must stay inside its qualification directory')
            sources['native/'+str(relative)] = location.read_bytes()
        show = json.loads(sources['native/'+identity['show']])
        manifest_raw = sources['native/'+identity['manifest']]
        manifest = json.loads(manifest_raw)
        require(digest(show['template'].encode()) == identity['template_sha256'], 'Native template drift')
        require(digest(manifest_raw) == identity['digest'], 'Model manifest digest drift')
        layers = [{k: layer[k] for k in ('digest', 'mediaType', 'size')}
                  for layer in [manifest['config'], *manifest['layers']]]
        require(layers == identity['layers'], 'Model layer binding drift')
        selected.append(identity)
    return dict(runtime=host, models=selected), sources


@dataclass
class Plan:
    summary: dict
    schedule: list
    requests: dict
    binding: dict
    snapshot: dict
    sources: dict
    runtime_path: Path


def _request(repo, member, prompt, model, repetition):
    # Explicit evidence projection only. Reference and case labels never enter LLM input.
    case = repo._row('test_cases', member['case_id'])
    operation = repo._row('api_operations', case['operation_id'])
    contract = repo._row('api_contracts', operation['contract_id'])
    response = repo._row('responses', case['response_id'])
    evidence = renderer.Evidence(repo.file(contract['file_id']), operation['http_method'],
        operation['path_template'], response['status_code'], response['content_type'],
        repo.file(response['body_file_id']))
    rendered = renderer.render(evidence, contract_identity=f'files:{contract["file_id"]}',
                               body_identity=f'files:{response["body_file_id"]}')
    return request_v2.build_request_v2(rendered, interface=request_v2.OutputInterfaceV2('format_json'),
        prompt=repo.file(prompt['file_id']), model=model['name'], model_digest=model['digest'],
        repetition=repetition)


def plan(repo, *, case_id, model_ids, repetitions, runtime_path, root):
    require(type(repetitions) is int and repetitions in SEEDS, 'Repetitions must be 1, 2 or 3')
    require(model_ids and len(model_ids) == len(set(model_ids)), 'Select each model identity once')
    inventory = catalog(repo)
    case = next((c for c in inventory['cases'] if c['id'] == case_id), None)
    require(case is not None, 'Case is not an eligible referenced development membership; final cases are blocked')
    member = repo._row('dataset_cases', case_id)
    models = [next((m for m in inventory['models'] if m['id'] == i), None) for i in model_ids]
    require(all(m is not None for m in models), 'Select existing approved model IDs')
    require(len({m['name'] for m in models}) == len(models), 'Select only one digest per model name')
    require(inventory['prompts'], 'Approved unchanged P2 is missing; demo cannot create or alter prompts')
    prompt = min(inventory['prompts'], key=lambda p: p['id'])
    configs = []
    for model in models:
        compatible = []
        for config in inventory['configs']:
            try:
                repo.require_d07(config['id'], model['name'])
            except ValueError:
                continue
            compatible.append(config['id'])
        require(compatible, 'No existing compatible D07 configuration for '+model['name'])
        configs.append(min(compatible))
    binding, sources = load_runtime(runtime_path, root, models)
    schedule, requests = [], {}
    for model, config in zip(models, configs, strict=True):
        for repetition in range(1, repetitions+1):
            order = len(schedule)+1
            schedule.append(dict(dataset_case_id=case_id, model_id=model['id'], prompt_id=prompt['id'],
                run_config_id=config, repetition=repetition, seed=SEEDS[repetition], run_order=order))
            requests[order] = _request(repo, member, prompt, model, repetition)
            request_v2.validate_request_v2(requests[order])
    snapshot = bindings(repo, member['dataset_id'], schedule)
    repo.cn.commit()  # Close the read transaction before user input/network I/O.
    summary = dict(service=case['service'], operation=f"{case['method'].upper()} {case['path']}",
        case=case['case_code'], case_id=case_id, reference=case['reference'],
        dataset_id=member['dataset_id'], dataset=case['dataset_name'],
        models=[m['name'] for m in models], model_ids=model_ids, prompt='P2', prompt_id=prompt['id'],
        run_config_ids=configs, repetitions=repetitions, seeds=[SEEDS[r] for r in range(1,repetitions+1)],
        planned=len(schedule), output_mode='format_json', options=OPTIONS, timeout_seconds=TIMEOUT,
        runtime=binding['runtime']['runtime_identity'], runtime_binding=str(Path(runtime_path).resolve()),
        runtime_binding_sha256=digest(sources['runtime-binding.json']),
        context='Measured after confirmation; exact native render/tokenize, no guessed tokens',
        destination='NEW LIVE-DEMO experiment; development references reused unchanged',
        scientific_evaluation=False, parser_sha256=parser.artifact_hash())
    return Plan(summary, schedule, requests, binding, snapshot, sources, Path(runtime_path))


def _unchanged(repo, prepared, root):
    require(prepared.summary['parser_sha256'] == parser.artifact_hash(), 'Parser changed after selection')
    selected = prepared.schedule[0]['dataset_case_id']
    require(selected in {c['id'] for c in catalog(repo)['cases']}, 'Development case eligibility changed')
    require(prepared.summary['dataset_id'] != PROTECTED_DATASET, 'Dataset 3 is protected')
    require(bindings(repo, prepared.summary['dataset_id'], prepared.schedule) == prepared.snapshot,
            'Demo source/configuration/reference changed after selection')
    models = [repo._row('models', i) for i in prepared.summary['model_ids']]
    current, sources = load_runtime(prepared.runtime_path, root, models)
    require(current == prepared.binding and sources == prepared.sources, 'Runtime evidence changed after selection')
    for slot in prepared.schedule:
        req = _request(repo, repo._row('dataset_cases', slot['dataset_case_id']),
            repo._row('prompts', slot['prompt_id']), repo._row('models', slot['model_id']), slot['repetition'])
        require(req == prepared.requests[slot['run_order']], 'Demo request changed after selection')
    repo.cn.commit()


def _measure(prepared, *, root, live_check, transport, runner, notify):
    sources, proofs = {}, {}
    for order, req in prepared.requests.items():
        require(live_check(prepared.binding, Path(root)) is True, 'Live runtime identity unverified')
        identity = next(i for i in prepared.binding['models'] if i['name'] == req.metadata['model'])
        notify(dict(event='context', run_order=order, planned=len(prepared.requests), model=identity['name']))
        render_request = {**json.loads(req.body), '_debug_render_only': True, 'truncate': False}
        render_raw = transport('http://127.0.0.1:11434/api/chat', render_request)
        rendered = json.loads(render_raw)
        require(not rendered.get('done') and not rendered.get('eval_count')
                and not rendered.get('message', {}).get('content')
                and not rendered.get('message', {}).get('thinking'), 'Unexpected generation in render-only measurement')
        _, url = runner(identity)
        token_request = dict(content=rendered['_debug_info']['rendered_template'], add_special=True, parse_special=True)
        token_raw = transport(url, token_request)
        measured_identity = {**identity, 'digest': req.metadata['model_digest']}
        count = main_v2_context.validate_measurement(req, measured_identity, render_request, rendered,
                                                     token_request, json.loads(token_raw))
        prefix = f'context/{order:03}'
        evidence = {'render-request': encode(render_request), 'render-response': render_raw,
                    'token-request': encode(token_request), 'token-response': token_raw}
        sources.update({prefix+'-'+k+'.json': raw for k, raw in evidence.items()})
        proof = ContextProof(digest(req.body), req.metadata['model_digest'], identity['template_sha256'], digest(token_raw), count)
        proof.verify(req)
        proofs[str(order)] = asdict(proof)
    require(live_check(prepared.binding, Path(root)) is True, 'Runtime changed during context measurement')
    return sources, proofs


def execute(repo, prepared, *, root, spool, notify=lambda event: None, client=None,
            live_check=freeze.verify_live, transport=main_v2_context.http, runner=main_v2_context.native_runner):
    """Create only a new demo after exact proof checks; never accept an experiment ID."""
    _unchanged(repo, prepared, root)
    measured, proofs = _measure(prepared, root=root, live_check=live_check, transport=transport,
                                runner=runner, notify=notify)
    _unchanged(repo, prepared, root)
    evaluation_batch_v2.prepare_spool(spool)
    name = 'LIVE-DEMO '+str(uuid4())
    experiment_id, run_ids = None, []
    try:
        with repo.transaction():
            files = list(prepared.snapshot['files'])
            for filename, raw in {**prepared.sources, **measured}.items():
                file_id = repo.archive('live-demo/'+filename, raw)
                files.append(dict(file_id=file_id, sha256=digest(raw)))
            setup = dict(format=FORMAT, live_demo=True, fabricated=False, scientific_evaluation=False,
                dataset_id=prepared.summary['dataset_id'], schedule_seed=SEEDS[1], schedule=prepared.schedule,
                expected_runs=len(prepared.schedule), parser_sha256=prepared.summary['parser_sha256'],
                renderer_sha256=renderer.artifact_hash(), request_builder_sha256=request_v2.artifact_hash(),
                files=files, bindings=prepared.snapshot, output_interface=asdict(request_v2.OutputInterfaceV2('format_json')),
                gate_b_complete=True, runtime=prepared.binding['runtime'], models=prepared.binding['models'],
                context_proofs=proofs, execution_consent='Explicit demo execution confirmation; not Main authorization',
                request_inventory=[dict(run_order=order, sha256=digest(req.body),
                    request_identity_sha256=req.metadata['request_identity_sha256']) for order,req in prepared.requests.items()])
            experiment_id, run_ids = repo.plan_experiment(name=name, kind='comparison',
                dataset_id=prepared.summary['dataset_id'], schedule_seed=SEEDS[1], setup=setup,
                schedule=prepared.schedule, notes='LIVE DEMO only; outside scientific evaluations. No automatic resume or retries.')
            require(experiment_id != PROTECTED_EXPERIMENT, 'Experiment 10003 is protected; demo creation rolled back')
        notify(dict(event='created', experiment_id=experiment_id, run_ids=run_ids, spool=str(spool)))
        persisted = repo._row('experiments', experiment_id)
        setup_hash = digest(repo.file(persisted['setup_file_id']))
        repo.cn.commit()

        def frozen_prepare(repository, run_id):
            require(run_id in run_ids and experiment_id != PROTECTED_EXPERIMENT, 'Run is outside this new demo')
            inputs, req = evaluation_batch_v2.prepare(repository, run_id)
            require(inputs['run']['experiment_id'] == experiment_id
                    and inputs['setup'].get('format') == FORMAT
                    and inputs['setup'].get('live_demo') is True
                    and inputs['setup_sha256'] == setup_hash, 'Demo setup identity drift')
            require(inputs['setup']['request_builder_sha256'] == request_v2.artifact_hash(), 'Request builder drift')
            require(req == prepared.requests[inputs['run']['run_order']], 'Frozen demo request drift')
            return inputs, req

        def verify_runtime(req, proof):
            proof.verify(req)
            _unchanged(repo, prepared, root)
            return live_check(prepared.binding, Path(root))

        result = batch.run(repo, experiment_id,
            client=client if client is not None else OllamaClient(request_validator=request_v2.validate_request_v2),
            spool_directory=spool, verify_runtime=verify_runtime, prepare_request=frozen_prepare,
            review_failure=lambda receipt, provider: 'ambiguous', notify=notify)
        details = [run_detail(repo, i) for i in run_ids]
        for detail in details:
            member = repo._row('dataset_cases', detail['run']['dataset_case_id'])
            detail['response_id'] = repo._row('test_cases', member['case_id'])['response_id']
        repo.cn.commit()
        return dict(status=result['status'], exit_code=result['exit_code'], experiment_id=experiment_id,
            run_ids=run_ids, results=details, spool=str(spool), message=result['message'],
            counts=result['state']['counts'], completed=result['state']['completed'], pending=result['state']['pending'])
    except KeyboardInterrupt:
        return dict(status='INTERRUPTED', exit_code=130, experiment_id=experiment_id, run_ids=run_ids,
                    results=[], spool=str(spool), message='Inspect stored attempts before any new demo. No automatic resume.')
    except Exception:
        # Driver messages may expose credentials. Keep IDs even if status reread fails.
        return dict(status='BLOCKED', exit_code=3, experiment_id=experiment_id, run_ids=run_ids,
                    results=[], spool=str(spool), message='Technical interruption; inspect these run IDs and durable spool. No automatic retry.')
