"""Actual disposable SQL Server; provider/runtime/context evidence is FABRICATED."""
from dataclasses import asdict, replace
from contextlib import closing
import json
import os

import pytest

from rest_api_checker.experiment import parser, provider, renderer, request, schedule
from rest_api_checker.experiment.encoding import Blocked, digest, encode
from rest_api_checker.experiment.orchestration import Paused, execute_attempt, reconcile_attempt
from rest_api_checker.persistence import spool
from rest_api_checker.persistence.database import IntegrityViolation, connect, read_settings
from rest_api_checker.persistence.importer import import_development, import_prompts
from rest_api_checker.persistence.repository import D07
from .conftest import ROOT, RESEARCH

pytestmark=pytest.mark.sqlserver
VALID=encode({c:{'verdict':v,'reason':'FABRICATED test answer'} for c,v in zip(('c1','c2','c3'),('FAIL','PASS','PASS'))}).decode()


def fabricated(content=VALID, *, technical=False, status=200):
    raw=b'FABRICATED interrupted transport' if technical else encode(dict(done=True,done_reason='length',
        message=dict(role='assistant',content=content,thinking='FABRICATED separate thinking'),
        prompt_eval_count=12,eval_count=7,total_duration=1000000))
    return provider.Receipt(raw,dict(complete=not technical,error_kind='transport' if technical else None,
        error_message='FABRICATED connection reset' if technical else None,http_status=None if technical else status,
        duration_ms=1,headers=[]),'2026-09-26T12:00:00+00:00','2026-09-26T12:00:01+00:00')


class FabricatedClient:
    def __init__(self,repo,response):
        self.repo,self.response,self.calls=repo,response,[]
        self.spid=repo.cn.execute('SELECT @@SPID').fetchval()
        repo.cn.commit()
    def send(self,req,*,on_start):
        on_start(self.response.started_at)
        # Both repository nesting and actual server transaction state checked.
        assert self.repo._depth==0
        # Querying @@TRANCOUNT on the tested non-autocommit ODBC connection
        # itself starts a transaction. Observe it from a separate connection.
        with closing(connect(read_settings(os.environ['RAC_SQL_TEST_ENV']), 'master', autocommit=True)) as monitor:
            assert monitor.execute('SELECT COUNT(*) FROM sys.dm_tran_session_transactions WHERE session_id=? AND is_user_transaction=1',self.spid).fetchval()==0
        self.calls.append(req)
        return self.response


