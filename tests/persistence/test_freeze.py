"""Read-only application-source closure and non-executable acceptance guards."""
from contextlib import closing
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from rest_api_checker import freeze
from rest_api_checker.experiment.encoding import digest, encode
from rest_api_checker.persistence.database import connect, read_settings
from rest_api_checker.persistence.repository import Repository

ROOT=Path(__file__).resolve().parents[2]
RESEARCH=ROOT.parent/'bachelor_rest_api_checker'
pytestmark=pytest.mark.sqlserver


@pytest.fixture
def candidate(monkeypatch):
    path=os.environ.get('RAC_SQL_APPLICATION_ENV')
    if not path: pytest.skip('Set RAC_SQL_APPLICATION_ENV for read-only application freeze checks')
    original=freeze.git
    monkeypatch.setattr(freeze,'git',lambda r,*a: '' if a[0]=='status' and r==ROOT else original(r,*a))
    # Construction is tested before the final commit/test receipt exists. Only
    # those prerequisites are simulated; SQL rows, request bytes and token counts
    # remain actual. The final candidate uses all unmodified production checks.
    monkeypatch.setattr(freeze.gate_b_closure,'inspect',lambda *a:{'Failure attribution':{'status':'PASS'}})
    monkeypatch.setattr(freeze,'source_hashes',lambda *a:{'implementation:pyproject.toml':digest((ROOT/'pyproject.toml').read_bytes())})
    with closing(connect(read_settings(path),'rest_api_checker')) as cn:
        repo=Repository(cn)
        result=freeze.build(repo,ROOT,RESEARCH,json.loads((ROOT/'docs/gate_b_closure_2026-09-26/registrations.json').read_bytes()))
        yield result,repo
        cn.rollback()


def test_read_only_complete_freeze(candidate):
    value,repo=candidate
    assert freeze.verify_candidate(json.loads(encode(value)),ROOT,RESEARCH,repo)
    assert len(value['schedule'])==len(value['context_proofs'])==324
    assert len(value['references'])==12 and len(value['bindings']['run_configs'])==3
    assert value['status']=='NOT AUTHOR-ACCEPTED' and value['instruction']=='DO NOT EXECUTE'
    assert value['database']['principal']['login']=='rac_application_login'
    for table in ('experiments','experiment_runs','run_attempts','predictions','evaluation_reports'):
        assert repo.cn.execute(f'SELECT COUNT(*) FROM dbo.{table}').fetchval()==0


@pytest.mark.parametrize('change',[
    lambda c:c.update(gate_b_complete=True),
    lambda c:c.update(implementation_commit='0'*40),
    lambda c:c['sources'].clear(),
    lambda c:c['schedule'].pop(),
    lambda c:c['schedule'][0].update(seed=999),
    lambda c:c['context_proofs']['1'].update(input_tokens=1),
    lambda c:c['configuration']['thinking'].update({'gemma3:27b':False}),
    lambda c:c.update(selected_prompt='P1'),
    lambda c:c['bindings']['reference_results'][0].update(c1='FAIL'),
    lambda c:c['database']['principal'].update(login='sa'),
])
def test_freeze_rejects_drift(candidate,change):
    value,repo=candidate
    value=deepcopy(value); change(value)
    with pytest.raises((ValueError,KeyError)): freeze.verify_candidate(value,ROOT,RESEARCH,repo)
