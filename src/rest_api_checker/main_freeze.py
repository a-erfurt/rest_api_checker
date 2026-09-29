"""Mechanical admission of the author-frozen final release; no provider calls.

Authority: research/04_case_studies/main_experiment_freeze_v1. Original source
bytes are archived alongside a lossless relational projection. No labels are
computed here, and no attempt is reserved by preparation.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess

from .experiment import parser, renderer, request
from .experiment.encoding import digest, encode
from .persistence.database import json_bytes, lock, pointer, require
from .persistence.inspection import bindings, portable, rows

DATASET = 'FINAL_EVALUATION_DATASET_V1'
NAME = 'MAIN_EVALUATION_V1'
VERSION = '1.0'
ROOT = '97510f5ef0df0f680a0f420a5bc9d496d81cd5166f2d4416081c70b5d5466b75'
P2 = '50bfce7831530c7d63dd469ed82fb9acab755bedf4808ae5574775fc5505594f'
ORDER = ['FC-EDX-001', 'FC-EDX-002', 'FC-EDX-005', 'FC-EDX-006'] + [f'FC-HTTS-{i:03}' for i in range(1, 11)]
SCHEDULE = 'main-evaluation-schedule-v1'
SEED = 20260925
NAMESPACE = DATASET + '/' + VERSION
ORIGINS = dict(NATURAL='natural_observation', CONSTRUCTED_CONTROL='synthetic_conformant_control',
               CONSTRUCTED_INCONSISTENCY='synthetic_inconsistency')


def order():
    result = []
    for model in request.MODELS:
        block = [(case, rep) for case in ORDER for rep in request.SEEDS]
        counter = 0
        for i in range(len(block)-1, 0, -1):
            limit = 2**256 - 2**256 % (i+1)
            while True:
                number = int(digest(f'{SCHEDULE}\n{SEED}\n{model}\n{counter}\n'.encode()), 16)
                counter += 1
                if number < limit:
                    break
            j = number % (i+1)
            block[i], block[j] = block[j], block[i]
        result.extend((case, model, rep) for case, rep in block)
    return result


class Release:
    """Root-bound current research files and historical technical source closure."""
    def __init__(self, research, technical):
        research, technical = Path(research), Path(technical)
        self.roots = dict(research=research, technical=technical,
                          legacy=research.parent/'api-contract-detector',
                          htts_inputs=research.parent/'htts_parent_candidates')
        prefix = '04_case_studies/final_evaluation_dataset_v1/'
        raw = (research/prefix/'freeze_manifest.json').read_bytes()
        require(digest(raw) == ROOT, 'Final dataset root mismatch')
        self.freeze = json.loads(raw)
        self.sources = {}
        self.inventory = self.freeze['files'] + [dict(repository='research',
            path=prefix+'freeze_manifest.json', sha256=ROOT, bytes=len(raw))]
        for item in self.inventory:
            path = Path(item['path']); repository = item['repository']
            require(not path.is_absolute() and '..' not in path.parts, 'Unsafe source path')
            if repository == 'technical' and not str(path).startswith('artifacts/'):
                # Historical dataset authority stays at its original source commit.
                content = subprocess.check_output(['git', '-C', str(technical), 'show',
                    self.freeze['source_commits']['technical']+':'+str(path)])
            else:
                content = (self.roots[repository]/path).read_bytes()
            require(digest(content) == item['sha256'] and len(content) == item['bytes'],
                    'Frozen source changed: '+repository+':'+str(path))
            self.sources[repository, str(path)] = content
        self.manifest = json.loads(self.sources['research', prefix+'dataset_manifest.json'])
        m = self.manifest
        require((m['name'], m['version'], m['purpose'], m['status']) ==
                (DATASET, VERSION, 'evaluation', 'FROZEN'), 'Wrong release identity')
        require(m['ordered_case_ids'] == ORDER == [c['case_id'] for c in m['cases']]
                and [c['position'] for c in m['cases']] == list(range(1, 15)), 'Membership changed')

    def raw(self, descriptor):
        content = self.sources[descriptor.get('repository', 'research'), descriptor['path']]
        require(digest(content) == descriptor['sha256'] and len(content) == descriptor['bytes'],
                'Descriptor mismatch')
        return content

    def projection(self):
        parents, cases = {}, []
        for c in self.manifest['cases']:
            proposal = json.loads(self.raw(c['oracle_result']))
            accepted = pointer(json.loads(self.raw(c['manual_ground_truth'])), c['manual_ground_truth']['pointer'])
            vector = [c['reference_vector'][k] for k in ('c1', 'c2', 'c3')]
            require(accepted['case_id'] == c['case_id'] == proposal['case_id']
                    and accepted['human_decision'] == 'ACCEPT' and accepted['state'] == 'ACCEPTED'
                    and accepted['oracle_result']['sha256'] == c['oracle_result']['sha256']
                    and accepted['confirmed_reference_vector'] == c['reference_vector']
                    and proposal['vector'] == vector
                    and accepted['confirmed_overall'] == c['overall'] == proposal['overall'],
                    'Accepted reference binding mismatch')
            body = self.raw(c['response_artifacts']['response_body.bin'])
            require(digest(body) == c['body_sha256'] and len(body) == c['body_bytes'], 'Body mismatch')
            require(self.raw(c['response_artifacts']['status.txt']).decode() == str(c['supplied_http_status'])
                    and self.raw(c['response_artifacts']['content_type.txt']).decode() == c['raw_content_type'],
                    'Raw response envelope mismatch')
            record = dict(case_id=c['case_id'], api=c['api'].lower(), operation=c['operation'],
                root_family=c['cap_family_id'], origin=ORIGINS[c['provenance_class']],
                immediate_parent=c['immediate_parent_id'], contract_sha256=c['contract_sha256'],
                status=c['supplied_http_status'], content_type=c['raw_content_type'],
                body=c['response_artifacts']['response_body.bin'], contract=c['contract_snapshot'],
                original_release_case=deepcopy(c), accepted_reference=accepted,
                oracle={**proposal['oracle_result'], 'vector':vector, 'overall':c['overall']},
                reference_rationale=proposal['rationale'])
            require([record['oracle'][k] for k in ('c1','c2','c3')] == vector, 'Reference vector drift')
            cases.append(record)
            parent = c['root_id']
            if parent in parents:
                continue
            base = {k:deepcopy(record[k]) for k in ('api','operation','root_family','contract_sha256','contract')}
            base.update(case_id=parent, immediate_parent=None, membership=False)
            if parent.startswith('BT-'):
                path = f'04_case_studies/final_evaluation_bases_v1/bases/{parent}/metadata.json'
                meta = json.loads(self.sources['research', path])
                desc = {**meta['artifacts']['response_body.bin'],
                        'path':'04_case_studies/final_evaluation_bases_v1/'+meta['artifacts']['response_body.bin']['path']}
                self.raw(desc)
                require(meta['contract_sha256'] == c['contract_sha256'] and meta['operation'] == c['operation']
                        and c['cap_family_id'] in meta['construction_family_ids'], 'Base lineage mismatch')
                base.update(origin='synthetic_conformant_control', status=meta['supplied_http_status'],
                    content_type=meta['raw_content_type'], body=desc, original_base_metadata=meta,
                    mapping_note='Unscored accepted contract-derived base; origin is a schema mapping, not a new reference.')
            else:
                require(parent == 'HTTS-PO-0003' and c['provenance_class'] == 'NATURAL', 'Unknown natural root')
                desc = next(d for d in c['natural_source_bindings'] if d['path'].endswith('/response_body.bin'))
                require(self.raw(desc) == body, 'Natural observation alias mismatch')
                base.update(origin='natural_observation', status=c['supplied_http_status'],
                    content_type=c['raw_content_type'], body=desc,
                    original_natural_bindings=c['natural_source_bindings'],
                    mapping_note='Unscored source observation; FC-HTTS-009 is its released natural alias.')
            parents[parent] = base
        require(len(parents) == 7, 'Unexpected ancestry')
        return dict(format='final-evaluation-sql-projection-v1', dataset_root=ROOT,
                    reference_revision=1, reference_revision_note='SQL adapter revision; original accepted source revisions/pointers retained.',
                    observed_at_note='No new acquisition timestamp inferred; original start/end/provenance bytes archived.',
                    parents=list(parents.values()), cases=cases)


def import_release(repo, release):
    """All-or-nothing import; unchanged repeat import is idempotent."""
    projection = release.projection()
    with repo.transaction():
        lock(repo.cn, NAMESPACE)
        dataset_id = repo.dataset(DATASET, VERSION, 'evaluation')
        archived = []
        for item in release.inventory:
            raw = release.sources[item['repository'], item['path']]
            file_id = repo.archive(item['path'], raw)
            archived.append({**item, 'file_id':file_id})
        source_id = repo.archive('final-evaluation-sql-projection-v1.json', encode(projection))
        case_ids, member_ids = {}, {}
        for collection in ('parents', 'cases'):
            for index, record in enumerate(projection[collection]):
                api_rows = rows(repo, 'apis', name=record['api'])
                api_id = api_rows[0]['id'] if api_rows else repo.api(record['api'])
                raw = release.raw(record['contract'])
                contract_id = repo.contract(api_id, repo.archive(record['contract']['path'], raw), json.loads(raw)['openapi'])
                operation_id = repo.operation(contract_id, record['operation']['method'], record['operation']['path'])
                family_id = repo.family(api_id, record['root_family'])
                existing = rows(repo, 'test_cases', source_namespace=NAMESPACE, native_case_id=record['case_id'])
                body_id = repo.archive(record['body']['path'], release.raw(record['body']))
                response_id = existing[0]['response_id'] if existing else repo.response(record['status'], record['content_type'], body_id)
                cid = repo.case(source_namespace=NAMESPACE, native_case_id=record['case_id'], operation_id=operation_id,
                    response_id=response_id, family_id=family_id, origin=record['origin'],
                    parent_case_id=case_ids.get(record['immediate_parent']), source_file_id=source_id,
                    source_pointer=f'/{collection}/{index}')
                case_ids[record['case_id']] = cid
                if collection == 'cases':
                    rid = repo.reference(cid, 1, source_id, f'/cases/{index}/oracle')
                    member_ids[record['case_id']] = repo.membership(dataset_id, cid, rid, record['case_id'], index+1)
        require(len(rows(repo, 'dataset_cases', dataset_id=dataset_id)) == 14, 'Unexpected dataset members')
        result = dict(dataset_id=dataset_id, dataset_root=ROOT, source_file_id=source_id,
                      projection_sha256=digest(encode(projection)), memberships=member_ids,
                      cases=case_ids, archived_sources=archived)
        verify_import(repo, release, result)
        return result


def verify_import(repo, release, imported):
    require(repo.file(imported['source_file_id']) == encode(release.projection()), 'Projection roundtrip mismatch')
    for source in imported['archived_sources']:
        require(repo.file(source['file_id']) == release.raw(source), 'Source roundtrip mismatch')
    members = sorted(rows(repo, 'dataset_cases', dataset_id=imported['dataset_id']), key=lambda r:r['position'])
    require([m['case_code'] for m in members] == ORDER, 'SQL membership order mismatch')
    for member, frozen in zip(members, release.manifest['cases'], strict=True):
        case = repo._row('test_cases', member['case_id'])
        repo.case(**{k:v for k,v in case.items() if k != 'id'})
        ref = repo._row('reference_results', member['reference_id'])
        require(ref['case_id'] == case['id'] and ref['version'] == 1 and member['position'] == frozen['position'], 'SQL reference owner/revision mismatch')
        repo.reference(case['id'], 1, ref['source_file_id'], ref['source_pointer'], ref['notes'])
        require({k:ref[k] for k in ('c1','c2','c3')} == frozen['reference_vector'], 'SQL reference vector mismatch')
    return True


def plan_main(repo, imported, setup):
    """Persist only 126 logical slots. No attempts, predictions or authorization."""
    with repo.transaction():
        lock(repo.cn, NAME+'/'+VERSION)
        ds = repo._row('datasets', imported['dataset_id'])
        require((ds['name'], ds['version'], ds['purpose']) == (DATASET,VERSION,'evaluation'), 'Main dataset required')
        require(setup['format'] == 'main-evaluation-setup-v1' and setup['version'] == VERSION
                and setup['dataset_root'] == ROOT and setup['execution_authorized'] is False
                and setup['metrics_version'] == 'main-evaluation-metrics-v1', 'Main setup identity mismatch')
        require(setup['parser_sha256'] == parser.artifact_hash() and setup['renderer_sha256'] == renderer.artifact_hash(), 'Qualified parser/renderer changed')
        schedule = setup['schedule']
        require(len(schedule) == 126 and setup['schedule_seed'] == SEED and setup['schedule_version'] == SCHEDULE
                and setup['dataset_id'] == ds['id'], 'Main schedule identity mismatch')
        for n, (slot, (case, model, rep)) in enumerate(zip(schedule, order(), strict=True), 1):
            require(set(slot) == {'dataset_case_id','model_id','prompt_id','run_config_id','repetition','seed','run_order'}, 'Unexpected schedule fields')
            require(slot['dataset_case_id'] == imported['memberships'][case] and slot['run_order'] == n
                    and slot['repetition'] == rep and slot['seed'] == request.SEEDS[rep], 'Main schedule drift')
            model_row = repo._row('models',slot['model_id'])
            require(model_row['name'] == model and model_row['digest'] == setup['model_digests'][model], 'Model identity drift')
            repo.require_d07(slot['run_config_id'], model)
            p = repo._row('prompts',slot['prompt_id'])
            require(p['name'] == 'P2' and digest(repo.file(p['file_id'])) == P2, 'Main prompt drift')
        repo.verify_closure(setup['files'])
        bound = bindings(repo, ds['id'], schedule)
        for member in bound['dataset_cases']:
            case = repo._row('test_cases', member['case_id'])
            ref = repo._row('reference_results', member['reference_id'])
            repo.case(**{k:v for k,v in case.items() if k != 'id'})
            require(ref['case_id'] == case['id'], 'Main reference/case mismatch')
            repo.reference(case['id'], ref['version'], ref['source_file_id'], ref['source_pointer'], ref['notes'])
        require(setup.get('bindings', bound) == bound, 'Main DB bindings drift')
        payload = {**setup, 'bindings':bound}
        existing = [e for e in rows(repo,'experiments') if e['name'] == NAME or e['dataset_id'] == ds['id']]
        if existing:
            require(len(existing) == 1 and existing[0]['name'] == NAME and existing[0]['kind'] == 'evaluation'
                    and existing[0]['dataset_id'] == ds['id']
                    and repo.file(existing[0]['setup_file_id']) == json_bytes(payload), 'Conflicting Main experiment')
            experiment_id = existing[0]['id']
            actual = rows(repo,'experiment_runs',experiment_id=experiment_id)
            require([{k:r[k] for k in schedule[0]} for r in actual] == schedule, 'Existing Main schedule drift')
            return experiment_id, [r['id'] for r in actual]
        setup_id = repo.archive('main-evaluation-setup-v1.json', json_bytes(payload))
        experiment_id = repo._insert('experiments', name=NAME, kind='evaluation', dataset_id=ds['id'],
            setup_file_id=setup_id, schedule_seed=SEED, started_at=None, finished_at=None, notes='Version 1.0; separate explicit execution authorization required.')
        run_ids = [repo._insert('experiment_runs', experiment_id=experiment_id, dataset_id=ds['id'], **s) for s in schedule]
        return experiment_id, run_ids


def pristine(repo, experiment_id):
    exp = repo._row('experiments',experiment_id)
    actual = rows(repo,'experiment_runs',experiment_id=experiment_id)
    require(exp['started_at'] is None and exp['finished_at'] is None and len(actual) == 126, 'Main already started/incomplete')
    for run in actual:
        require(all(run[k] is None for k in ('started_at','finished_at','result','request_file_id')),
                'Main run is no longer pristine')
        require(not rows(repo,'run_attempts',run_id=run['id']) and not rows(repo,'predictions',run_id=run['id']), 'Main attempt/output exists')
    require(not rows(repo,'evaluation_reports',experiment_id=experiment_id), 'Main report exists')
    return dict(logical_runs=126, attempts=0, predictions=0, evaluation_reports=0, executed=0)
