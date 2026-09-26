from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from decimal import Decimal
from hashlib import sha256
import itertools
import json
from pathlib import Path
import shutil

import pyodbc
import pytest

from rest_api_checker.persistence import migrate, spool
from rest_api_checker.persistence.admin import destroy_test_database
from rest_api_checker.persistence.database import IntegrityViolation, connect, json_bytes, lock, transaction
from rest_api_checker.persistence.importer import import_development, import_prompts, load_development, PROMPT_HASHES
from rest_api_checker.persistence.repository import D07, Repository, TABLES
from .conftest import ROOT, RESEARCH, fixture_case, outcome

pytestmark = pytest.mark.sqlserver


def rejected(repo, statement, *params):
    with pytest.raises(pyodbc.Error):
        with repo.transaction():
            repo.cn.execute(statement,*params)


def test_db01_db02_db50_migrations(settings,db,tmp_path):
    with closing(connect(settings,db)) as cn:
        assert migrate.inspect(cn)==[]
        with pytest.raises(IntegrityViolation,match='explicit migration'):
            Repository(cn)
        cn.rollback()
        assert migrate.apply(cn,expected_current=0)==[1,2]
        assert migrate.apply(cn,expected_current=2)==[]
        assert migrate.verify(cn)==2
        assert cn.execute('SELECT COUNT(*) FROM sys.tables WHERE is_ms_shipped=0').fetchval()==19
        fks = cn.execute('SELECT delete_referential_action,update_referential_action,is_disabled,is_not_trusted FROM sys.foreign_keys').fetchall()
        assert len(fks)==34 and all(tuple(r)==(0,0,False,False) for r in fks)
        assert cn.execute("SELECT COUNT(*) FROM sys.indexes WHERE is_primary_key=1 AND type=1").fetchval()==19
        cn.commit()
        with pytest.raises(IntegrityViolation,match='current schema'):
            migrate.apply(cn,expected_current=0)
        for p in migrate.MIGRATIONS.glob('*.sql'):
            shutil.copy(p,tmp_path/p.name)
        with (tmp_path/'001_application_schema.sql').open('a') as f:
            f.write('\n-- changed reviewed bytes\n')
        with pytest.raises(IntegrityViolation,match='checksum'):
            migrate.apply(cn,expected_current=2,directory=tmp_path)
        assert len(migrate.inspect(cn))==2


def test_db50_transaction_failure(settings,db,tmp_path):
    (tmp_path/'001_bad.sql').write_text('CREATE TABLE dbo.partial(id INT);\nGO\nTHROW 51000, \'fabricated migration failure\', 1;')
    with closing(connect(settings,db)) as cn:
        with pytest.raises(pyodbc.Error):
            migrate.apply(cn,expected_current=0,directory=tmp_path)
        assert migrate.inspect(cn)==[]
        assert cn.execute("SELECT OBJECT_ID('dbo.partial')").fetchval() is None
        cn.rollback()
        assert migrate.apply(cn,expected_current=0)==[1,2]


def test_db50_exclusive_lock(settings,db):
    with closing(connect(settings,db)) as owner, closing(connect(settings,db)) as other:
        lock(owner,'rest_api_checker:migrations')
        with pytest.raises(IntegrityViolation,match='lock failed'):
            migrate.apply(other,expected_current=0,lock_timeout_ms=0)
        owner.rollback()
        assert migrate.apply(other,expected_current=0)==[1,2]


def test_db50_concurrent_application(settings,db):
    def apply():
        with closing(connect(settings,db)) as cn:
            try:
                return migrate.apply(cn,expected_current=0)
            except IntegrityViolation as e:
                return str(e)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _:apply(),range(2)))
    assert [1,2] in results and 'Unexpected current schema version' in results


