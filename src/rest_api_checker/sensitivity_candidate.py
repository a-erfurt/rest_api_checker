"""Final sensitivity freeze: local immutable evidence, no acceptance or SQL writes."""
from dataclasses import asdict
import json
from pathlib import Path
import shutil

from . import freeze, sensitivity_freeze as sf, sensitivity_evaluation as se
from .experiment import parser, renderer, request
from .experiment.encoding import digest, encode
from .persistence.database import require
from .persistence.inspection import rows, portable
from .persistence.migrate import verify as verify_schema
from .persistence.repository import TABLES

DIRECTORY='artifacts/sensitivity_freeze_candidate_v2'
FORMAT='sensitivity-freeze-candidate-v2'
PRELIMINARY_SHA='716f379f0e6154daaf635ab964e2549ccfce13112df9fc73089afc1254b1a195'
SCHEDULE_SHA='0dbe99e7022f4dc46ece2a6127889b4f4c8a5822869557b332602f5221e0c700'


def sources(root,research):
    result=freeze.source_hashes(root,research)
    for p in (research/sf.BASE).glob('*sensitivity*'):
        if p.is_file():result['research:'+str(p.relative_to(research))]=digest(p.read_bytes())
    for pattern in ('tools/sensitivity_freeze/*.py','tests/*sensitivity*.py','tests/persistence/*sensitivity*.py'):
        for p in root.glob(pattern):result['implementation:'+str(p.relative_to(root))]=digest(p.read_bytes())
    return result


def row_hash(record):
    def safe(v):
        if isinstance(v,bytes):return dict(binary_sha256=digest(v),size_bytes=len(v))
        if isinstance(v,dict):return {k:safe(x) for k,x in v.items()}
        if isinstance(v,(tuple,list)):return [safe(x) for x in v]
        return portable(v)
    return digest(encode(safe(record)))


def baseline_rows(repo):
    return {t:{str(r['id']):row_hash(r) for r in rows(repo,t)} for t in TABLES}


def verify_database(candidate,repo):
    require(freeze.principal(repo.cn)==candidate['database']['principal'],'Application principal/database drift')
    require(verify_schema(repo.cn)==candidate['database']['schema_version'],'Schema drift')
    for table,records in candidate['baseline_rows'].items():
        current={str(r['id']):row_hash(r) for r in rows(repo,table)}
        require(all(current.get(i)==sha for i,sha in records.items()),'Historical database evidence changed: '+table)
    for item in candidate['request_inventory']:
        model=repo._row('models',item['model_id']);repo.require_d07(item['run_config_id'],model['name'])
        baseline=repo._row('experiment_runs',item['baseline_run_id'])
        require(baseline['experiment_id']==candidate['baseline']['experiment_id']
            and baseline['run_order']==item['baseline_run_order']
            and all(baseline[k]==item[k] for k in ('dataset_case_id','model_id','run_config_id','repetition','seed')),
            'Baseline request pairing drift')
        baseline_raw=repo.file(baseline['request_file_id'])
        require(digest(baseline_raw)==item['baseline_request_sha256'],'Baseline request drift')
    repo.verify_closure(candidate['files']);repo.cn.rollback()


