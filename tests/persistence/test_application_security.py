"""Least-privilege login qualification in marked disposable databases only."""
from contextlib import closing
import json
import os
from pathlib import Path

import pyodbc
import pytest

from rest_api_checker.experiment.encoding import digest, encode
from rest_api_checker.experiment.orchestration import execute_attempt
from rest_api_checker.persistence.admin import create_test_database, destroy_test_database
from rest_api_checker.persistence.database import connect, read_settings, utc_now
from rest_api_checker.persistence.inspection import rows
from rest_api_checker.persistence.migrate import apply, verify
from rest_api_checker.persistence.repository import Repository
from .test_experiment import make_stage, FabricatedClient, fabricated

pytestmark=pytest.mark.sqlserver


@pytest.fixture
def application_repo(settings, db):
    path=os.environ.get('RAC_SQL_APPLICATION_ENV')
    if not path:
        pytest.skip('Set RAC_SQL_APPLICATION_ENV to qualify the provisioned application login')
    application=read_settings(path)
    assert application.get('RAC_SQL_USER')=='rac_application_login'
    with closing(connect(settings,db)) as admin:
        apply(admin,expected_current=0)
        admin.execute('CREATE USER [rac_application_user] FOR LOGIN [rac_application_login]')
        admin.execute('ALTER ROLE [rac_application] ADD MEMBER [rac_application_user]')
        admin.commit()
    with closing(connect(application,db)) as cn:
        yield Repository(cn),application
        cn.rollback()


def test_application_login_complete_normal_write_path(application_repo,tmp_path):
    repo,_=application_repo
    assert tuple(repo.cn.execute("SELECT ORIGINAL_LOGIN(),USER_NAME(),IS_SRVROLEMEMBER('sysadmin'),IS_MEMBER('db_owner'),IS_MEMBER('rac_application')").fetchone())==('rac_application_login','rac_application_user',0,0,1)
    assert verify(repo.cn)==2
    stage=make_stage(repo)
    for table in ('datasets','dataset_cases','reference_results','prompts','models','run_configs'):
        assert rows(repo,table)
    for attempt,response in ((1,fabricated(technical=True)),(2,fabricated())):
        client=FabricatedClient(repo,response)
        result=execute_attempt(repo,stage['run'],attempt=attempt,client=client,spool_directory=tmp_path,
            context_proof=stage['proof'],verify_runtime=lambda r,p:True,review_failure=lambda r,p:'isolated')
        assert result==('technical_failure' if attempt==1 else 'valid')
    assert len(rows(repo,'experiment_runs'))==1
    assert len(rows(repo,'run_attempts'))==2
    assert len(rows(repo,'predictions'))==1
    repo.complete_experiment(stage['experiment'],finished_at=utc_now())
    run=repo._row('experiment_runs',stage['run'])
    member=repo._row('dataset_cases',run['dataset_case_id'])
    # Storage permission probe only: no evaluator selection or study report.
    source_id=repo._row('test_cases',member['case_id'])['source_file_id']
    inputs=encode(dict(fabricated=True,experiment_id=stage['experiment'],
        files=[dict(file_id=source_id,sha256=digest(repo.file(source_id)))],
        references=[dict(run_id=stage['run'],reference_id=member['reference_id'])]))
    input_id=repo.archive('FABRICATED permission report input.json',inputs)
    output_id=repo.archive('FABRICATED permission report.json',encode(dict(fabricated=True,input_sha256=digest(inputs))))
    report=repo.report(experiment_id=stage['experiment'],input_file_id=input_id,file_id=output_id,code_version='FABRICATED-permission-probe')
    assert repo.file(repo._row('evaluation_reports',report)['file_id'])==repo.file(output_id)
    with pytest.raises(pyodbc.Error):
        repo.cn.execute('UPDATE dbo.evaluation_reports SET code_version=? WHERE id=?','overwritten',report)
    repo.cn.rollback()


@pytest.mark.parametrize('statement',[
    'CREATE TABLE dbo.rac_forbidden_fixture (id int)',
    'ALTER TABLE dbo.files ADD forbidden_fixture int NULL',
    'DROP TABLE dbo.predictions',
    'CREATE USER rac_forbidden_fixture WITHOUT LOGIN',
    'ALTER ROLE db_owner ADD MEMBER rac_application_user',
    "INSERT dbo.schema_migrations(version,name,sha256) VALUES (3,'forbidden',REPLICATE('0',64))",
    'DELETE FROM dbo.files',
    "UPDATE dbo.models SET architecture='forbidden'",
])
def test_application_login_denied_schema_security_and_evidence_mutation(application_repo,statement):
    repo,_=application_repo
    with pytest.raises(pyodbc.Error):
        repo.cn.execute(statement)
    repo.cn.rollback()


def test_application_login_cannot_apply_new_migration(application_repo,tmp_path):
    from rest_api_checker.persistence.migrate import MIGRATIONS
    repo,_=application_repo
    for source in MIGRATIONS.glob('*.sql'):
        (tmp_path/source.name).write_bytes(source.read_bytes())
    (tmp_path/'003_forbidden.sql').write_text('CREATE TABLE dbo.forbidden_fixture (id int);')
    with pytest.raises(pyodbc.Error):
        apply(repo.cn,expected_current=2,directory=tmp_path)
    assert verify(repo.cn)==2


def test_application_login_denied_database_admin(application_repo,settings):
    _,application=application_repo
    created=None
    try:
        with pytest.raises(pyodbc.Error):
            created=create_test_database(application)
    finally:
        if created is not None:
            destroy_test_database(settings,created)
    other=create_test_database(settings)
    try:
        with closing(connect(application,'master',autocommit=True)) as cn:
            assert cn.execute("SELECT HAS_PERMS_BY_NAME(NULL,NULL,'ALTER ANY LOGIN')").fetchval()==0
            for statement in (f'DROP DATABASE [{other}]',
                'ALTER SERVER ROLE sysadmin ADD MEMBER rac_application_login'):
                with pytest.raises(pyodbc.Error): cn.execute(statement)
        with closing(connect(settings,'master')) as admin:
            assert admin.execute('SELECT DB_ID(?)',other).fetchval() is not None
            admin.rollback()
    finally:
        destroy_test_database(settings,other)


def test_application_login_denied_backup(application_repo):
    import uuid
    repo,_=application_repo
    assert repo.cn.execute("SELECT HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','BACKUP DATABASE')").fetchval()==0
    database=repo.cn.execute('SELECT DB_NAME()').fetchval()
    repo.cn.commit()
    repo.cn.autocommit=True
    try:
        path='/var/opt/mssql/backup/rac_persistence_'+uuid.uuid4().hex+'.bak'
        with pytest.raises(pyodbc.Error) as caught:
            repo.cn.execute(f'BACKUP DATABASE [{database}] TO DISK=? WITH COPY_ONLY,CHECKSUM',path)
        assert 'permission' in str(caught.value).lower()
    finally:
        repo.cn.autocommit=False