def test_db03_db07_db38_db39_db45_import(repo,monkeypatch):
    # Fail fast if an accidental call ever crosses into scientific construction.
    from rest_api_checker import construction, development_dataset, oracle
    def forbidden(*args,**kwargs):
        pytest.fail('Importer called scientific execution')
    for module,names in [(construction,('construct_parent','construct_control','mutate','observe')),
                         (development_dataset,('materialize',)),(oracle,('evaluate_response',))]:
        for name in names:
            monkeypatch.setattr(module,name,forbidden)
    args = (repo,ROOT/'artifacts/development_dataset_v1',ROOT/'docs/development_dataset_v1_release.json',RESEARCH)
    first = import_development(*args)
    counts = {t:repo.cn.execute(f'SELECT COUNT(*) FROM dbo.{t}').fetchval() for t in TABLES}
    second = import_development(*args)
    assert first==second
    assert counts=={t:repo.cn.execute(f'SELECT COUNT(*) FROM dbo.{t}').fetchval() for t in TABLES}
    assert counts['test_cases']==counts['responses']==counts['reference_results']==counts['dataset_cases']==12
    assert counts['experiment_runs']==counts['models']==counts['experiments']==0
    source = json.loads(repo.file(first['files']['manifest.json']))
    for i,record in enumerate(source['cases']):
        case = repo._row('test_cases',first['case_ids'][record['case_id']])
        assert repo.source(case['source_file_id'],case['source_pointer'])==record
        member = repo._row('dataset_cases',first['membership_ids'][i])
        ref = repo._row('reference_results',member['reference_id'])
        assert repo.source(ref['source_file_id'],ref['source_pointer'])==record['oracle']
        assert [ref[k] for k in ('c1','c2','c3')]==record['oracle']['vector']
        response = repo._row('responses',case['response_id'])
        assert response['status_code']==record['status'] and response['content_type']==record['content_type']
        assert sha256(repo.file(response['body_file_id'])).hexdigest()==record['body']['sha256']
        assert member['position']==i+1 and member['case_code']==record['case_id']
        assert (response['observed_at'] is None)==(record['origin']!='NATURAL')
    assert source['cases'][1]['transformation']['family'] is None
    assert source['cases'][1]['oracle_before']['vector']==['PASS','PASS','FAIL']
    times = [r[0] for r in repo.cn.execute('SELECT observed_at FROM dbo.responses WHERE observed_at IS NOT NULL ORDER BY id')]
    assert times==['2026-09-21T14:44:58.0000000+00:00','2026-09-21T15:21:12.0000000+00:00','2026-09-21T15:21:30.0000000+00:00']
    prompt_import = import_prompts(repo,RESEARCH)
    assert prompt_import==import_prompts(repo,RESEARCH)
    for name,prompt_id in prompt_import['prompt_ids'].items():
        raw = repo.file(repo._row('prompts',prompt_id)['file_id'])
        assert sha256(raw).hexdigest()==PROMPT_HASHES[name]
        assert len(raw)=={'P1':4325,'P2':4996,'P3':5835}[name]
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.experiment_runs').fetchval()==0


def test_db04_db47_changed_and_missing_sources(repo,tmp_path):
    stage = tmp_path/'dev'
    shutil.copytree(ROOT/'artifacts/development_dataset_v1',stage)
    body = stage/'cases/DEV-01/response_body.bin'
    original = body.read_bytes()
    body.write_bytes(original+b' ')
    with pytest.raises(IntegrityViolation,match='hash binding'):
        import_development(repo,stage,ROOT/'docs/development_dataset_v1_release.json',RESEARCH)
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.test_cases').fetchval()==0
    body.unlink()
    with pytest.raises(FileNotFoundError):
        load_development(stage,ROOT/'docs/development_dataset_v1_release.json',RESEARCH)


def test_db05_db06_db37_db54_bytes(repo):
    values = [b'',b'null',b'{broken',b'\xff\xfe\x00\x80',bytes(range(256))*8192]
    for raw in values:
        file_id = repo.archive('original',raw)
        assert file_id==repo.archive('alias',raw)
        assert repo.file(file_id)==raw
        assert repo.cn.execute("SELECT LOWER(CONVERT(varchar(64),HASHBYTES('SHA2_256',content),2)) FROM dbo.files WHERE id=?",file_id).fetchval()==sha256(raw).hexdigest()
    empty = repo.archive('empty',b'')
    ids = [repo.response(200,media,empty) for media in (None,'','application/json')]
    assert len(set(ids))==3
    assert [repo._row('responses',i)['content_type'] for i in ids]==[None,'','application/json']
    with pytest.raises(IntegrityViolation):
        repo.response(200,None,None)
    rejected(repo,'UPDATE dbo.files SET content=? WHERE id=?',b'changed',empty)
    rejected(repo,'DELETE dbo.files WHERE id=?',empty)
    text = 'Grüße 中文 😀 e\u0301 é\r\n  '*4096
    api = repo.api('unicode',text)
    assert repo._row('apis',api)['description']==text


