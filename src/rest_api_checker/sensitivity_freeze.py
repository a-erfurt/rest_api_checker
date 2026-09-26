"""Candidate-only sensitivity preparation. No experiment or generation adapter.

The comparison implementation remains frozen. Only the system-message bytes
are substituted after exact approval verification; these requests cannot pass
its P1/P2/P3 execution allowlist.
"""
from dataclasses import asdict, replace
from datetime import datetime
import json
from pathlib import Path

from . import freeze, evaluation
from .experiment import request, renderer, schedule, parser
from .experiment.encoding import digest, encode
from .persistence.database import require
from .persistence.importer import load_development
from .persistence.inspection import bindings, portable, rows, status
from .persistence.migrate import verify
from .persistence.repository import TABLES

PROMPT = 'P2_SENSITIVITY_V1'
SHA = 'e8d256399192e3f3ed66c23c78b80dc976bb8adc5e422a49ce3401ad407926cc'
PARENT_SHA = '50bfce7831530c7d63dd469ed82fb9acab755bedf4808ae5574775fc5505594f'
REVIEW_SHA = '40092bb062fec5a0a64a3f8fa2b19d3278ad049b647c997c576f8476c43986ae'
BASE = '03_research_design/prompt_candidates_v1/'
MANIFEST = BASE + 'sensitivity_manifest_p2_v1.json'
DIRECTORY = 'artifacts/sensitivity_freeze_candidate_v1'
FORMAT = 'sensitivity-freeze-candidate-v1'
SCHEDULE_VERSION = 'sensitivity-p2-projection-v1'
BLOCKERS = ['EXACT_CANDIDATE_REVIEW_PENDING', 'SENSITIVITY_EXECUTION_ADAPTER_NOT_IMPLEMENTED',
            'D11_SENSITIVITY_EVALUATOR_NOT_IMPLEMENTED']


def read_approval(research):
    m = json.loads((research / MANIFEST).read_bytes())
    require(m['status'] == 'AUTHOR_APPROVED_EXACT_TEXTS'
            and m['exact_text_author_approval'] == 'AUTHOR_APPROVED', 'Approval missing')
    a = m['approval']['exact_text_approval_record']
    raw = (research / a['path']).read_bytes()
    require(digest(raw) == a['sha256'], 'Approval record drift')
    record = json.loads(raw)
    require(record['format'] == 'prompt-author-approval-reconciliation-v1'
            and record['status'] == 'AUTHOR_APPROVED_EXACT_TEXTS', 'Approval status')
    require(datetime.fromisoformat(record['recorded_at']).tzinfo is not None, 'Approval recording offset required')
    expected = dict(id=PROMPT, path=BASE+'p2_structured_checklist_sensitivity_v1.txt',
                    sha256=SHA, byte_length=5032)
    require(record['approved_candidates'] == [expected], 'Approval exact identity')
    prompt = (research / expected['path']).read_bytes()
    parent = (research / m['parent']['path']).read_bytes()
    require(digest(prompt) == SHA and len(prompt) == 5032, 'Approved prompt drift')
    require(digest(parent) == PARENT_SHA and len(parent) == 4996, 'Parent drift')
    review = m['semantic_equivalence_review']
    require(digest((research / review['path']).read_bytes()) == REVIEW_SHA
            and review['sha256'] == REVIEW_SHA and review['pass_count'] == 37
            and review['open_question_count'] == 0, 'Review drift')
    require(all(m['variant'][k] == v for k,v in expected.items()), 'Manifest identity drift')
    require(prompt.startswith((research / (BASE+'common_semantic_core_v1.txt')).read_bytes())
            and prompt.endswith((research / (BASE+'common_output_contract_v1.txt')).read_bytes()), 'Shared blocks drift')
    require([i for i,(a,b) in enumerate(zip(parent.splitlines(True),prompt.splitlines(True)),1) if a!=b] == [17,18,19]
            and len(parent.splitlines()) == len(prompt.splitlines()) == 24, 'Paraphrase scope drift')
    return m, record, prompt, parent


def schedule_bytes():
    slots = [replace(s, prompt=PROMPT, run_order=i) for i,s in enumerate(
        (s for s in schedule.comparison_schedule() if s.prompt=='P2'),1)]
    return encode(dict(format=SCHEDULE_VERSION, schedule_seed=schedule.SCHEDULE_SEED,
        algorithm='Order-preserving P2 projection of comparison-schedule-v1; rename prompt and renumber 1..108.',
        source_schedule_sha256=digest(schedule.dry_run_bytes()), non_dispatched=True,
        slots=[asdict(s) for s in slots]))


def variant_request(rendered, *, parent, variant, model, model_digest, repetition):
    require(digest(variant)==SHA, 'Variant drift')
    base = request.build_request(rendered, prompt_name='P2', prompt=parent, model=model,
                                 model_digest=model_digest, repetition=repetition)
    request.validate_request(base)
    body = json.loads(base.body)
    body['messages'][0]['content'] = variant.decode('utf-8')
    raw = encode(body)
    return request.Request(raw, {**base.metadata, 'prompt_name':PROMPT, 'prompt_sha256':SHA,
                                'rendered_request_sha256':digest(raw)})


