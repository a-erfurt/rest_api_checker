"""Explicit opt-in SQL Server tests; every fixture owns a disposable database."""
from contextlib import closing
from hashlib import sha256
import os
from pathlib import Path

import pytest

from rest_api_checker.persistence.admin import create_test_database, destroy_test_database
from rest_api_checker.persistence.database import connect, json_bytes, read_settings
from rest_api_checker.persistence.migrate import apply
from rest_api_checker.persistence.repository import D07, Repository

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT.parent/'bachelor_rest_api_checker'


@pytest.fixture(scope='session')
def settings():
    path = os.environ.get('RAC_SQL_TEST_ENV')
    if not path:
        pytest.skip('Set RAC_SQL_TEST_ENV to external credentials for disposable SQL Server integration tests')
    return read_settings(path)


@pytest.fixture
def db(settings):
    name = create_test_database(settings)
    try:
        yield name
    finally:
        destroy_test_database(settings,name)


@pytest.fixture
def repo(settings,db):
    with closing(connect(settings,db)) as cn:
        apply(cn,expected_current=0)
        yield Repository(cn)


def fixture_case(repo, *, suffix='', body=b'{"fixture":true}', reference=True):
    api = repo.api('fixture-api'+suffix)
    contract_raw = json_bytes({'openapi':'3.1.0','paths':{'/items':{'post':{},'POST':{}},'/Items':{'post':{}}}})
    contract_file = repo.archive('fixture-contract.json',contract_raw)
    contract = repo.contract(api,contract_file,'3.1.0')
    operation = repo.operation(contract,'post','/items')
    family = repo.family(api,'fixture-family'+suffix)
    body_id = repo.archive('fixture-body.bin',body)
    response_id = repo.response(200,'application/json',body_id)
    source = dict(case_id='fixture-case'+suffix,api='fixture-api'+suffix,root_family='fixture-family'+suffix,
        operation={'method':'post','path':'/items'},origin='natural_observation',immediate_parent=None,
        contract_sha256=sha256(contract_raw).hexdigest(),status=200,content_type='application/json',
        body={'sha256':sha256(body).hexdigest()},oracle=dict(c1='PASS',c2='PASS',c3='PASS',
            vector=['PASS']*3,overall='CONSISTENT',selected_response='200',selected_media='application/json',schema_pointer=None,diagnostics=[]))
    source_id = repo.archive('fixture-source.json',json_bytes(source))
    case_id = repo.case(source_namespace='persistence-fixtures',native_case_id=source['case_id'],operation_id=operation,
        response_id=response_id,family_id=family,origin='natural_observation',parent_case_id=None,
        source_file_id=source_id,source_pointer='')
    reference_id = repo.reference(case_id,1,source_id,'/oracle') if reference else None
    return dict(case_id=case_id,reference_id=reference_id,source_id=source_id,source=source,contract=contract,
                operation=operation,family=family,response_id=response_id,body_id=body_id)


@pytest.fixture
def case(repo):
    return fixture_case(repo)


@pytest.fixture
def planned(repo,case):
    dataset = repo.dataset('fabricated','v1','development')
    member = repo.membership(dataset,case['case_id'],case['reference_id'],'fixture-case',1)
    metadata = repo.archive('fabricated-model.json',b'{"fabricated":true}')
    model = repo.model(name='fabricated-model',family='fixture',parameters_b=None,quantization='fixture',
        context_length=32768,digest='sha256:'+'0'*64,architecture='fixture',metadata_file_id=metadata)
    prompt = repo.prompt('fabricated','v1','direct',repo.archive('fabricated-prompt.txt',b'fabricated prompt'))
    config = repo.configuration(think=False,**D07)
    schedule = [dict(dataset_case_id=member,model_id=model,prompt_id=prompt,run_config_id=config,
                     repetition=1,seed=101,run_order=1)]
    setup = dict(dataset_id=dataset,schedule_seed=20260925,schedule=schedule,parser_sha256='1'*64,
        fabricated=True,files=[dict(file_id=case['source_id'],sha256=sha256(repo.file(case['source_id'])).hexdigest())])
    experiment,runs = repo.plan_experiment(name='FABRICATED persistence verification',kind='comparison',
        dataset_id=dataset,schedule_seed=20260925,setup=setup,schedule=schedule)
    return dict(dataset=dataset,member=member,model=model,prompt=prompt,config=config,experiment=experiment,
                run=runs[0],schedule=schedule,setup=setup,case=case)


def outcome(repo, attempt, result='valid', retry=False, response=b'fabricated raw envelope'):
    row = repo._row('run_attempts',attempt)
    prediction = dict(c1='FAIL',c1_reason='fabricated C1',c2='PASS',c2_reason=' fabricated C2 ',
                      c3='NOT_APPLICABLE',c3_reason='fabricated C3') if result=='valid' else None
    return dict(result=result,response=response,prediction=prediction,finished_at='2026-09-26T12:01:00.1234567+05:45',
        diagnostics=dict(parser_sha256='1'*64,run_id=row['run_id'],attempt_id=attempt,
            request_sha256=sha256(repo.file(row['request_file_id'])).hexdigest(),retry_eligible=retry,
            attribution='fabricated isolated transport failure' if retry else 'fabricated outcome'))