def test_db08_db10_db12_db40_db47_sources(repo,case):
    other = fixture_case(repo,suffix='-other')
    dataset = repo.dataset('dataset','v1','development')
    rejected(repo,'INSERT dbo.dataset_cases(dataset_id,case_id,reference_id,case_code,position) VALUES (?,?,?,?,?)',
             dataset,case['case_id'],other['reference_id'],'bad',1)
    row = repo._row('test_cases',case['case_id'])
    row.pop('id')
    row['family_id'] = other['family']
    with pytest.raises(IntegrityViolation,match='Family/API'):
        repo.case(**row)
    row['family_id'] = case['family']
    row['source_pointer'] = '/oracle'
    with pytest.raises((IntegrityViolation,KeyError)):
        repo.case(**row)
    source = dict(case['source'])
    source['oracle'] = dict(source['oracle'],c3=None)
    bad = repo.archive('incomplete-reference.json',json_bytes(source))
    with pytest.raises(IntegrityViolation):
        repo.reference(case['case_id'],2,bad,'/oracle')
    member = repo.membership(dataset,case['case_id'],None,'fixture-case',1)
    assert repo._row('dataset_cases',member)['reference_id'] is None
    repo.bind_reference(member,case['reference_id'])
    assert repo._row('dataset_cases',member)['reference_id']==case['reference_id']


def test_db04_db37_same_native_identity(repo,case):
    other = fixture_case(repo,suffix='-second')
    assert other['body_id']==case['body_id']
    assert other['case_id']!=case['case_id'] and other['response_id']!=case['response_id']
    row = repo._row('test_cases',case['case_id'])
    row.pop('id')
    row['response_id'] = repo.response(200,'application/json',repo.archive('different',b'new'))
    with pytest.raises(IntegrityViolation,match='response mismatch'):
        repo.case(**row)
    assert repo._row('test_cases',case['case_id'])['response_id']==case['response_id']


def test_db09_db16_db40_schedule(repo,planned):
    run = repo._row('experiment_runs',planned['run'])
    columns = ('experiment_id','dataset_id','dataset_case_id','model_id','prompt_id','run_config_id','repetition','seed','run_order')
    statement = 'INSERT dbo.experiment_runs('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')'
    rejected(repo,statement,*[run[c] for c in columns])
    other = repo.dataset('other','v1','development')
    run['dataset_id'] = other
    rejected(repo,statement,*[run[c] for c in columns])
    member = repo._row('dataset_cases',planned['member'])
    with pytest.raises(IntegrityViolation,match='immutable'):
        repo.bind_reference(planned['member'],member['reference_id'])
    # Whole schedule rolls back when its second member duplicates an order.
    schedule = planned['schedule']+[dict(planned['schedule'][0],repetition=2)]
    setup = dict(planned['setup'],schedule=schedule)
    count = repo.cn.execute('SELECT COUNT(*) FROM dbo.experiments').fetchval()
    with pytest.raises(pyodbc.IntegrityError):
        repo.plan_experiment(name='bad schedule',kind='comparison',dataset_id=planned['dataset'],schedule_seed=20260925,setup=setup,schedule=schedule)
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.experiments').fetchval()==count


def test_db12_db40_null_reference_blocks_schedule(repo,planned):
    draft = repo.dataset('draft','v1','development')
    member = repo.membership(draft,planned['case']['case_id'],None,'draft',1)
    schedule = [dict(planned['schedule'][0],dataset_case_id=member)]
    setup = dict(planned['setup'],dataset_id=draft,schedule=schedule)
    with pytest.raises(IntegrityViolation,match='Incomplete'):
        repo.plan_experiment(name='draft',kind='comparison',dataset_id=draft,schedule_seed=20260925,setup=setup,schedule=schedule)


