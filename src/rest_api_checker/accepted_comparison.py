"""Explicit post-review adapter for the existing comparison orchestrator.

No approval writer, prompt selection, sensitivity or main-evaluation entry point.
An unaccepted candidate cannot connect to SQL or dispatch a provider request.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path

from . import freeze
from .experiment import batch, orchestration
from .experiment.encoding import digest, encode
from .experiment.provider import OllamaClient
from .persistence import spool
from .persistence.database import connect, read_settings, require, timestamp
from .persistence.inspection import rows
from .persistence.repository import Repository


def authorization(candidate_path, acceptance_path):
    raw=Path(candidate_path).read_bytes()
    approval_raw=Path(acceptance_path).read_bytes()
    freeze.require_acceptance(raw,json.loads(approval_raw))
    return raw,approval_raw,json.loads(raw)


def accepted_setup(repo,candidate_raw,approval_raw,candidate):
    """Only called after acceptance and current source/runtime validation."""
    freeze.require_acceptance(candidate_raw,json.loads(approval_raw))
    files=list(candidate['files'])
    ids=[]
    for name,raw in (('author-reviewed-candidate.json',candidate_raw),('author-acceptance.json',approval_raw)):
        identity=repo.archive(name,raw); ids.append(identity)
        files.append(dict(file_id=identity,sha256=digest(raw)))
    return {**candidate,'files':files,'fabricated':False,'gate_b_complete':True,
        'author_candidate_file_id':ids[0],'author_acceptance_file_id':ids[1],
        'author_candidate_sha256':digest(candidate_raw),'author_acceptance_sha256':digest(approval_raw)}


def require_persisted(repo,experiment_id,raw,approval):
    experiment=repo._row('experiments',experiment_id)
    setup=json.loads(repo.file(experiment['setup_file_id']))
    require(setup.get('gate_b_complete') is True and setup.get('fabricated') is False
        and setup.get('author_candidate_sha256')==digest(raw)
        and setup.get('author_acceptance_sha256')==digest(approval)
        and repo.file(setup['author_candidate_file_id'])==raw
        and repo.file(setup['author_acceptance_file_id'])==approval,'Persisted author acceptance mismatch')
    expected=json.loads(raw)
    for key,value in expected.items():
        if key not in ('files','gate_b_complete'):
            require(setup.get(key)==value,'Accepted setup drift: '+key)
    repo.verify_closure(setup['files']); repo.cn.commit()


def technical_review(path,record):
    """Exact-spool technical review only; no final-content repair/reclassification."""
    raw,_,_=spool.read(path)
    require(record.get('spool_sha256')==digest(raw),'Technical review/spool mismatch')
    require(record.get('attribution') in ('isolated','systematic','ambiguous'),'Invalid technical attribution')
    require(type(record.get('reviewer')) is str and bool(record['reviewer'].strip()),'Named technical reviewer required')
    require(type(record.get('reason')) is str and bool(record['reason'].strip()),'Technical justification required')
    require(type(record.get('reviewed_at')) is str,'Technical review time required')
    timestamp(record['reviewed_at'])
    return record['attribution']


def run_accepted(repo,experiment_id,raw,approval,candidate,root,research,spool_directory):
    require_persisted(repo,experiment_id,raw,approval)
    def verify_runtime(request,proof):
        freeze.verify_candidate(candidate,root,research,repo)
        require(proof.request_sha256 in {p['request_sha256'] for p in candidate['context_proofs'].values()},
                'Request outside accepted context inventory')
        proof.verify(request)
        return freeze.verify_live(candidate,root)
    # Technical failures pause after durable retention. An explicit, spool-bound
    # technical review/reconcile permits the existing identical second attempt.
    return batch.run(repo,experiment_id,client=OllamaClient(),spool_directory=spool_directory,
        verify_runtime=verify_runtime,review_failure=lambda receipt,provider:'ambiguous')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','run','reconcile'))
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--acceptance',type=Path,required=True)
    p.add_argument('--env-file',type=Path,default=Path.home()/'.config/rest-api-checker/application-credentials.env')
    p.add_argument('--experiment-id',type=int)
    p.add_argument('--spool',type=Path)
    p.add_argument('--technical-review',type=Path)
    args=p.parse_args(argv)
    # Fail before SQL/network, even if an operator tries the future entry point.
    raw,approval,candidate=authorization(args.candidate,args.acceptance)
    root=Path(__file__).resolve().parents[2]; research=root.parent/'bachelor_rest_api_checker'
    freeze.verify_candidate(candidate,root,research)
    with closing(connect(read_settings(args.env_file),'rest_api_checker')) as cn:
        repo=Repository(cn)
        freeze.verify_candidate(candidate,root,research,repo)
        if args.action=='prepare':
            require(not rows(repo,'experiments'),'An experiment already exists; inspect, never implicitly reschedule')
            freeze.verify_live(candidate,root)
            with repo.transaction():
                setup=accepted_setup(repo,raw,approval,candidate)
                experiment,runs=repo.plan_experiment(name='Author-accepted Development Dataset v1 prompt comparison',
                    kind='comparison',dataset_id=candidate['dataset_id'],schedule_seed=candidate['schedule_seed'],
                    setup=setup,schedule=candidate['schedule'])
            result=dict(experiment_id=experiment,logical_runs=len(runs),dispatched=False)
        else:
            require(args.experiment_id is not None and args.spool is not None,'Experiment ID and spool required')
            require_persisted(repo,args.experiment_id,raw,approval)
            if args.action=='run':
                result=run_accepted(repo,args.experiment_id,raw,approval,candidate,root,research,args.spool)
            else:
                require(args.technical_review is not None,'Explicit spool-bound technical review required')
                review_raw=args.technical_review.read_bytes(); record=json.loads(review_raw)
                attribution=technical_review(args.spool,record)
                _,value,_=spool.read(args.spool)
                require(repo._row('experiment_runs',value['run_id'])['experiment_id']==args.experiment_id,
                        'Spool belongs to another experiment')
                repo.archive('technical-failure-review-'+digest(review_raw)+'.json',review_raw)
                result=dict(result=orchestration.reconcile_attempt(repo,args.spool,
                    review_failure=lambda receipt,provider:attribution),dispatched=False)
    print(json.dumps(result,sort_keys=True))
    return result.get('exit_code',0)

if __name__=='__main__':
    raise SystemExit(main())
