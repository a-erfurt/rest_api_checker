"""Hash-accepted sensitivity adapter over the qualified sequential attempt lifecycle."""
import argparse
from contextlib import closing
from dataclasses import asdict
import json
from pathlib import Path

from . import accepted_comparison, freeze, sensitivity_freeze as sf
from .experiment import batch, orchestration, parser, renderer, request
from .experiment.encoding import digest, encode
from .experiment.provider import OllamaClient
from .persistence import spool
from .persistence.database import connect, read_settings, require, timestamp
from .persistence.inspection import bindings, rows
from .persistence.repository import Repository

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT.parent/'bachelor_rest_api_checker'


def validate_request(req):
    require(type(req) is request.Request and req.timeout==request.TIMEOUT, 'Request type/timeout drift')
    _,_,variant,parent = sf.read_approval(RESEARCH)
    body = json.loads(req.body)
    evidence = body['messages'][1]['content'].encode()
    require(digest(evidence)==req.metadata['rendered_evidence_sha256'], 'Evidence hash drift')
    expected = sf.variant_request(renderer.Rendered(evidence,req.metadata),parent=parent,variant=variant,
        model=req.metadata['model'],model_digest=req.metadata['model_digest'],repetition=req.metadata['repetition'])
    require(req.body==expected.body and req.metadata==expected.metadata, 'Sensitivity request drift')


def require_acceptance(raw, record):
    value=json.loads(raw)
    require(value.get('format')=='sensitivity-freeze-candidate-v2'
        and value.get('status')=='NOT ACCEPTED' and value.get('instruction')=='DO NOT EXECUTE'
        and value.get('gate_b_complete') is False
        and value.get('execution_blockers')==['EXACT_CANDIDATE_REVIEW_PENDING'], 'Final sensitivity candidate required')
    require(record.get('decision')=='AUTHOR_ACCEPTED_FOR_P2_SENSITIVITY'
        and record.get('candidate_sha256')==digest(raw), 'Explicit final sensitivity acceptance required')
    require(type(record.get('author')) is str and bool(record['author'].strip()), 'Named author required')
    timestamp(record.get('accepted_at'))
    require(record.get('accepted_at') is not None, 'Acceptance time required')
    return True


def authorization(candidate_path, acceptance_path):
    raw=Path(candidate_path).read_bytes(); approval=Path(acceptance_path).read_bytes()
    require_acceptance(raw,json.loads(approval))
    return raw,approval,json.loads(raw)


def sql_schedule(candidate,prompt_id):
    return [dict(dataset_case_id=r['dataset_case_id'],model_id=r['model_id'],prompt_id=prompt_id,
        run_config_id=r['run_config_id'],repetition=r['repetition'],seed=r['seed'],run_order=r['run_order'])
        for r in candidate['request_inventory']]


def prepare_request(repo, run_id):
    inputs=repo.execution_inputs(run_id); run=inputs['run']; setup=inputs['setup']
    require(repo._row('experiments',run['experiment_id'])['kind']=='sensitivity', 'Wrong execution phase')
    require(inputs['prompt_name']==sf.PROMPT and digest(inputs['prompt'])==sf.SHA, 'Sensitivity prompt drift')
    require(run['seed']==request.SEEDS.get(run['repetition']), 'Sensitivity seed drift')
    require(setup['parser_sha256']==parser.artifact_hash() and setup['renderer_sha256']==renderer.artifact_hash(),
            'Parser/renderer drift')
    _,_,variant,parent=sf.read_approval(RESEARCH)
    rendered=renderer.render(inputs['evidence'],contract_identity=inputs['contract_identity'],body_identity=inputs['body_identity'])
    req=sf.variant_request(rendered,parent=parent,variant=variant,model=inputs['model']['name'],
        model_digest=inputs['model']['digest'],repetition=run['repetition'])
    validate_request(req)
    expected=next(r for r in setup['request_inventory'] if r['run_order']==run['run_order'])
    require(expected['request_sha256']==digest(req.body), 'Frozen request hash drift')
    return inputs,req


def accepted_setup(repo,raw,approval,candidate):
    require_acceptance(raw,json.loads(approval))
    _,_,variant,_=sf.read_approval(RESEARCH)
    files=[]
    for name,content in (('accepted-sensitivity-candidate.json',raw),('sensitivity-acceptance.json',approval),
                         ('p2_structured_checklist_sensitivity_v1.txt',variant)):
        identity=repo.archive(name,content);files.append(dict(file_id=identity,sha256=digest(content)))
    parents=[p for p in rows(repo,'prompts') if p['name']=='P2'
             and digest(repo.file(p['file_id']))==sf.PARENT_SHA]
    require(len(parents)==1,'Exact parent P2 required')
    prompt_id=repo.prompt(sf.PROMPT,'v1',parents[0]['strategy'],files[2]['file_id'],parent_prompt_id=parents[0]['id'])
    schedule=sql_schedule(candidate,prompt_id)
    return {**candidate,'files':files+candidate['files'],'fabricated':False,'gate_b_complete':True,
        'author_candidate_file_id':files[0]['file_id'],'author_acceptance_file_id':files[1]['file_id'],
        'author_candidate_sha256':digest(raw),'author_acceptance_sha256':digest(approval),
        'dataset_id':candidate['dataset']['id'],'schedule':schedule,
        'bindings':bindings(repo,candidate['dataset']['id'],schedule),
        'parser_sha256':candidate['parser']['sha256'],'renderer_sha256':candidate['renderer']['sha256']}