def test_db13_db52_tokens_and_nulls(repo,case):
    for token in ('pass','Pass','FAIL ','NOT_APPLICABLE ',' PASS','PASS\t','','UNKNOWN',None):
        rejected(repo,'INSERT dbo.reference_results(case_id,version,c1,c2,c3,source_file_id,source_pointer) VALUES (?,2,?,?,?, ?,?)',
                 case['case_id'],token,'PASS','PASS',case['source_id'],'/oracle')
    rejected(repo,'INSERT dbo.reference_results(case_id,version,c1,c2,c3,source_file_id,source_pointer) VALUES (?,2,?,?,?,?,?)',
             case['case_id'],'FAIL','PASS','PASS',case['source_id'],'/oracle')
    for name in ('bad ',''):
        rejected(repo,'INSERT dbo.apis(name) VALUES (?)',name)
    for purpose in ('Development','development ',''):
        rejected(repo,'INSERT dbo.datasets(name,version,purpose) VALUES (?,?,?)','bad','v1',purpose)


def test_db14_db23_db52_all_legal_prediction_vectors(repo,planned):
    # Direct SQL tests deliberately bypass lifecycle APIs to isolate SQL responsibility.
    for n,vector in enumerate(itertools.product(('PASS','FAIL','NOT_APPLICABLE'),repeat=3),1):
        with repo.transaction():
            run = repo._insert('experiment_runs',experiment_id=planned['experiment'],dataset_id=planned['dataset'],
                **dict(planned['schedule'][0],repetition=n+1,run_order=n+1))
        attempt = repo.reserve(run,b'fabricated',attempt=1)
        with repo.transaction():
            repo.cn.execute('INSERT dbo.predictions(run_id,attempt_id,c1,c1_reason,c2,c2_reason,c3,c3_reason) VALUES (?,?,?,?,?,?,?,?)',
                            run,attempt,vector[0],'x',vector[1],'x',vector[2],'x')
    attempt = repo.reserve(planned['run'],b'fabricated',attempt=1)
    rejected(repo,'INSERT dbo.predictions(run_id,attempt_id,c1,c1_reason,c2,c2_reason,c3,c3_reason) VALUES (?,?,?,?,?,?,?,?)',
             run,attempt,'PASS','x','PASS','x','PASS','x')
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.predictions').fetchval()==27


@pytest.mark.parametrize('second_result',['valid','parser_failure','technical_failure'])
def test_db17_db18_db19_db20_db21_db22_retry(repo,planned,second_result):
    first = repo.reserve(planned['run'],b'fabricated-request',attempt=1)
    repo.finalize(first,**outcome(repo,first,'technical_failure',retry=True,response=None))
    assert repo._row('experiment_runs',planned['run'])['result'] is None
    with pytest.raises(IntegrityViolation,match='request mismatch'):
        repo.reserve(planned['run'],b'changed-request',attempt=2)
    second = repo.reserve(planned['run'],b'fabricated-request',attempt=2)
    repo.finalize(second,**outcome(repo,second,second_result))
    assert repo._row('experiment_runs',planned['run'])['result']==second_result
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.predictions').fetchval()==(1 if second_result=='valid' else 0)
    with pytest.raises(IntegrityViolation):
        repo.reserve(planned['run'],b'fabricated-request',attempt=3)
    rejected(repo,'INSERT dbo.run_attempts(run_id,attempt,request_file_id,prepared_at) VALUES (?,3,?,SYSDATETIMEOFFSET())',
             planned['run'],repo._row('run_attempts',first)['request_file_id'])


@pytest.mark.parametrize('result,retry',[('parser_failure',False),('valid',False),('technical_failure',False)])
def test_db17_retry_not_entitled(repo,planned,result,retry):
    first = repo.reserve(planned['run'],b'fixture',attempt=1)
    repo.finalize(first,**outcome(repo,first,result,retry=retry))
    with pytest.raises(IntegrityViolation):
        repo.reserve(planned['run'],b'fixture',attempt=2)


def test_db24_atomic_finalize(repo,planned,monkeypatch):
    attempt = repo.reserve(planned['run'],b'fixture',attempt=1)
    original = repo._insert
    def fail_prediction(table,**values):
        if table=='predictions':
            raise RuntimeError('fabricated insertion failure')
        return original(table,**values)
    monkeypatch.setattr(repo,'_insert',fail_prediction)
    count = repo.cn.execute('SELECT COUNT(*) FROM dbo.files').fetchval()
    with pytest.raises(RuntimeError):
        repo.finalize(attempt,**outcome(repo,attempt))
    assert repo._row('run_attempts',attempt)['result'] is None
    assert repo._row('experiment_runs',planned['run'])['result'] is None
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.predictions').fetchval()==0
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.files').fetchval()==count


