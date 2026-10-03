"""Deterministic Main-v2 request preparation and SQL materialization; no inference."""
import argparse
from contextlib import closing
from decimal import Decimal
import json
from pathlib import Path

from . import main_v2_release as release, runtime_evidence
from .experiment import parser, renderer, request, request_v2
from .experiment.encoding import digest, encode
from .persistence.database import connect, json_bytes, lock, read_settings, require
from .persistence.importer import PROMPT_HASHES
from .persistence.inspection import bindings, rows
from .persistence.repository import D07, Repository

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT.parent/'bachelor_rest_api_checker'
ORDER_VERSION = 'dataset-position-model-repetition-v1'


def authorities(final):
    """Resolve the release's existing authorities; no second generation config."""
    plan = json.loads(final['files']['candidate/runtime_plan.json'])
    source_bindings = json.loads(final['files']['candidate/source_bindings.json'])['files']
    def bound_read(path):
        path = Path(path)
        identity = source_bindings.get(str(path))
        raw = path.read_bytes()
        require(identity is not None and digest(raw) == identity['sha256'] and len(raw) == identity['bytes'],
                'Frozen authority source drift: '+str(path))
        return raw
    source = plan['configuration_authority']
    require(Path(source['path']).resolve() == Path(request.__file__).resolve()
            and digest(Path(request.__file__).read_bytes()) == source['sha256'], 'Generation authority drift')
    prompt = bound_read(plan['prompt']['path'])
    require(digest(prompt) == plan['prompt']['sha256'] == PROMPT_HASHES['P2'], 'P2 identity drift')
    rb = plan['qualified_runtime_binding']
    runtime_raw = bound_read(rb['path'])
    require(digest(runtime_raw) == rb['sha256'], 'Qualified v2 runtime binding drift')
    runtime = json.loads(runtime_raw)
    require(runtime['runtime']['runtime_identity'] == rb['identity']
            and runtime['runtime']['format'] == 'evaluation-v2-runtime-identity-v1', 'Qualified v2 runtime required')
    require([m['name'] for m in runtime['models']] == list(request.MODELS), 'Configured model roster drift')
    pilot = Path(rb['path']).parent
    qualification_raw = bound_read(pilot/'qualification/complete.json')
    qualification = json.loads(qualification_raw)
    require(qualification['status'] == 'PASS_FOR_BOUNDED_INTERFACE_PILOT'
            and qualification['runtime_binding_sha256'] == digest(runtime_raw), 'Missing qualified Evaluation-v2 runtime')
    qualified_plan_raw = bound_read(pilot/'prepared/manifest.json')
    qualified_plan = json.loads(qualified_plan_raw)
    for key, value in code_identities().items():
        require(qualified_plan[key] == value, 'Qualified scientific implementation drift: '+key)
    require(plan['renderer_artifact_sha256'] == renderer.artifact_hash(), 'Reviewed renderer drift')
    require(plan['output_interface']['mode'] == 'format_json', 'Main-v2 author-selected output mode required')
    interface = request_v2.OutputInterfaceV2(plan['output_interface']['mode'], plan['output_interface']['version'])
    require(interface.binding() == plan['output_interface'], 'Output interface drift')
    files = dict(prompt=prompt, runtime=runtime_raw,
                 qualification=qualification_raw,
                 interface_selection=bound_read(plan['output_interface_authority']),
                 qualified_plan=qualified_plan_raw,
                 generation_authority=bound_read(request.__file__))
    for model in runtime['models']:
        for field in ('show', 'manifest'):
            raw = bound_read(release.safe_path(pilot/'runtime_namespace', model[field]))
            files['native/'+model[field]] = raw
        show = json.loads(files['native/'+model['show']])
        require(digest(show['template'].encode()) == model['template_sha256'], 'Native template drift')
        require(digest(files['native/'+model['manifest']]) == model['digest'], 'Model manifest drift')
    return plan, runtime, interface, files


def code_identities():
    return dict(parser_sha256=parser.artifact_hash(), renderer_sha256=renderer.artifact_hash(),
                request_builder_sha256=request_v2.artifact_hash())