def snapshot(repo):
    """Hash actual bytes in every domain row, including all archived file content."""
    def safe(v):
        if isinstance(v, bytes): return dict(binary_sha256=digest(v), size_bytes=len(v))
        if isinstance(v, dict): return {k:safe(x) for k,x in v.items()}
        if isinstance(v, (tuple,list)): return [safe(x) for x in v]
        return portable(v)
    result = {}
    for table in TABLES:
        records = rows(repo, table)
        result[table] = dict(count=len(records), sha256=digest(encode(safe(records))))
    return result


def prepare(repo, root, research):
    """SELECT-only reconstruction from the accepted comparison and released data."""
    m, approval, variant, parent = read_approval(research)
    require(not freeze.git(root,'status','--porcelain','--untracked-files=no'), 'Commit implementation first')
    before = snapshot(repo)
    require(len(rows(repo,'experiments')) == 1, 'Unexpected experiment inventory')
    state = status(repo,1)
    require(state['planned']==state['completed']==324 and state['pending']==0, 'Comparison incomplete')
    require(state['experiment']['kind']=='comparison', 'Baseline phase')
    setup_raw = repo.file(state['experiment']['setup_file_id'])
    setup = json.loads(setup_raw)
    old_raw = repo.file(setup['author_candidate_file_id'])
    acceptance_raw = repo.file(setup['author_acceptance_file_id'])
    old = json.loads(old_raw)
    freeze.require_acceptance(old_raw,json.loads(acceptance_raw))
    require(digest(old_raw)==setup['author_candidate_sha256']
            and digest(acceptance_raw)==setup['author_acceptance_sha256'], 'Baseline acceptance drift')
    freeze.check_sources(old,root,research)
    require(bindings(repo,1,old['schedule'])==old['bindings'], 'Baseline bindings drift')
    repo.verify_closure(setup['files'])
    reports = rows(repo,'evaluation_reports',experiment_id=1)
    require(len(reports)==1, 'Review baseline report inventory explicitly')
    report_raw = repo.file(reports[0]['file_id'])
    report = json.loads(report_raw)
    require(report['selected_prompt']=='P2', 'Persisted selection is not P2')
    require(old['evaluator']['sha256']==evaluation.artifact_hash(), 'Evaluator drift')
    manifest, closure = load_development(root/'artifacts/development_dataset_v1',
                                      root/'docs/development_dataset_v1_release.json',research)
    source_cases={c['case_id']:c for c in manifest['cases']}
    members={c['case_code']:c for c in rows(repo,'dataset_cases',dataset_id=1)}
    rendered={}
    for code,member in members.items():
        case=repo._row('test_cases',member['case_id']); source=source_cases[code]
        require(repo.source(case['source_file_id'],case['source_pointer'])==source, 'SQL case drift')
        ref=repo._row('reference_results',member['reference_id'])
        require(repo.source(ref['source_file_id'],ref['source_pointer'])==source['oracle']
                and all(ref[c]==source['oracle'][c] for c in ('c1','c2','c3')), 'Reference drift')
        op=repo._row('api_operations',case['operation_id'])
        contract=repo._row('api_contracts',op['contract_id']); response=repo._row('responses',case['response_id'])
        rendered[code]=renderer.render(renderer.Evidence(repo.file(contract['file_id']),op['http_method'],op['path_template'],
            response['status_code'],response['content_type'],repo.file(response['body_file_id'])),
            contract_identity=f'files:{contract["file_id"]}',body_identity=f'files:{response["body_file_id"]}')
    models={v['name']:v for v in old['bindings']['models']}
    prompts={v['id']:v['name'] for v in old['bindings']['prompts']}
    baseline={}
    model_names={v['id']:v['name'] for v in models.values()}
    member_names={v['id']:k for k,v in members.items()}
    for run in state['runs']:
        if prompts[run['prompt_id']]=='P2':
            baseline[(member_names[run['dataset_case_id']],model_names[run['model_id']],run['repetition'])]=run
    inventory=[]; requests={}
    for slot in json.loads(schedule_bytes())['slots']:
        model=slot['model']; run=baseline[(slot['case'],model,slot['repetition'])]
        repo.require_d07(run['run_config_id'],model)
        expected=request.build_request(rendered[slot['case']],prompt_name='P2',prompt=parent,model=model,
            model_digest=models[model]['digest'],repetition=slot['repetition'])
        require(expected.body==repo.file(run['request_file_id']), 'Baseline request reconstruction drift')
        req=variant_request(rendered[slot['case']],parent=parent,variant=variant,model=model,
            model_digest=models[model]['digest'],repetition=slot['repetition'])
        requests[slot['run_order']]=req
        inventory.append(dict(**slot, request_sha256=digest(req.body),request_path=f'requests/{slot["run_order"]:03}.json',
            baseline_run_id=run['id'],baseline_run_order=run['run_order'],baseline_request_sha256=digest(expected.body),
            dataset_case_id=run['dataset_case_id'],model_id=run['model_id'],run_config_id=run['run_config_id'],
            prompt_id=None, prompt_not_registered=True))
    sources=freeze.source_hashes(root,research)
    for p in (research/BASE).rglob('*'):
        if p.is_file() and ('sensitivity' in p.name): sources['research:'+str(p.relative_to(research))]=digest(p.read_bytes())
    for pattern in ('tools/sensitivity_freeze/*.py','tests/test_sensitivity_freeze.py'):
        for p in root.glob(pattern): sources['implementation:'+str(p.relative_to(root))]=digest(p.read_bytes())
    result=dict(format=FORMAT,status='NOT YET EXECUTABLE',instruction='DO NOT EXECUTE',gate_b_complete=False,
        freeze_review='PENDING_EXPLICIT_REVIEW_OF_EXACT_CANDIDATE_SHA256',execution_blockers=BLOCKERS,
        phase='prompt_sensitivity_development',created_at=datetime.now().astimezone().isoformat(),
        implementation_commit=freeze.git(root,'rev-parse','HEAD'),research_commit=freeze.git(research,'rev-parse','HEAD'),
        research_working_tree=freeze.git(research,'status','--porcelain'),sources=sources,
        approval=m['approval']['exact_text_approval_record'],prompt=m['variant'],selected_prompt='P2',
        semantic_equivalence_review=m['semantic_equivalence_review'],construction_disclosure=m['boundaries']['author_result_exposure'],
        baseline=dict(experiment_id=1,setup_sha256=digest(setup_raw),candidate_sha256=digest(old_raw),
            acceptance_sha256=digest(acceptance_raw),implementation_commit=old['implementation_commit'],
            report=portable(reports[0]),report_sha256=digest(report_raw),reuse_original_outcomes=True),
        database=dict(schema_version=verify(repo.cn),principal=freeze.principal(repo.cn),before=before),
        schedule_version=SCHEDULE_VERSION,schedule_seed=schedule.SCHEDULE_SEED,
        schedule_sha256=digest(schedule_bytes()),expected_runs=108,portable_schedule=json.loads(schedule_bytes())['slots'],
        request_inventory=inventory,sql_schedule_persisted=False,
        evaluator=dict(**old['evaluator'],sensitivity_implementation=None,
            required_logic='Prompt Development Protocol v1 sections 6 and 9 / D11; paired descriptive sensitivity metrics; no recomputation in this preparation.'),
        **{k:old[k] for k in ('dataset','dataset_manifest_sha256','references','models','runtime','native_runner',
                              'configuration','renderer','parser','input_policy','bindings')})
    require(snapshot(repo)==before,'Database changed during preparation');repo.cn.rollback()
    return portable(result), requests