def test_db43_idempotent_finalize_and_reservation(repo,planned):
    attempt = repo.reserve(planned['run'],b'fixture',attempt=1)
    with pytest.raises(IntegrityViolation,match='reconcile'):
        repo.reserve(planned['run'],b'fixture',attempt=1)
    payload = outcome(repo,attempt)
    assert repo.finalize(attempt,**payload)
    assert not repo.finalize(attempt,**payload)
    with pytest.raises(IntegrityViolation,match='Conflicting'):
        repo.finalize(attempt,**dict(payload,response=b'late conflicting bytes'))
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.predictions').fetchval()==1


def test_db34_bounds_and_identity(repo,case):
    assert repo.operation(case['contract'],'post','/items')!=repo.operation(case['contract'],'post','/Items')
    assert repo.operation(case['contract'],'POST','/items')!=case['operation']
    api = repo.api('😀'*64)
    assert repo._row('apis',api)['name']=='😀'*64
    for value in ('😀'*65,'x'*129):
        with pytest.raises(IntegrityViolation,match='bound'):
            repo.api(value)
    with pytest.raises(IntegrityViolation):
        repo.api('name ')
    path = '/'+'x'*511
    raw = json_bytes({'openapi':'3.1.0','paths':{path:{'post':{}}}})
    contract = repo.contract(api,repo.archive('max-path.json',raw),'3.1.0')
    assert repo._row('api_operations',repo.operation(contract,'post',path))['path_template']==path
    with pytest.raises(IntegrityViolation):
        repo.response(2**31,None,case['body_id'])


def test_db45_db46_config_time(repo,planned):
    for think in (False,None):
        config = repo.configuration(think=think,**D07)
        row = repo._row('run_configs',config)
        assert row['think'] is think
        assert all(row[k]==v for k,v in D07.items())
        repo.require_d07(config,'qwen3.6:27b' if think is False else 'gemma3:27b')
    with pytest.raises(IntegrityViolation,match='scale'):
        repo.configuration(think=False,**dict(D07,temperature=Decimal('0.2001')))
    with pytest.raises(IntegrityViolation,match='BIT'):
        repo.configuration(think=0,**D07)
    attempt = repo.reserve(planned['run'],b'fixture',attempt=1)
    assert repo._row('run_attempts',attempt)['started_at'] is None
    observed = '2026-09-26T12:00:00.1234567-00:30'
    repo.observe_start(attempt,observed)
    assert repo._row('run_attempts',attempt)['started_at']==observed
    with pytest.raises(IntegrityViolation):
        repo.response(200,None,planned['case']['body_id'],'2026-09-22')


def test_db32_db26_append_reference_report(repo,planned):
    attempt = repo.reserve(planned['run'],b'fixture',attempt=1)
    with pytest.raises(IntegrityViolation,match='Incomplete'):
        repo.complete_experiment(planned['experiment'],finished_at='2026-09-26T12:02:00Z')
    repo.finalize(attempt,**outcome(repo,attempt))
    repo.complete_experiment(planned['experiment'],finished_at='2026-09-26T12:02:00Z')
    source = dict(planned['case']['source'])
    source['revision_note'] = 'fabricated correction authority'
    source_id = repo.archive('reference-revision.json',json_bytes(source))
    revision = repo.reference(planned['case']['case_id'],2,source_id,'/oracle')
    old_reference = repo._row('dataset_cases',planned['member'])['reference_id']
    reports = []
    for reference in (old_reference,revision):
        inputs = dict(experiment_id=planned['experiment'],references=[dict(run_id=planned['run'],reference_id=reference)],
                      files=[dict(file_id=source_id,sha256=sha256(repo.file(source_id)).hexdigest())])
        input_id = repo.archive('fabricated-report-input.json',json_bytes(inputs))
        file_id = repo.archive('fabricated-report.json',json_bytes(dict(input_sha256=sha256(repo.file(input_id)).hexdigest(),fabricated=True)))
        reports.append(repo.report(experiment_id=planned['experiment'],input_file_id=input_id,file_id=file_id,code_version='fixture-code'))
    assert reports[0]!=reports[1]
    assert repo._row('dataset_cases',planned['member'])['reference_id']==old_reference
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.experiment_runs').fetchval()==1
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.evaluation_reports').fetchval()==2


