"""Real SQL Server storage with unmistakably fabricated provider outcomes."""
from contextlib import closing
import io
import json
import os
import signal
import shutil

import pytest
import pyodbc

from rest_api_checker import cli, demo, evaluation, terminal
from rest_api_checker.experiment.batch import run, StopRequest
from rest_api_checker.persistence.database import IntegrityViolation, connect
from rest_api_checker.persistence.admin import destroy_test_database
from rest_api_checker.persistence.inspection import rows, run_detail, status
from .conftest import ROOT, RESEARCH
from .test_experiment import make_stage, FabricatedClient, fabricated

pytestmark = pytest.mark.sqlserver


def execute(repo,stage,tmp_path,client,**kwargs):
    return run(repo,stage['experiment'],client=client,spool_directory=tmp_path,
        verify_runtime=lambda r,p:True,review_failure=lambda r,p:'isolated',**kwargs)


def test_full_fabricated_cli_demo_reports_and_reconciliation(repo,tmp_path,settings,db,capsys):
    experiment,runs = demo.plan(repo,ROOT,RESEARCH)
    with pytest.raises(IntegrityViolation,match='Unfinished'):
        evaluation.create_report(repo,experiment)
    assert not rows(repo,'evaluation_reports')
    client = demo.client_for(repo,experiment)
    events = []
    def notify(event):
        client.event(event)
        if event['event']=='progress':
            events.append((event['state']['completed'],event['state']['planned']))
    result = run(repo,experiment,client=client,spool_directory=tmp_path/'spool',
        verify_runtime=lambda r,p:True,review_failure=lambda r,p:'isolated',notify=notify)
    assert result['exit_code']==0 and client.calls==326
    assert result['state']['counts']==dict(valid=322,parser_failure=1,technical_failure=1)
    assert all(total==324 for _,total in events)
    assert [n for n,_ in events[:5]]==[1,1,2,2,3]
    first,report = evaluation.create_report(repo,experiment)
    record = repo._row('evaluation_reports',first)
    input_raw, report_raw = repo.file(record['input_file_id']),repo.file(record['file_id'])
    snapshot = json.loads(input_raw)
    assert len(snapshot['runs'])==324 and len(snapshot['references'])==324
    assert evaluation.evaluate(snapshot)['metrics']==report['metrics']
    assert report['fabricated'] and report['selected_prompt'] in ('P1','P2','P3')
    second, report2 = evaluation.create_report(repo,experiment)
    assert second!=first and report2==report
    assert repo.file(record['input_file_id'])==input_raw and repo.file(record['file_id'])==report_raw
    # Full engine check against independently counted all-PASS fake outputs:
    # DEV vectors contain 11+9+4=24 PASS states over 36 category units;
    # repeated 3 times across 3 models => 216/324 before two failed runs.
    for p in ('P1','P2','P3'):
        failed = [r for r in snapshot['runs'] if r['prompt']==p and r['result']!='valid']
        lost = sum(sum(v=='PASS' for v in r['reference'].values()) for r in failed)
        assert report['metrics'][p]['Score']==evaluation.ratio(216-lost,324)
    # A snapshot is unaffected by later diagnostics; no overwrite API exists.
    detail = run_detail(repo,runs[1])
    assert len(detail['attempts'])==2 and detail['prediction'] is not None
    stream = io.StringIO()
    terminal.inspection(terminal.console(file=stream),detail)
    assert 'FABRICATED fixed answer' in stream.getvalue() and 'provider_envelopes' not in stream.getvalue()
    assert 'raw' in run_detail(repo,runs[1],raw=True)
    # SQL drift checks must reject rather than publish another report.
    mutations = [
        ('UPDATE dbo.experiment_runs SET result=NULL,finished_at=NULL WHERE id=?',runs[0]),
        ('UPDATE dbo.experiment_runs SET seed=999 WHERE id=?',runs[0]),
        ('UPDATE dbo.run_configs SET top_k=41 WHERE id=?',snapshot['runs'][0]['run_config_id']),
        ('UPDATE dbo.models SET architecture=? WHERE id=?',('DRIFT',snapshot['runs'][0]['model_id'])),
        ('DELETE dbo.experiment_runs WHERE id=?',runs[-1]),
    ]
    # Delete has child FKs, so use an independent unfinished experiment for missing/extra below.
    for sql,parameters in mutations[:-1]:
        try:
            with repo.transaction():
                repo.cn.execute(sql,*(parameters if isinstance(parameters,tuple) else (parameters,)))
                with pytest.raises(IntegrityViolation):
                    evaluation.analysis_input(repo,experiment)
                raise RuntimeError('rollback fabricated corruption')
        except RuntimeError:
            pass
    assert repo.file(record['file_id'])==report_raw
    repo.cn.execute("CREATE USER rac_report_fixture WITHOUT LOGIN")
    repo.cn.execute("ALTER ROLE rac_application ADD MEMBER rac_report_fixture")
    repo.cn.commit()
    repo.cn.execute("EXECUTE AS USER='rac_report_fixture'")
    try:
        for sql in ('UPDATE dbo.evaluation_reports SET code_version=\'overwritten\' WHERE id=?',
                    'DELETE dbo.evaluation_reports WHERE id=?'):
            with pytest.raises(pyodbc.Error): repo.cn.execute(sql,first)
            repo.cn.rollback()
    finally:
        repo.cn.execute('REVERT')
        repo.cn.commit()
    # CLI/JSON loads exactly the immutable engine output on a separate connection.
    repo.cn.commit()
    common = ['--env-file',os.environ['RAC_SQL_TEST_ENV'],'--database',db]
    assert cli.main([*common,'evaluate','show',str(first),'--json'])==0
    assert json.loads(capsys.readouterr().out)['report']==report
    assert cli.main([*common,'experiment','show',str(experiment),'--json'])==0
    assert json.loads(capsys.readouterr().out)['completed']==324
    assert cli.main([*common,'inspect','run',str(runs[1]),'--json'])==0
    assert json.loads(capsys.readouterr().out)['prediction']['c1']=='PASS'
    export = tmp_path/'report.json'
    assert cli.main([*common,'evaluate','export',str(first),'--output',str(export),'--json'])==0
    assert export.read_bytes()==report_raw
    capsys.readouterr()
    assert cli.main([*common,'evaluate','export',str(first),'--output',str(export),'--json'])==3
    assert export.read_bytes()==report_raw