def make_stage(repo, *, full_schedule=False):
    dev=import_development(repo,ROOT/'artifacts/development_dataset_v1',ROOT/'docs/development_dataset_v1_release.json',RESEARCH)
    imported=import_prompts(repo,RESEARCH)
    prompts=imported['prompt_ids']
    members=dict(zip(schedule.CASES,dev['membership_ids']))
    metadata=repo.archive('FABRICATED-model-metadata.json',b'{"fabricated":true}')
    models={m:repo.model(name=m,family='FABRICATED',parameters_b=None,quantization='Q4_K_M',context_length=32768,
        digest='sha256:'+str(i+1)*64,architecture='FABRICATED',metadata_file_id=metadata) for i,m in enumerate(request.MODELS)}
    configs={m:repo.configuration(think=False if m==request.MODELS[0] else None,**D07) for m in request.MODELS}
    # Construct context proofs from exact evidence BEFORE the setup is frozen.
    # Counts/template identities are marked fabricated and never admit real HTTP.
    manifest=json.loads(repo.file(dev['files']['manifest.json']))
    cases={c['case_id']:c for c in manifest['cases']}
    rendered_cases={}
    for code,c in cases.items():
        contract=manifest['sources'][manifest['contracts'][c['api']]]
        ev=renderer.Evidence(repo.file(dev['files'][contract['path']]),c['operation']['method'],c['operation']['path'],
            c['status'],c['content_type'],repo.file(dev['files'][c['body']['path']]))
        rendered_cases[code]=renderer.render(ev,contract_identity='FABRICATED binding',body_identity='FABRICATED binding')
    model_rows={m:repo._row('models',row_id) for m,row_id in models.items()}
    prompt_bytes={p:repo.file(repo._row('prompts',row_id)['file_id']) for p,row_id in prompts.items()}
    proofs={}
    for slot in schedule.comparison_schedule():
        model=model_rows[slot.model]
        req=request.build_request(rendered_cases[slot.case],prompt_name=slot.prompt,prompt=prompt_bytes[slot.prompt],
            model=slot.model,model_digest=model['digest'],repetition=slot.repetition)
        proofs[str(slot.run_order)]=asdict(request.ContextProof(digest(req.body),model['digest'],'b'*64,'c'*64,10000))
    repo.cn.commit()
    setup=dict(parser_sha256=parser.artifact_hash(),renderer_sha256=renderer.artifact_hash(),
        fabricated=True,gate_b_complete=False,context_proofs=proofs,
        files=[dict(file_id=dev['files']['manifest.json'],sha256=digest(repo.file(dev['files']['manifest.json'])))])
    if full_schedule:
        experiment,runs=schedule.persist_comparison(repo,name='FABRICATED disposable schedule',dataset_id=dev['dataset_id'],
            memberships=members,prompts=prompts,models=models,configs=configs,setup=setup)
    else:
        # Lifecycle tests need one run. The separate materialization test verifies
        # the complete 324-run schedule, without repeating it for every fault.
        slot=schedule.comparison_schedule()[0]
        rows=[dict(dataset_case_id=members[slot.case],prompt_id=prompts[slot.prompt],model_id=models[slot.model],
            run_config_id=configs[slot.model],repetition=slot.repetition,seed=slot.seed,run_order=1)]
        setup.update(dataset_id=dev['dataset_id'],schedule_seed=20260925,schedule=rows)
        experiment,runs=repo.plan_experiment(name='FABRICATED single-slot lifecycle fixture',kind='comparison',
            dataset_id=dev['dataset_id'],schedule_seed=20260925,setup=setup,schedule=rows)
    return dict(run=runs[0],runs=runs,experiment=experiment,proof=request.ContextProof(**proofs['1']))


@pytest.fixture
def stage(repo):
    return make_stage(repo)


def execute(repo,stage,tmp_path,response,attempt=1,review='isolated'):
    client=FabricatedClient(repo,response)
    result=execute_attempt(repo,stage['run'],attempt=attempt,client=client,spool_directory=tmp_path,
        context_proof=stage['proof'],verify_runtime=lambda req,proof:True,review_failure=lambda r,p:review)
    return result,client


def test_schedule_sql_materialization(repo):
    stage=make_stage(repo,full_schedule=True)
    rows=repo.cn.execute('SELECT repetition,seed,run_order,result FROM dbo.experiment_runs ORDER BY run_order').fetchall()
    assert len(rows)==324 and len(stage['runs'])==324
    assert all(r[1]==request.SEEDS[r[0]] and r[3] is None for r in rows)
    assert [r[2] for r in rows]==list(range(1,325))
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.run_attempts').fetchval()==0
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.predictions').fetchval()==0
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.experiment_runs WHERE request_file_id IS NOT NULL').fetchval()==0


@pytest.mark.parametrize('content',['{','',VALID.replace('"c1":','"c1":{},"c1":',1), '```'+VALID+'```'])
def test_db15_db17_parser_failure_never_retries(repo,stage,tmp_path,content):
    result,client=execute(repo,stage,tmp_path,fabricated(content))
    assert result=='parser_failure' and len(client.calls)==1
    with pytest.raises(IntegrityViolation): execute(repo,stage,tmp_path,fabricated(),attempt=2)
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.predictions').fetchval()==0
    raw=repo.cn.execute('SELECT response_file_id FROM dbo.run_attempts').fetchval()
    assert repo.file(raw)==fabricated(content).raw


@pytest.mark.parametrize('second,result',[(fabricated(),'valid'),(fabricated('{'),'parser_failure'),
                                         (fabricated(technical=True),'technical_failure')])