def test_db44_db55_spool(repo,planned,tmp_path):
    attempt = repo.reserve(planned['run'],b'fixture',attempt=1)
    run = repo._row('experiment_runs',planned['run'])
    experiment = repo._row('experiments',planned['experiment'])
    args = dict(run_id=planned['run'],attempt_id=attempt,request_sha256=sha256(b'fixture').hexdigest(),
                setup_sha256=sha256(repo.file(experiment['setup_file_id'])).hexdigest(),response=b'\xff\x00{invalid',transport={'fabricated':True})
    path = spool.stage(tmp_path,**args)
    assert spool.stage(tmp_path,**args)==path
    assert spool.read(path)[2]==args['response']
    assert spool.reconcile(repo,path)
    assert not spool.reconcile(repo,path)
    assert repo._row('run_attempts',attempt)['result'] is None
    payload = outcome(repo,attempt)
    payload.pop('response')
    payload['diagnostics']['spool_sha256'] = sha256(path.read_bytes()).hexdigest()
    assert spool.reconcile(repo,path,outcome=payload)
    assert not spool.reconcile(repo,path,outcome=payload)
    assert path.exists()
    terminal = repo._row('run_attempts',attempt)
    late = spool.stage(tmp_path,**dict(args,response=b'late favorable answer'))
    assert spool.reconcile(repo,late)
    assert repo._row('run_attempts',attempt)['response_file_id']==terminal['response_file_id']
    assert repo._row('run_attempts',attempt)['result']=='valid'
    with pytest.raises(IntegrityViolation,match='compare-and-swap'):
        repo.append_diagnostics(attempt,expected_file_id=terminal['diagnostics_file_id'],evidence={'files':[]})
    damaged = json.loads(path.read_bytes())
    damaged['payload']['run_id'] += 1
    path.write_bytes(json_bytes(damaged))
    with pytest.raises(IntegrityViolation,match='checksum'):
        spool.reconcile(repo,path)


def test_application_permissions(repo):
    repo.cn.execute("CREATE USER rac_fixture WITHOUT LOGIN; ALTER ROLE rac_application ADD MEMBER rac_fixture;")
    repo.cn.commit()
    repo.cn.execute("EXECUTE AS USER='rac_fixture'")
    try:
        assert repo.api('permitted')
        rejected(repo,"UPDATE dbo.apis SET name='changed'")
        rejected(repo,'DELETE dbo.apis')
        rejected(repo,'CREATE TABLE dbo.forbidden(id INT)')
        rejected(repo,'DELETE dbo.schema_migrations')
    finally:
        repo.cn.execute('REVERT')
        repo.cn.commit()


def test_safe_drop_scope(settings):
    with pytest.raises(IntegrityViolation):
        destroy_test_database(settings,'rest_api_checker')
    with pytest.raises(IntegrityViolation):
        destroy_test_database(settings,'rac_env_probe_20260926')


def test_db13_db52_prediction_tokens_at_storage_boundary(repo,planned):
    attempt = repo.reserve(planned['run'],b'fixture',attempt=1)
    for token in ('PASS ','pass','NOT_APPLICABLE ','NOT_APPLICABLE  ',None):
        rejected(repo,'INSERT dbo.predictions(run_id,attempt_id,c1,c1_reason,c2,c2_reason,c3,c3_reason) VALUES (?,?,?,?,?,?,?,?)',
                 planned['run'],attempt,token,'x','PASS','x','PASS','x')