def test_missing_extra_duplicate_and_reference_drift(repo):
    stage = make_stage(repo)
    run_id = stage['run']
    original = repo._row('experiment_runs',run_id)
    for mutate in ('missing','extra','duplicate','reference'):
        try:
            with repo.transaction():
                if mutate=='missing':
                    repo.cn.execute('DELETE dbo.experiment_runs WHERE id=?',run_id)
                elif mutate=='extra':
                    repo._insert('experiment_runs',**{**{k:v for k,v in original.items() if k!='id'},'repetition':4,'run_order':2})
                elif mutate=='duplicate':
                    with pytest.raises(Exception):
                        repo._insert('experiment_runs',**{k:v for k,v in original.items() if k!='id'})
                    raise RuntimeError('rollback')
                else:
                    member = repo._row('dataset_cases',original['dataset_case_id'])
                    repo.cn.execute('UPDATE dbo.reference_results SET notes=? WHERE id=?','DRIFT',member['reference_id'])
                    from rest_api_checker.persistence.inspection import bindings
                    setup = json.loads(repo.file(repo._row('experiments',stage['experiment'])['setup_file_id']))
                    assert bindings(repo,original['dataset_id'],setup['schedule'])!=setup['bindings']
                    raise RuntimeError('rollback')
                with pytest.raises(IntegrityViolation): status(repo,stage['experiment'])
                raise RuntimeError('rollback')
        except RuntimeError:
            pass