def verify_final(final):
    require(isinstance(final, dict) and 'root' in final, 'Explicit FINAL/FROZEN release required')
    require(release.load_release(final['root']) == final, 'Final release identity changed')


def projection(final):
    """Lossless capture projection, using the existing service_capture origin mapping."""
    result = []
    for case in final['manifest']['cases']:
        vector = [case[k] for k in ('C1', 'C2', 'C3')]
        body = final['files']['candidate/'+case['response_evidence_file']]
        contract = final['files']['candidate/'+case['contract_evidence_file']]
        require(digest(body) == case['body_sha256'] and len(body) == case['body_length']
                and digest(contract) == case['contract_sha256'], 'Response/contract identity mismatch')
        record = dict(case_id=case['candidate_id'], api=case['api'], root_family=case['dependency_family'],
            operation=dict(method='post', path=case['operation_path']), origin='natural_observation', immediate_parent=None,
            contract_sha256=case['contract_sha256'], status=case['http_status'], content_type=case['content_type'],
            body=dict(path='candidate/'+case['response_evidence_file'], sha256=case['body_sha256']),
            contract=dict(path='candidate/'+case['contract_evidence_file'], sha256=case['contract_sha256']),
            original_candidate=case,
            origin_mapping='Captured observation, as in service_capture.materialize; original controlled-state provenance retained; no synthetic ancestry inferred.',
            oracle=dict(c1=vector[0], c2=vector[1], c3=vector[2], vector=vector, overall=case['overall_consistency'],
                selected_response=case['selected_response_branch'], selected_media=case['selected_media_branch'],
                schema_pointer=case['schema_pointer'], diagnostics=case['reference_diagnostics']))
        result.append(record)
    return dict(format='main-v2-sql-projection-v1', dataset_root=final['sha256'], cases=result)


def request_files(final):
    verify_final(final)
    _, runtime, interface, sources = authorities(final)
    payload = {'authority/'+n: b for n, b in sources.items()}
    slots = []
    for record in projection(final)['cases']:
        evidence = renderer.Evidence(final['files'][record['contract']['path']], 'post', record['operation']['path'],
                                     record['status'], record['content_type'], final['files'][record['body']['path']])
        rendered = renderer.render(evidence, contract_identity=record['contract_sha256'], body_identity=record['body']['sha256'])
        require(digest(rendered.content) == record['original_candidate']['exact_model_context_sha256'], 'Reviewed context drift')
        for model in runtime['models']:
            for repetition, seed in request.SEEDS.items():
                req = request_v2.build_request_v2(rendered, interface=interface, prompt=sources['prompt'],
                            model=model['name'], model_digest=model['digest'], repetition=repetition)
                request_v2.validate_request_v2(req)
                number = len(slots)+1
                path = f'requests/{number:06}.json'
                payload[path] = req.body
                payload[f'provenance/{number:06}.json'] = encode(req.metadata)
                slots.append(dict(run_order=number, case=record['case_id'], model=model['name'], repetition=repetition,
                    seed=seed, request_path=path, sha256=digest(req.body), request_identity_sha256=req.metadata['request_identity_sha256'],
                    logical_identity_sha256=digest(encode(dict(dataset_root=final['sha256'], case=record['case_id'],
                        model=model['digest'], repetition=repetition, seed=seed, request_identity=req.metadata['request_identity_sha256'])))))
    return release.seal(payload, 'plan.json', format='main-v2-prepared-v1', status='PREPARED_NOT_AUTHORIZED_NOT_EXECUTED',
        dataset_root=final['sha256'], dataset_name=release.DATASET, dataset_version=final['manifest']['version'],
        cases=len(final['manifest']['cases']), planned=len(slots), schedule_version=ORDER_VERSION,
        # SQL requires an integer seed. Order is lexicographic, with no shuffle or PRNG.
        schedule_seed=0, models=list(request.MODELS), repetitions={str(k): v for k, v in request.SEEDS.items()}, generation_options=request.OPTIONS,
        output_interface=interface.binding(), prompt_sha256=PROMPT_HASHES['P2'], **code_identities(), slots=slots)