def test_db52_completion_and_numeric_constraints(repo,planned):
    attempt = repo.reserve(planned['run'],b'fixture',attempt=1)
    for sql in (
        "UPDATE dbo.run_attempts SET result='valid' WHERE id=?",
        'UPDATE dbo.run_attempts SET finished_at=SYSDATETIMEOFFSET() WHERE id=?',
        "UPDATE dbo.run_attempts SET result='valid',finished_at=SYSDATETIMEOFFSET() WHERE id=?",
        'UPDATE dbo.run_attempts SET prompt_tokens=-1 WHERE id=?',
        'UPDATE dbo.run_attempts SET output_tokens=-1 WHERE id=?',
        'UPDATE dbo.run_attempts SET duration_ms=-1 WHERE id=?',
        "UPDATE dbo.run_attempts SET result='Valid',finished_at=SYSDATETIMEOFFSET(),diagnostics_file_id=request_file_id WHERE id=?",
        "UPDATE dbo.run_attempts SET result='technical_failure ',finished_at=SYSDATETIMEOFFSET(),diagnostics_file_id=request_file_id WHERE id=?",
    ):
        rejected(repo,sql,attempt)
    rejected(repo,"UPDATE dbo.experiment_runs SET result='valid' WHERE id=?",planned['run'])
    rejected(repo,'UPDATE dbo.experiment_runs SET finished_at=SYSDATETIMEOFFSET() WHERE id=?',planned['run'])
    for column,value in [('temperature',-1),('top_p',2),('min_p',-1),('top_k',-1),('repeat_penalty',0),
                         ('repeat_last_n',-1),('draft_num_predict',-1),('num_ctx',0),('num_predict',0),('timeout_seconds',0)]:
        rejected(repo,f'UPDATE dbo.run_configs SET {column}=? WHERE id=?',value,planned['config'])
    other_file = repo.archive('other-request',b'other request')
    rejected(repo,'INSERT dbo.run_attempts(run_id,attempt,request_file_id,prepared_at) VALUES (?,2,?,SYSDATETIMEOFFSET())',
             planned['run'],other_file)


def test_db43_competing_reservations_and_finalizations(repo,planned,settings,db):
    def reserve():
        with closing(connect(settings,db)) as cn:
            service = Repository(cn)
            try:
                return service.reserve(planned['run'],b'fixture',attempt=1)
            except IntegrityViolation:
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _:reserve(),range(2)))
    assert sum(i is not None for i in ids)==1
    attempt = next(i for i in ids if i is not None)
    payload = outcome(repo,attempt)
    repo.cn.commit()
    def finalize():
        with closing(connect(settings,db)) as cn:
            return Repository(cn).finalize(attempt,**payload)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _:finalize(),range(2)))
    assert sorted(results)==[False,True]
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.predictions WHERE run_id=?',planned['run']).fetchval()==1


def test_db55_fsync_failure_leaves_unresolved(repo,planned,tmp_path,monkeypatch):
    attempt = repo.reserve(planned['run'],b'fixture',attempt=1)
    setup = repo._row('experiments',planned['experiment'])['setup_file_id']
    def fail(_):
        raise OSError('fabricated fsync failure')
    monkeypatch.setattr(spool.os,'fsync',fail)
    with pytest.raises(OSError,match='fsync'):
        spool.stage(tmp_path,run_id=planned['run'],attempt_id=attempt,request_sha256=sha256(b'fixture').hexdigest(),
            setup_sha256=sha256(repo.file(setup)).hexdigest(),response=b'retained fabricated bytes',transport={})
    assert list(tmp_path.glob('.incomplete-*'))
    assert not list(tmp_path.glob('*.json'))
    assert repo._row('run_attempts',attempt)['result'] is None
    assert repo._row('experiment_runs',planned['run'])['result'] is None
    with pytest.raises(IntegrityViolation):
        repo.reserve(planned['run'],b'fixture',attempt=2)


def test_db54_unicode_reasons_and_export(repo,planned,tmp_path):
    from rest_api_checker.persistence.archive import export_files
    attempt = repo.reserve(planned['run'],b'fixture',attempt=1)
    payload = outcome(repo,attempt,response=bytes(range(256))*8192)
    reason = '文字 😀 Grüße e\u0301\r\n  '*8192
    payload['prediction']['c1_reason'] = reason
    repo.finalize(attempt,**payload)
    assert repo.cn.execute('SELECT c1_reason FROM dbo.predictions WHERE attempt_id=?',attempt).fetchval()==reason
    file_id = repo._row('run_attempts',attempt)['response_file_id']
    digest = sha256(payload['response']).hexdigest()
    manifest = export_files(repo,[dict(file_id=file_id,sha256=digest,path='untrusted/../../display-only')],tmp_path/'export')
    assert (manifest.parent/(digest+'.bin')).read_bytes()==payload['response']
    with pytest.raises(FileExistsError):
        export_files(repo,[dict(file_id=file_id,sha256=digest)],tmp_path/'export')


