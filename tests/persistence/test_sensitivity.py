"""Disposable SQL experiments; every provider response and acceptance is FABRICATED."""
from dataclasses import asdict
import json
from pathlib import Path

import pytest
from rest_api_checker import evaluation, sensitivity_analysis as sa, sensitivity_evaluation as se
from rest_api_checker import sensitivity_execution as sx, sensitivity_freeze as sf
from rest_api_checker.experiment import batch, request, renderer, parser, orchestration
from rest_api_checker.experiment.encoding import digest,encode
from rest_api_checker.persistence.inspection import rows,status,portable
from .test_experiment import make_stage,fabricated,FabricatedClient
from .conftest import RESEARCH

pytestmark=pytest.mark.sqlserver


class FixtureClient:
    def __init__(self, mode='baseline'):
        self.calls=[];self.mode=mode
    def send(self,req,*,on_start):
        self.calls.append(req)
        if self.mode=='baseline':
            response=fabricated()
            if req.metadata['prompt_name']!='P2':response=fabricated('{}')
        else:
            index=len(self.calls)
            response=fabricated(technical=True) if index in (2,3) else fabricated('```{} ```') if index==1 else fabricated()
        on_start(response.started_at);return response


def fixture_plan(repo,tmp_path,monkeypatch):
    original=repo.plan_experiment
    def baseline_plan(**kw):
        raw=b'{"format":"FABRICATED comparison candidate"}'
        approval=b'{"format":"FABRICATED comparison acceptance"}'
        c=repo.archive('FABRICATED baseline candidate',raw);a=repo.archive('FABRICATED baseline acceptance',approval)
        kw['setup'].update(author_candidate_file_id=c,author_acceptance_file_id=a,
            author_candidate_sha256=digest(raw),author_acceptance_sha256=digest(approval))
        return original(**kw)
    monkeypatch.setattr(repo,'plan_experiment',baseline_plan)
    stage=make_stage(repo,full_schedule=True)
    monkeypatch.setattr(repo,'plan_experiment',original)
    result=batch.run(repo,stage['experiment'],client=FixtureClient(),spool_directory=tmp_path/'baseline',
        verify_runtime=lambda r,p:True,review_failure=lambda r,p:'isolated')
    assert result['exit_code']==0
    report_id,report=evaluation.create_report(repo,stage['experiment'])
    assert report['selected_prompt']=='P2'
    baseline=evaluation.analysis_input(repo,stage['experiment']);repo.cn.commit()
    report_row=repo._row('evaluation_reports',report_id)
    source=[r for r in baseline['runs'] if r['prompt']=='P2']
    slots=json.loads(sf.schedule_bytes())['slots'];inventory=[];proofs={}
    _,_,variant,parent=sf.read_approval(RESEARCH)
    models={r['id']:r for r in baseline['bindings']['models']}
    for slot,run in zip(slots,source):
        content=json.loads(repo.file(run['request_file_id']))['messages'][1]['content'].encode()
        req=sf.variant_request(renderer.Rendered(content,dict(rendered_evidence_sha256=digest(content))),
            parent=parent,variant=variant,model=slot['model'],model_digest=models[run['model_id']]['digest'],
            repetition=slot['repetition'])
        inventory.append(dict(**slot,**{k:run[k] for k in ('dataset_case_id','model_id','run_config_id')},
            baseline_run_id=run['id'],request_sha256=digest(req.body)))
        proofs[str(slot['run_order'])]=asdict(request.ContextProof(digest(req.body),models[run['model_id']]['digest'],
            'b'*64,'c'*64,10000))
    candidate=dict(format='sensitivity-freeze-candidate-v2',status='NOT ACCEPTED',instruction='DO NOT EXECUTE',
        gate_b_complete=False,execution_blockers=['EXACT_CANDIDATE_REVIEW_PENDING'],request_inventory=inventory,
        context_proofs=proofs,dataset=baseline['bindings']['datasets'][0],schedule_seed=20260925,
        parser=dict(version=parser.VERSION,sha256=parser.artifact_hash()),renderer=dict(version=renderer.VERSION,sha256=renderer.artifact_hash()),
        evaluator=dict(version=se.VERSION,sha256=se.artifact_hash()),files=baseline['setup']['files'],
        baseline=dict(experiment_id=stage['experiment'],setup_sha256=baseline['setup_sha256'],
            candidate_sha256=baseline['setup']['author_candidate_sha256'],acceptance_sha256=baseline['setup']['author_acceptance_sha256'],
            report=portable(report_row),report_sha256=digest(repo.file(report_row['file_id']))),
        fixture_notice='FABRICATED acceptance/runtime/provider evidence in disposable SQL only')
    raw=encode(candidate);approval=encode(dict(decision='AUTHOR_ACCEPTED_FOR_P2_SENSITIVITY',candidate_sha256=digest(raw),
        author='FABRICATED TEST',accepted_at='2026-09-26T12:00:00+02:00'))
    with repo.transaction():
        setup=sx.accepted_setup(repo,raw,approval,candidate)
        exp,runs=repo.plan_experiment(name='FABRICATED sensitivity lifecycle',kind='sensitivity',dataset_id=setup['dataset_id'],
            schedule_seed=setup['schedule_seed'],setup=setup,schedule=setup['schedule'])
    return exp,runs,raw,approval,candidate,stage['experiment'],report_row