def load_prepared(final, prepared):
    plan, files, raw = release.checked_package(prepared, 'plan.json')
    expected = request_files(final)
    require(raw == expected['plan.json'] and all(files[n] == b for n, b in expected.items()
            if n not in ('plan.json', 'plan.sha256')), 'Prepared request/configuration identity drift')
    return plan, files, raw


def restore_native(files, root):
    """Restore only the v2 namespace, with identical-byte reuse; never replace v1."""
    for name, raw in files.items():
        if not name.startswith('authority/native/'):
            continue
        relative = name.removeprefix('authority/native/')
        require(Path(relative).parts[0].startswith('evaluation_v2_'), 'Separate v2 native namespace required')
        path = release.safe_path(Path(root)/runtime_evidence.DIRECTORY, relative)
        if path.exists():
            require(path.read_bytes() == raw, 'Existing native namespace drift')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(raw)


def import_dataset(repo, final):
    verify_final(final)
    projected = projection(final)
    namespace = release.DATASET+'/'+final['manifest']['version']
    with repo.transaction():
        lock(repo.cn, namespace)
        ds = repo.dataset(release.DATASET, final['manifest']['version'], 'evaluation')
        # Existing import must match the exact source bytes; no edits to membership.
        source = repo.archive('main-v2-sql-projection.json', encode(projected))
        file_ids = {n: repo.archive(n, b) for n, b in final['files'].items()}
        file_ids['freeze.json'] = repo.archive('main-v2-freeze.json', final['freeze_raw'])
        members = {}
        for index, c in enumerate(projected['cases']):
            existing_api = rows(repo, 'apis', name=c['api'])
            api = existing_api[0]['id'] if existing_api else repo.api(c['api'])
            contract = repo.contract(api, file_ids[c['contract']['path']], json.loads(final['files'][c['contract']['path']])['openapi'])
            operation = repo.operation(contract, c['operation']['method'], c['operation']['path'])
            family = repo.family(api, c['root_family'])
            existing = rows(repo, 'test_cases', source_namespace=namespace, native_case_id=c['case_id'])
            response = existing[0]['response_id'] if existing else repo.response(c['status'], c['content_type'], file_ids[c['body']['path']])
            cid = repo.case(source_namespace=namespace, native_case_id=c['case_id'], operation_id=operation,
                response_id=response, family_id=family, origin=c['origin'], parent_case_id=None,
                source_file_id=source, source_pointer=f'/cases/{index}')
            rid = repo.reference(cid, 1, source, f'/cases/{index}/oracle')
            members[c['case_id']] = repo.membership(ds, cid, rid, c['case_id'], index+1)
        actual = sorted(rows(repo, 'dataset_cases', dataset_id=ds), key=lambda r: r['position'])
        require([m['id'] for m in actual] == list(members.values()), 'Final dataset membership identity mismatch')
        return dict(dataset_id=ds, dataset_root=final['sha256'], members=members,
                    file_ids=sorted(set(file_ids.values()) | {source}))


def authorize_binding(final, plan_raw, context_raw, dataset_id, database):
    return dict(dataset_root=final['sha256'], prepared_plan_sha256=digest(plan_raw),
                context_manifest_sha256=digest(context_raw), dataset_id=dataset_id, database=database)