def verify(candidate,root,research,directory,repo=None):
    from .sensitivity_execution import validate_request
    require(candidate['format']==FORMAT and candidate['status']=='NOT ACCEPTED'
        and candidate['instruction']=='DO NOT EXECUTE' and candidate['gate_b_complete'] is False
        and candidate['execution_blockers']==['EXACT_CANDIDATE_REVIEW_PENDING'], 'Final unaccepted candidate required')
    require(candidate['implementation_commit']==freeze.git(root,'rev-parse','HEAD'),'Execution commit drift')
    require(not freeze.git(root,'status','--porcelain','--untracked-files=all'),'Uncommitted implementation changes')
    require(candidate['sources']==sources(root,research),'Source inventory/hash drift')
    freeze.check_sources(candidate,root,research)
    sf.read_approval(research)
    require(candidate['research_commit']==freeze.git(research,'rev-parse','HEAD'),'Research commit drift')
    require(candidate['expected_runs']==108 and candidate['phase']=='prompt_sensitivity_development'
        and candidate['prompt']['id']==sf.PROMPT and candidate['prompt']['sha256']==sf.SHA
        and candidate['parent_prompt_sha256']==sf.PARENT_SHA,'Sensitivity identity drift')
    require(candidate['evaluator']==dict(version=se.VERSION,sha256=se.artifact_hash()),'D11 evaluator drift')
    require(candidate['parser']==dict(version=parser.VERSION,sha256=parser.artifact_hash())
        and candidate['renderer']==dict(version=renderer.VERSION,sha256=renderer.artifact_hash()),'Parser/renderer drift')
    expected=json.loads(sf.schedule_bytes())['slots']
    require(candidate['portable_schedule']==expected and candidate['schedule_sha256']==SCHEDULE_SHA
        and digest(sf.schedule_bytes())==SCHEDULE_SHA and (directory/'schedule.json').read_bytes()==sf.schedule_bytes(),
        'Sensitivity schedule drift')
    old_raw=(root/freeze.CANDIDATE).read_bytes();old=json.loads(old_raw)
    require(digest(old_raw)==candidate['baseline']['candidate_sha256'],'Historical comparison candidate drift')
    freeze.verify_historical(old,root,research)
    for key in ('dataset','dataset_manifest_sha256','references','models','runtime','native_runner','configuration','input_policy'):
        require(candidate[key]==old[key],'Original comparison binding drift: '+key)
    require(candidate['baseline']['implementation_commit']==old['implementation_commit']
        and candidate['baseline']['reuse_original_outcomes'] is True,'Baseline binding drift')
    for path,sha in candidate['artifacts'].items():
        require(not Path(path).is_absolute() and '..' not in Path(path).parts,'Unsafe artifact path')
        require(digest((directory/path).read_bytes())==sha,'Candidate artifact drift: '+path)
    context_raw=(directory/'context.json').read_bytes();context=json.loads(context_raw)
    require(digest(context_raw)==candidate['context_evidence_sha256'] and len(context['rows'])==108
        and context['study_generation_calls']==0,'Context evidence drift')
    require(len(candidate['request_inventory'])==108 and len(candidate['context_proofs'])==108,'Request/proof coverage')
    _,_,variant,parent=sf.read_approval(research)
    for slot,item,measurement in zip(expected,candidate['request_inventory'],context['rows']):
        require(all(item[k]==v and measurement[k]==v for k,v in slot.items()),'Context/request order drift')
        order=slot['run_order'];raw=(directory/item['request_path']).read_bytes();payload=json.loads(raw)
        model=next(m for m in candidate['models'] if m['name']==slot['model'])
        member=next(r for r in candidate['references'] if r['case']==slot['case'])['membership']
        baseline_slot=old['schedule'][item['baseline_run_order']-1]
        require(item['dataset_case_id']==member['id'] and all(item[k]==baseline_slot[k] for k in
                ('dataset_case_id','model_id','run_config_id','repetition','seed')),'Baseline pairing drift')
        evidence=payload['messages'][1]['content'].encode()
        baseline_request=request.build_request(renderer.Rendered(evidence,dict(rendered_evidence_sha256=digest(evidence))),
            prompt_name='P2',prompt=parent,model=slot['model'],model_digest=model['digest'],repetition=slot['repetition'])
        require(digest(baseline_request.body)==item['baseline_request_sha256'],'Original evidence/request drift')
        req=sf.variant_request(renderer.Rendered(evidence,dict(rendered_evidence_sha256=digest(evidence))),
            parent=parent,variant=variant,model=slot['model'],model_digest=model['digest'],repetition=slot['repetition'])
        validate_request(req)
        require(raw==req.body and digest(raw)==item['request_sha256']==measurement['request_sha256'],'Request drift')
        proof=request.ContextProof(digest(raw),model['digest'],model['template_sha256'],digest(context_raw),measurement['input_tokens'])
        require(candidate['context_proofs'][str(order)]==asdict(proof),'Context proof mismatch');proof.verify(req)
        debug=json.loads((directory/measurement['render_path']).read_bytes())
        tokens=json.loads((directory/measurement['tokens_path']).read_bytes())['tokens']
        require(not debug.get('done') and not debug.get('eval_count') and not debug.get('message',{}).get('content')
                and not debug.get('message',{}).get('thinking'),'Unexpected completion evidence')
        require(digest(debug['_debug_info']['rendered_template'].encode())==measurement['rendered_sha256']
            and digest(encode(tokens))==measurement['tokens_sha256'] and len(tokens)==measurement['input_tokens'],
            'Native context evidence drift')
    maxima={m:max(r['input_tokens'] for r in context['rows'] if r['model']==m) for m in request.MODELS}
    require(maxima==candidate['context_max_input_tokens']==context['max_input_tokens'], 'Context maxima drift')
    if repo is not None:verify_database(candidate,repo)
    return True