def test_disposable_sensitivity_lifecycle_analysis_and_immutability(repo,tmp_path,monkeypatch):
    exp,runs,raw,approval,candidate,baseline_id,baseline_report=fixture_plan(repo,tmp_path,monkeypatch)
    baseline_bytes=repo.file(baseline_report['file_id'])
    with pytest.raises(ValueError,match='Incomplete'):sa.create_report(repo,exp)
    sx.require_persisted(repo,exp,raw,approval,candidate)
    client=FixtureClient('sensitivity');stop=batch.StopRequest()
    def notify(event):
        if event['event']=='progress':stop.requested=True
    result=batch.run(repo,exp,client=client,spool_directory=tmp_path/'variant',prepare_request=sx.prepare_request,
        verify_runtime=lambda r,p:True,review_failure=lambda r,p:'isolated',stop=stop,notify=notify)
    assert result['exit_code']==130 and len(client.calls)==1
    assert rows(repo,'experiment_runs',experiment_id=exp)[0]['result']=='parser_failure'
    bad=dict(candidate['context_proofs']['2'],request_sha256='0'*64)
    with pytest.raises(ValueError):
        orchestration.execute_attempt(repo,runs[1],attempt=1,client=client,spool_directory=tmp_path/'variant',
            context_proof=request.ContextProof(**bad),prepare_request=sx.prepare_request,verify_runtime=lambda r,p:True)
    assert len(client.calls)==1 and not rows(repo,'run_attempts',run_id=runs[1])
    result=batch.run(repo,exp,client=client,spool_directory=tmp_path/'variant',prepare_request=sx.prepare_request,
        verify_runtime=lambda r,p:True,review_failure=lambda r,p:'ambiguous')
    assert result['exit_code']==3 and len(client.calls)==2
    with pytest.raises(ValueError):sa.analysis_input(repo,exp)
    held=next((tmp_path/'variant').glob(str(runs[1])+'-*.json'))
    with pytest.raises(orchestration.Paused):
        orchestration.reconcile_attempt(repo,held,review_failure=lambda r,p:'systematic')
    result=batch.run(repo,exp,client=client,spool_directory=tmp_path/'variant',prepare_request=sx.prepare_request,
        verify_runtime=lambda r,p:True,review_failure=lambda r,p:'isolated')
    assert result['exit_code']==3 and len(client.calls)==2  # Reserved hold is never redispatched.
    assert orchestration.reconcile_attempt(repo,held,review_failure=lambda r,p:'isolated')=='technical_failure'
    result=batch.run(repo,exp,client=client,spool_directory=tmp_path/'variant',prepare_request=sx.prepare_request,
        verify_runtime=lambda r,p:True,review_failure=lambda r,p:'isolated')
    assert result['exit_code']==0 and len(client.calls)==109
    assert client.calls[1].body==client.calls[2].body
    assert result['state']['counts']==dict(valid=106,parser_failure=1,technical_failure=1)
    report_id,report=sa.create_report(repo,exp)
    assert report['diagnostic_only'] and 'selected_prompt' not in report
    assert report['variant']['Reliability']==se.ratio(106,108)
    assert repo.file(baseline_report['file_id'])==baseline_bytes
    assert len(rows(repo,'evaluation_reports',experiment_id=baseline_id))==1
    second,again=sa.create_report(repo,exp)
    assert second!=report_id and report==again
    for sql,params in (
        ('UPDATE dbo.experiment_runs SET seed=999 WHERE id=?',(runs[0],)),
        ('UPDATE dbo.experiment_runs SET result=NULL,finished_at=NULL WHERE id=?',(runs[0],)),
        ('UPDATE dbo.run_configs SET top_k=41 WHERE id=?',(candidate['request_inventory'][0]['run_config_id'],)),
    ):
        try:
            with repo.transaction():
                repo.cn.execute(sql,*params)
                with pytest.raises(ValueError):sa.analysis_input(repo,exp)
                raise RuntimeError('rollback FABRICATED mutation')
        except RuntimeError:pass
    assert sa.analysis_input(repo,exp)['evaluator_version']==se.VERSION