def materialize(repo, final, prepared, context, authorization, *, dataset_id, database):
    """Single atomic, duplicate-protected plan. ZERO transport calls or attempts."""
    from .main_v2_context import verify_context
    plan, files, plan_raw = load_prepared(final, prepared)
    proofs, context_files, context_raw = verify_context(plan, files, plan_raw, context)
    auth_raw = Path(authorization).read_bytes()
    release.accepted(json.loads(auth_raw), 'AUTHORIZE_MAIN_V2_PLAN',
                     authorize_binding(final, plan_raw, context_raw, dataset_id, database))
    with repo.transaction():
        require(repo.cn.execute('SELECT DB_NAME()').fetchval() == database, 'Authorized database/connection mismatch')
        lock(repo.cn, release.DATASET+'/'+final['manifest']['version'])
        imported = import_dataset(repo, final)
        require(imported['dataset_id'] == dataset_id, 'Explicit final dataset ID mismatch')
        require(not rows(repo, 'experiments', dataset_id=dataset_id), 'Main-v2 already materialized; inspect existing experiment, never duplicate')
        archived = set(imported['file_ids'])
        for name, raw in {**files, **{'context/'+n: b for n, b in context_files.items()},
                          'plan.json': plan_raw, 'context/manifest.json': context_raw, 'authorization.json': auth_raw}.items():
            archived.add(repo.archive(name, raw))
        prompt = repo.prompt('P2', 'v1', 'checklist', repo.archive('P2.txt', files['authority/prompt']))
        runtime = json.loads(files['authority/runtime'])
        models, configs = {}, {}
        for identity in runtime['models']:
            name = identity['name']
            native = files['authority/native/'+identity['show']]
            show = json.loads(native)
            arch = show['model_info']['general.architecture']
            properties = dict(name=name, family=show['details']['family'], parameters_b=Decimal(show['details']['parameter_size'].removesuffix('B')),
                quantization=show['details']['quantization_level'], context_length=show['model_info'][arch+'.context_length'],
                digest=identity['digest'], architecture=arch)
            existing = rows(repo, 'models', name=name, digest=identity['digest'])
            if existing:
                require(len(existing) == 1 and all(existing[0][k] == v for k, v in properties.items()), 'Existing model identity drift')
                models[name] = existing[0]['id']
            else:
                models[name] = repo.model(**properties, metadata_file_id=repo.archive(identity['show'], native))
            configs[name] = repo.configuration(think=False if name == request.MODELS[0] else None, **D07)
            repo.require_d07(configs[name], name)
        schedule, request_inventory = [], []
        for slot in plan['slots']:
            order = slot['run_order']
            schedule.append(dict(dataset_case_id=imported['members'][slot['case']], model_id=models[slot['model']],
                prompt_id=prompt, run_config_id=configs[slot['model']], repetition=slot['repetition'], seed=slot['seed'], run_order=order))
            request_inventory.append({k: slot[k] for k in ('run_order', 'sha256', 'request_identity_sha256', 'logical_identity_sha256')} |
                dict(file_id=repo.archive(slot['request_path'], files[slot['request_path']])))
        bound = bindings(repo, dataset_id, schedule)
        archived.update(f['file_id'] for f in bound['files'])
        setup = dict(format='main-evaluation-setup-v2', dataset_id=dataset_id, dataset_root=final['sha256'],
            schedule=schedule, schedule_seed=plan['schedule_seed'], schedule_version=ORDER_VERSION,
            bindings=bound, files=[dict(file_id=i, sha256=digest(repo.file(i))) for i in sorted(archived)],
            output_interface={k: plan['output_interface'][k] for k in ('mode', 'version')},
            output_interface_sha256=digest(encode(plan['output_interface'])),
            context_proofs=proofs, request_inventory=request_inventory, **runtime, **code_identities(),
            runtime_binding_sha256=digest(files['authority/runtime']),
            generation_identity_sha256=digest(files['authority/generation_authority']), prompt_sha256=plan['prompt_sha256'],
            prepared_plan_sha256=digest(plan_raw), context_manifest_sha256=digest(context_raw),
            authorization_sha256=digest(auth_raw), execution_authorized=True, gate_b_complete=True)
        setup_raw = json_bytes(setup)
        setup_id = repo.archive('main-evaluation-setup-v2.json', setup_raw)
        experiment = repo._insert('experiments', name='MAIN_EVALUATION_V2', kind='evaluation', dataset_id=dataset_id,
            setup_file_id=setup_id, schedule_seed=plan['schedule_seed'], started_at=None, finished_at=None,
            notes='Human-bound Main-v2 plan; explicit CLI execution required; no automatic retry.')
        runs = [repo._insert('experiment_runs', experiment_id=experiment, dataset_id=dataset_id, **s) for s in schedule]
        # Check through the actual runner before the transaction can commit.
        from . import evaluation_batch_v2 as batch
        inspected = batch.inspect_plan(repo, dataset_id, experiment, database=database)
        for rid, slot in zip(runs, plan['slots'], strict=True):
            _, req = batch.prepare(repo, rid)
            require(req.body == files[slot['request_path']] and req.metadata['request_identity_sha256'] == slot['request_identity_sha256'], 'SQL request roundtrip drift')
            request.ContextProof(**proofs[str(slot['run_order'])]).verify(req)
        require(inspected.summary['planned'] == len(final['manifest']['cases'])*len(request.MODELS)*len(request.SEEDS)
                and inspected.summary['problematic'] == 0, 'Incomplete Main schedule')
        return dict(dataset_id=dataset_id, experiment_id=experiment, cases=plan['cases'], models=len(models),
            repetitions=len(request.SEEDS), seeds=list(request.SEEDS.values()), planned_runs=len(runs),
            setup_sha256=digest(setup_raw), attempts=0, predictions=0, model_calls=0, automatic_retries=0)