def build(repo,root,research,directory):
    require(not directory.exists(),'Preserve existing candidate; select a new version')
    preliminary=root/sf.DIRECTORY
    old_raw=(preliminary/'candidate.json').read_bytes()
    require(digest(old_raw)==PRELIMINARY_SHA,'Preliminary candidate drift')
    old=json.loads(old_raw)
    candidate,requests=sf.prepare(repo,root,research)
    require(candidate['schedule_sha256']==old['schedule_sha256']==SCHEDULE_SHA,'Schedule changed')
    for path,sha in old['artifacts'].items():
        require(digest((preliminary/path).read_bytes())==sha,'Preliminary artifact drift: '+path)
    for order,req in requests.items():
        require(req.body==(preliminary/f'requests/{order:03}.json').read_bytes(),'Unexpected request/context drift')
    freeze.verify_live(candidate,root)
    frozen_rows=baseline_rows(repo)
    candidate.update(format=FORMAT,status='NOT ACCEPTED',execution_blockers=['EXACT_CANDIDATE_REVIEW_PENDING'],
        evaluator=dict(version=se.VERSION,sha256=se.artifact_hash()),parent_prompt_sha256=sf.PARENT_SHA,
        sources=sources(root,research),baseline_rows=frozen_rows,preliminary_candidate_sha256=PRELIMINARY_SHA,
        files=[dict(file_id=r['id'],sha256=digest(repo.file(r['id']))) for r in rows(repo,'files')],
        context_evidence_sha256=old['context_evidence_sha256'],context_max_input_tokens=old['context_max_input_tokens'],
        context_reuse='Exact 108 request bytes and runtime/template/tokenizer identities reverified; original native measurements retained.')
    context=json.loads((preliminary/'context.json').read_bytes())
    candidate['context_proofs']={str(r['run_order']):asdict(request.ContextProof(r['request_sha256'],r['model_digest'],
        r['template_sha256'],candidate['context_evidence_sha256'],r['input_tokens'])) for r in context['rows']}
    directory.mkdir(parents=True)
    for path in old['artifacts']:
        if path.startswith(('requests/','native/')) or path in ('context.json','schedule.json','request_inventory.json'):
            target=directory/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(preliminary/path,target)
    candidate['artifacts']={str(p.relative_to(directory)):digest(p.read_bytes()) for p in sorted(directory.rglob('*')) if p.is_file()}
    verify(candidate,root,research,directory,repo)
    require(sf.snapshot(repo)==candidate['database']['before'],'Database changed during final freeze')
    raw=encode(candidate);(directory/'candidate.json').write_bytes(raw)
    (directory/'candidate.sha256').write_text(digest(raw)+'  candidate.json\n')
    return candidate