def test_db19_db20_db21_db22_retry(repo,stage,tmp_path,second,result):
    first,c1=execute(repo,stage,tmp_path,fabricated(technical=True))
    assert first=='technical_failure'
    assert repo._row('experiment_runs',stage['run'])['result'] is None
    with pytest.raises(IntegrityViolation,match='request mismatch'):
        repo.reserve(stage['run'],c1.calls[0].body+b' ',attempt=2)
    final,c2=execute(repo,stage,tmp_path,second,attempt=2)
    assert final==result and c1.calls==c2.calls
    assert repo._row('experiment_runs',stage['run'])['result']==result
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.run_attempts').fetchval()==2
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.predictions').fetchval()==(result=='valid')
    if result=='valid':
        assert repo.cn.execute('SELECT a.attempt FROM dbo.predictions p JOIN dbo.run_attempts a ON a.id=p.attempt_id').fetchval()==2
    with pytest.raises(IntegrityViolation): execute(repo,stage,tmp_path,fabricated(),attempt=3)


def test_db25_db43_lost_finalize_ack_reconcile_without_dispatch(repo,stage,tmp_path,monkeypatch):
    original=repo.finalize
    def lost(*a,**k):
        original(*a,**k)
        raise OSError('FABRICATED lost commit acknowledgement')
    monkeypatch.setattr(repo,'finalize',lost)
    client=FabricatedClient(repo,fabricated())
    with pytest.raises(Paused) as caught:
        execute_attempt(repo,stage['run'],attempt=1,client=client,spool_directory=tmp_path,
            context_proof=stage['proof'],verify_runtime=lambda r,p:True)
    assert len(client.calls)==1
    monkeypatch.setattr(repo,'finalize',original)
    assert reconcile_attempt(repo,caught.value.spool_path)=='valid'
    files=repo.cn.execute('SELECT COUNT(*) FROM dbo.files').fetchval()
    assert reconcile_attempt(repo,caught.value.spool_path)=='valid'
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.files').fetchval()==files
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.predictions').fetchval()==1
    with pytest.raises(IntegrityViolation): execute(repo,stage,tmp_path,fabricated())


def test_db25_db55_storage_outage_no_provider_retry(repo,stage,tmp_path,monkeypatch):
    original=repo.finalize
    monkeypatch.setattr(repo,'finalize',lambda *a,**k: (_ for _ in ()).throw(OSError('FABRICATED database outage')))
    with pytest.raises(Paused) as caught: execute(repo,stage,tmp_path,fabricated())
    assert caught.value.receipt.raw==fabricated().raw and caught.value.spool_path.exists()
    assert repo._row('experiment_runs',stage['run'])['result'] is None
    with pytest.raises(IntegrityViolation): execute(repo,stage,tmp_path,fabricated(),attempt=2)
    monkeypatch.setattr(repo,'finalize',original)
    assert reconcile_attempt(repo,caught.value.spool_path)=='valid'


def test_db55_fsync_failure_preserves_receipt_and_unresolved_slot(repo,stage,tmp_path,monkeypatch):
    monkeypatch.setattr(spool.os,'fsync',lambda _: (_ for _ in ()).throw(OSError('FABRICATED fsync outage')))
    with pytest.raises(Paused) as caught: execute(repo,stage,tmp_path,fabricated())
    assert caught.value.receipt.raw==fabricated().raw and caught.value.spool_path is None
    assert repo._row('experiment_runs',stage['run'])['result'] is None
    assert list(tmp_path.glob('.incomplete-*'))
    with pytest.raises(IntegrityViolation): execute(repo,stage,tmp_path,fabricated(),attempt=2)


@pytest.mark.parametrize('response,review',[(replace(fabricated(),raw=b'{}'),'isolated'),
    (fabricated(technical=True),'systematic'),(fabricated(technical=True),'ambiguous')])