def test_ctrl_c_finishes_persistence_then_resume_skips_terminal(repo,tmp_path):
    stage = make_stage(repo)
    client = FabricatedClient(repo,fabricated())
    original = client.send
    def interrupted(*args,**kwargs):
        result = original(*args,**kwargs)
        os.kill(os.getpid(),signal.SIGINT)
        return result
    client.send = interrupted
    result = execute(repo,stage,tmp_path,client)
    assert result['exit_code']==130 and result['state']['completed']==1
    assert len(rows(repo,'predictions'))==1
    result = execute(repo,stage,tmp_path,client)
    assert result['exit_code']==0 and len(client.calls)==1


def test_stop_between_attempts_resumes_identical_retry(repo,tmp_path):
    stage = make_stage(repo)
    stop = StopRequest()
    client = FabricatedClient(repo,fabricated(technical=True))
    def notify(event):
        if event['event']=='progress': stop.requested=True
    result = execute(repo,stage,tmp_path,client,notify=notify,stop=stop)
    assert result['exit_code']==130 and result['state']['pending']==1 and result['state']['completed']==0
    second = FabricatedClient(repo,fabricated())
    result = execute(repo,stage,tmp_path,second)
    assert result['exit_code']==0 and client.calls[0].body==second.calls[0].body
    assert len(rows(repo,'run_attempts'))==2


def test_ambiguous_dispatch_blocks_resume_without_provider(repo,tmp_path):
    stage = make_stage(repo)
    repo.reserve(stage['run'],b'FABRICATED reserved request',attempt=1)
    client = FabricatedClient(repo,fabricated())
    for _ in range(2):
        result = execute(repo,stage,tmp_path,client)
        assert result['exit_code']==3 and result['state']['pending']==1
        assert 'NEEDS RECONCILIATION' in result['message']
    assert not client.calls and not rows(repo,'predictions')


def test_demo_marker_and_namespace_required(repo):
    repo.cn.execute("EXEC sys.sp_dropextendedproperty @name=N'rest_api_checker_disposable'")
    repo.cn.commit()
    try:
        with pytest.raises(IntegrityViolation,match='marker'): demo.plan(repo,ROOT,RESEARCH)
        assert not rows(repo,'experiments')
    finally:
        repo.cn.execute("EXEC sys.sp_addextendedproperty @name=N'rest_api_checker_disposable', @value=N'v1'")
        repo.cn.commit()


def test_real_cli_run_blocks_before_dispatch(repo,db,tmp_path,capsys):
    stage = make_stage(repo)
    assert cli.main(['--env-file',os.environ['RAC_SQL_TEST_ENV'],'--database',db,'experiment','run',
                     str(stage['experiment']),'--spool',str(tmp_path),'--json'])==3
    assert 'Gate-B' in json.loads(capsys.readouterr().out)['error']
    assert not rows(repo,'run_attempts')


def test_interrupted_cli_demo_retains_sql_state_and_spool(settings,monkeypatch,capsys):
    def small_plan(repo,root,research):
        s = make_stage(repo)
        return s['experiment'],s['runs']
    original = cli.run
    def stop_before_dispatch(*args,**kwargs):
        return original(*args,**kwargs,stop=StopRequest(requested=True))
    monkeypatch.setattr(demo,'plan',small_plan)
    monkeypatch.setattr(cli,'run',stop_before_dispatch)
    code = cli.main(['--env-file',os.environ['RAC_SQL_TEST_ENV'],'experiment','demo','--json'])
    captured = capsys.readouterr()
    value = json.loads(captured.out)
    try:
        assert code==130 and value['retained'] and value['provider_calls']==0
        assert value['execution']['state']['pending']==1
        assert '--fabricated' in value['resume_command'] and value['database'] in value['resume_command']
        with closing(connect(settings,value['database'])) as cn:
            assert cn.execute('SELECT COUNT(*) FROM dbo.experiment_runs WHERE result IS NULL').fetchval()==1
            assert cn.execute('SELECT COUNT(*) FROM dbo.run_attempts').fetchval()==0
    finally:
        destroy_test_database(settings,value['database'])
        shutil.rmtree(value['spool'])