def test_db33_db54_application_backup_restore(repo,planned,settings,db):
    """Opt-in Docker copy only for the already-qualified project/container."""
    import os
    import subprocess
    import uuid
    from rest_api_checker.persistence.admin import backup_database, restore_test_database
    directory = os.environ.get('RAC_SQL_TEST_BACKUP_DIR')
    if directory is None:
        pytest.skip('Set RAC_SQL_TEST_BACKUP_DIR to retain a backup outside the container')
    container = 'rac-sql-env-20260926-sqlserver-1'
    def docker(*args):
        return subprocess.check_output(['docker',*args],text=True).strip()
    image = docker('inspect','--format','{{.Config.Image}}',container)
    assert image=='mcr.microsoft.com/mssql/server@sha256:4402d880dd4c34bfa7d8705e56a86cd6c88da80a1f6bbbe741f999e76264a090'
    attempt = repo.reserve(planned['run'],b'fixture',attempt=1)
    payload = outcome(repo,attempt,response=bytes(range(256))*8192)
    payload['prediction']['c1_reason'] = 'Unicode 😀 中文\r\n '*4096
    repo.finalize(attempt,**payload)
    import_development(repo,ROOT/'artifacts/development_dataset_v1',ROOT/'docs/development_dataset_v1_release.json',RESEARCH)
    import_prompts(repo,RESEARCH)
    def snapshot(cn):
        return {table:[tuple(r) for r in cn.execute(f'SELECT * FROM dbo.{table} ORDER BY '+('version' if table=='schema_migrations' else 'id'))]
                for table in [*TABLES,'schema_migrations']}
    before = snapshot(repo.cn)
    repo.cn.commit()
    token = uuid.uuid4().hex
    server = f'/var/opt/mssql/backup/rac_persistence_{token}.bak'
    docker('exec',container,'mkdir','-p','/var/opt/mssql/backup')
    backup_database(settings,db,server)
    host = Path(directory)
    host.mkdir(mode=0o700,parents=True,exist_ok=True)
    backup = host/f'rac_persistence_{token}.bak'
    assert not backup.exists()
    docker('cp',f'{container}:{server}',str(backup))
    backup.chmod(0o600)
    digest = sha256(backup.read_bytes()).hexdigest()
    assert docker('exec',container,'sha256sum',server).split()[0]==digest
    copied = f'/var/opt/mssql/backup/rac_persistence_{uuid.uuid4().hex}.bak'
    docker('cp',str(backup),f'{container}:{copied}')
    docker('exec','--user','root',container,'chown','mssql',copied)
    assert docker('exec',container,'sha256sum',copied).split()[0]==digest
    restored = restore_test_database(settings,copied)
    try:
        with closing(connect(settings,restored)) as cn:
            assert migrate.verify(cn)==2
            assert snapshot(cn)==before
        assert snapshot(repo.cn)==before
        assert repo.cn.execute('SELECT COUNT(*) FROM dbo.experiment_runs').fetchval()==1  # Fabricated fixture only.
        evidence = dict(result='PASS',original_database=db,restored_database=restored,host_backup=str(backup),
            backup_sha256=digest,size_bytes=backup.stat().st_size,server_path=server,host_copy_server_path=copied,
            tables_equal=19,foreign_keys=34,dev_cases=12,approved_prompts=3,fabricated_runs=1,study_runs=0,
            migrations=[list(r) for r in migrate.inspect(repo.cn)])
        (host/f'{token}-verification.json').write_bytes(json_bytes(evidence))
    finally:
        destroy_test_database(settings,restored)


def test_reference_revision_cannot_change_case_inputs(repo,case):
    changed = dict(case['source'],status=500)
    file_id = repo.archive('changed-case-reference.json',json_bytes(changed))
    with pytest.raises(IntegrityViolation,match='changes case inputs'):
        repo.reference(case['case_id'],2,file_id,'/oracle')
    assert repo.cn.execute('SELECT COUNT(*) FROM dbo.reference_results WHERE case_id=?',case['case_id']).fetchval()==1