def require_persisted(repo,experiment_id,raw,approval,candidate,*,finish_read=True):
    require_acceptance(raw,json.loads(approval))
    exp=repo._row('experiments',experiment_id)
    require(exp['kind']=='sensitivity' and exp['dataset_id']==candidate['dataset']['id'], 'Wrong persisted phase/dataset')
    setup=json.loads(repo.file(exp['setup_file_id']))
    require(setup.get('gate_b_complete') is True and setup.get('fabricated') is False
        and repo.file(setup['author_candidate_file_id'])==raw and repo.file(setup['author_acceptance_file_id'])==approval
        and setup['author_candidate_sha256']==digest(raw) and setup['author_acceptance_sha256']==digest(approval),
        'Persisted sensitivity acceptance mismatch')
    for key,value in candidate.items():
        if key not in ('files','gate_b_complete','bindings'):
            require(setup.get(key)==value,'Accepted sensitivity setup drift: '+key)
    bound=bindings(repo,exp['dataset_id'],setup['schedule'])
    require(bound==setup['bindings'] and len(bound['prompts'])==1,'Sensitivity relational binding drift')
    prompt=bound['prompts'][0]
    require(prompt['name']==sf.PROMPT and digest(repo.file(prompt['file_id']))==sf.SHA,'Persisted prompt drift')
    require(setup['schedule']==sql_schedule(candidate,prompt['id']),'Persisted schedule drift')
    actual=rows(repo,'experiment_runs',experiment_id=experiment_id)
    require([{k:r[k] for k in setup['schedule'][0]} for r in actual]==setup['schedule'], 'Missing/duplicate/drifted persisted runs')
    repo.verify_closure(setup['files'])
    if finish_read:repo.cn.commit()


def run_accepted(repo,experiment_id,raw,approval,candidate,root,research,directory,spool_directory,**kwargs):
    from . import sensitivity_candidate as sc
    require_persisted(repo,experiment_id,raw,approval,candidate)
    def verify_runtime(req,proof):
        sc.verify(candidate,root,research,directory,repo)
        require(asdict(proof) in candidate['context_proofs'].values(), 'Unbound context proof')
        proof.verify(req)
        return freeze.verify_live(candidate,root)
    return batch.run(repo,experiment_id,client=OllamaClient(request_validator=validate_request),
        spool_directory=spool_directory,verify_runtime=verify_runtime,prepare_request=prepare_request,
        review_failure=lambda receipt,provider:'ambiguous',**kwargs)


def main(argv=None):
    from . import sensitivity_candidate as sc
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','run','reconcile'))
    p.add_argument('--candidate',type=Path,required=True);p.add_argument('--acceptance',type=Path,required=True)
    p.add_argument('--env-file',type=Path,default=Path.home()/'.config/rest-api-checker/application-credentials.env')
    p.add_argument('--experiment-id',type=int);p.add_argument('--spool',type=Path);p.add_argument('--technical-review',type=Path)
    args=p.parse_args(argv)
    raw,approval,candidate=authorization(args.candidate,args.acceptance)
    directory=args.candidate.parent
    sc.verify(candidate,ROOT,RESEARCH,directory)  # Before SQL or provider access.
    with closing(connect(read_settings(args.env_file),'rest_api_checker')) as cn:
        repo=Repository(cn);sc.verify(candidate,ROOT,RESEARCH,directory,repo)
        if args.action=='prepare':
            require(len(rows(repo,'experiments'))==1, 'Unexpected experiment inventory; never implicitly reschedule')
            freeze.verify_live(candidate,ROOT)
            with repo.transaction():
                setup=accepted_setup(repo,raw,approval,candidate)
                experiment,runs=repo.plan_experiment(name='Author-accepted P2 wording sensitivity',kind='sensitivity',
                    dataset_id=setup['dataset_id'],schedule_seed=setup['schedule_seed'],setup=setup,schedule=setup['schedule'])
            result=dict(experiment_id=experiment,logical_runs=len(runs),dispatched=False)
        else:
            require(args.experiment_id is not None and args.spool is not None,'Experiment ID and spool required')
            require_persisted(repo,args.experiment_id,raw,approval,candidate)
            if args.action=='run':
                result=run_accepted(repo,args.experiment_id,raw,approval,candidate,ROOT,RESEARCH,directory,args.spool)
            else:
                require(args.technical_review is not None,'Explicit spool-bound review required')
                review=args.technical_review.read_bytes();record=json.loads(review)
                attribution=accepted_comparison.technical_review(args.spool,record)
                _,value,_=spool.read(args.spool)
                require(repo._row('experiment_runs',value['run_id'])['experiment_id']==args.experiment_id,'Wrong spool experiment')
                repo.archive('sensitivity-technical-review-'+digest(review)+'.json',review)
                result=dict(result=orchestration.reconcile_attempt(repo,args.spool,review_failure=lambda r,p:attribution),dispatched=False)
    print(json.dumps(result,sort_keys=True));return result.get('exit_code',0)


if __name__=='__main__':
    raise SystemExit(main())