def test_db49_ambiguous_or_systematic_pauses(repo,stage,tmp_path,response,review):
    with pytest.raises(Paused) as caught: execute(repo,stage,tmp_path,response,review=review)
    assert caught.value.spool_path.exists()
    assert repo._row('experiment_runs',stage['run'])['result'] is None
    assert repo.cn.execute('SELECT result FROM dbo.run_attempts').fetchval() is None
    with pytest.raises(IntegrityViolation): execute(repo,stage,tmp_path,fabricated(),attempt=2)


def test_db44_late_result_retained_without_replacement(repo,stage,tmp_path):
    execute(repo,stage,tmp_path,fabricated(technical=True))
    first=next(tmp_path.glob('*.json'))
    _,value,_=spool.read(first)
    execute(repo,stage,tmp_path,fabricated('{'),attempt=2)
    late=spool.stage(tmp_path,run_id=value['run_id'],attempt_id=value['attempt_id'],
        request_sha256=value['request_sha256'],setup_sha256=value['setup_sha256'],response=fabricated().raw,
        transport=fabricated().transport,started_at=value['started_at'],received_at=value['received_at'])
    with pytest.raises(Paused): reconcile_attempt(repo,late)
    assert repo._row('experiment_runs',stage['run'])['result']=='parser_failure'
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.predictions').fetchval()==0
    assert repo.attempt_state(value['attempt_id'])['result']=='technical_failure'
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.files WHERE sha256=?',digest(fabricated().raw)).fetchval()==1


def test_gate_b_and_context_failure_never_reserve(repo,stage,tmp_path):
    with pytest.raises(Blocked,match='GATE_B'):
        execute_attempt(repo,stage['run'],attempt=1,client=provider.OllamaClient(),spool_directory=tmp_path,
            context_proof=stage['proof'],verify_runtime=lambda r,p:True)
    with pytest.raises(Blocked,match='OVERFLOW'):
        execute_attempt(repo,stage['run'],attempt=1,client=FabricatedClient(repo,fabricated()),spool_directory=tmp_path,
            context_proof=replace(stage['proof'],input_tokens=32768),verify_runtime=lambda r,p:True)
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.run_attempts').fetchval()==0


def test_db43_lost_reservation_ack_never_sends(repo,stage,tmp_path,monkeypatch):
    original=repo.reserve
    def lost(*a,**k):
        original(*a,**k)
        raise OSError('FABRICATED lost reservation acknowledgement')
    monkeypatch.setattr(repo,'reserve',lost)
    client=FabricatedClient(repo,fabricated())
    with pytest.raises(OSError):
        execute_attempt(repo,stage['run'],attempt=1,client=client,spool_directory=tmp_path,
            context_proof=stage['proof'],verify_runtime=lambda r,p:True)
    assert client.calls==[]
    monkeypatch.setattr(repo,'reserve',original)
    with pytest.raises(IntegrityViolation,match='Slot already reserved'):
        execute(repo,stage,tmp_path,fabricated())


def test_single_orchestrator_claim_and_nested_transaction_rejected(repo,settings,db):
    from rest_api_checker.persistence.database import connect
    from rest_api_checker.persistence.repository import Repository
    with closing(connect(settings,db)) as cn:
        other=Repository(cn)
        with repo.dispatch_owner():
            with pytest.raises(IntegrityViolation,match='Another orchestrator'):
                with other.dispatch_owner(): pytest.fail('Second owner admitted')
        with other.dispatch_owner(): pass
    with repo.transaction():
        with pytest.raises(IntegrityViolation,match='caller transaction'):
            with repo.dispatch_owner(): pytest.fail('Nested dispatch admitted')


def test_changed_retry_runtime_blocks_before_call(repo,stage,tmp_path):
    execute(repo,stage,tmp_path,fabricated(technical=True))
    client=FabricatedClient(repo,fabricated())
    with pytest.raises(Blocked,match='RUNTIME_IDENTITY'):
        execute_attempt(repo,stage['run'],attempt=2,client=client,spool_directory=tmp_path,
            context_proof=stage['proof'],verify_runtime=lambda r,p:False)
    assert client.calls==[]
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.run_attempts').fetchval()==1