def write_json(path, value):
    with Path(path).open('xb') as out:
        out.write(encode(value))


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--research', type=Path, default=RESEARCH)
    sub = cli.add_subparsers(dest='command', required=True)
    for action in ('integrity', 'freeze-template', 'freeze'):
        p = sub.add_parser(action)
        p.add_argument('--archive', type=Path, required=True)
        p.add_argument('--review-dir', type=Path, required=True)
        p.add_argument('--output', type=Path, required=True)
        if action != 'integrity':
            p.add_argument('--integrity', type=Path, required=True)
            p.add_argument('--version', required=True)
        if action == 'freeze':
            p.add_argument('--approval', type=Path, required=True)
    for action in ('prepare', 'import-dataset', 'plan-template', 'materialize'):
        p = sub.add_parser(action)
        p.add_argument('--release', type=Path, required=True)
        p.add_argument('--output', type=Path, required=True)
        if action in ('import-dataset', 'materialize'):
            p.add_argument('--env-file', type=Path, required=True)
            p.add_argument('--database', required=True)
        if action in ('plan-template', 'materialize'):
            p.add_argument('--prepared', type=Path, required=True)
            p.add_argument('--context', type=Path, required=True)
            p.add_argument('--dataset-id', type=int, required=True)
            if action == 'plan-template':
                p.add_argument('--database', required=True)
            else:
                p.add_argument('--authorization', type=Path, required=True)
    args = cli.parse_args(argv)
    require(not args.output.resolve().is_relative_to(args.research.resolve()), 'Research repository is read only')
    require(not args.output.exists(), 'New output path required')
    if args.command == 'integrity':
        write_json(args.output, release.check_integrity(args.archive, args.review_dir))
    elif args.command == 'freeze-template':
        _, files, raw = release.checked_package(args.archive, 'archive_manifest.json')
        reviews = {n: (args.review_dir/n).read_bytes() for n in release.REVIEW_FILES}
        cases = release.reviewed(files, reviews)
        write_json(args.output, dict(decision='PENDING', author='', accepted_at='', version=args.version,
            **release.freeze_binding(raw, reviews, cases, args.integrity.read_bytes(), files)))
    elif args.command == 'freeze':
        release.freeze_dataset(args.archive, args.review_dir, args.integrity, args.approval, args.output,
                               version=args.version, research=args.research)
    else:
        final = release.load_release(args.release)
        if args.command == 'prepare':
            release.publish(args.output, request_files(final), research=args.research)
        elif args.command == 'plan-template':
            from .main_v2_context import verify_context
            plan, files, raw = load_prepared(final, args.prepared)
            _, _, context_raw = verify_context(plan, files, raw, args.context)
            write_json(args.output, dict(decision='PENDING', author='', accepted_at='',
                **authorize_binding(final, raw, context_raw, args.dataset_id, args.database)))
        else:
            with closing(connect(read_settings(args.env_file), args.database)) as cn:
                repo = Repository(cn)
                if args.command == 'import-dataset':
                    result = import_dataset(repo, final)
                else:
                    result = materialize(repo, final, args.prepared, args.context, args.authorization,
                                         dataset_id=args.dataset_id, database=args.database)
                write_json(args.output, result)
    print('Completed '+args.command+'; model calls: 0; predictions: 0; receipt: '+str(args.output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