def verify_bundle(candidate, root, research, directory, repo):
    require(candidate['format']==FORMAT and candidate['status']=='NOT YET EXECUTABLE'
            and candidate['instruction']=='DO NOT EXECUTE' and not candidate['gate_b_complete']
            and candidate['execution_blockers']==BLOCKERS, 'Non-executable candidate required')
    fresh, requests=prepare(repo,root,research)
    for key,value in fresh.items():
        if key!='created_at': require(candidate[key]==value, 'Candidate drift: '+key)
    require((directory/'schedule.json').read_bytes()==schedule_bytes(),'Schedule artifact drift')
    context=json.loads((directory/'context.json').read_bytes())
    require(len(context['rows'])==108 and context['study_generation_calls']==0, 'Context inventory')
    seen=set()
    for item in context['rows']:
        order=item['run_order'];require(order not in seen,'Duplicate context row');seen.add(order)
        req=requests[order]
        require((directory/f'requests/{order:03}.json').read_bytes()==req.body,'Request artifact drift')
        proof=request.ContextProof(item['request_sha256'],item['model_digest'],item['template_sha256'],
            digest((directory/'context.json').read_bytes()),item['input_tokens'])
        proof.verify(req)
        identity=next(m for m in candidate['models'] if m['name']==req.metadata['model'])
        require(item['template_sha256']==identity['template_sha256'],'Template drift')
        debug=json.loads((directory/item['render_path']).read_bytes())
        text=debug['_debug_info']['rendered_template']
        tokens=json.loads((directory/item['tokens_path']).read_bytes())['tokens']
        require(not debug.get('done') and not debug.get('eval_count')
                and not debug.get('message',{}).get('content'),'Unexpected completion')
        require(digest(text.encode())==item['rendered_sha256'] and len(tokens)==item['input_tokens']
                and digest(encode(tokens))==item['tokens_sha256'],'Token/render evidence drift')
    require(set(requests)==seen,'Context coverage')
    require(candidate['context_evidence_sha256']==digest((directory/'context.json').read_bytes()),'Context binding')
    for path,sha in candidate['artifacts'].items():
        require(digest((directory/path).read_bytes())==sha,'Local evidence drift: '+path)
    return True
