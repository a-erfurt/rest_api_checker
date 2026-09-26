"""Read-only security/source/runtime inspection. No model generation or SQL writes."""
from contextlib import closing
from datetime import datetime
import json
import os
from pathlib import Path
import stat

from fastapi.testclient import TestClient
from rest_api_checker import freeze, runtime_evidence
from rest_api_checker.experiment.encoding import digest
from rest_api_checker.persistence.database import connect, read_settings
from rest_api_checker.persistence.inspection import portable, rows
from rest_api_checker.persistence.migrate import verify
from rest_api_checker.persistence.repository import Repository
from rest_api_checker.web.app import create_app

ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'docs/gate_b_closure_2026-09-26'
APP=Path.home()/'.config/rest-api-checker/application-credentials.env'


def inspect():
    before=json.loads((FOLDER/'before.json').read_bytes())
    changed=[p for p,sha in before['protected'].items() if digest(Path(p).read_bytes())!=sha]
    if changed: raise ValueError('Protected input drift: '+str(changed))
    prior=ROOT/runtime_evidence.DIRECTORY
    runtime=dict(runtime=json.loads((prior/'host.json').read_bytes()),models=json.loads((prior/'identities.json').read_bytes()))
    freeze.verify_live(runtime,ROOT)
    with closing(connect(read_settings(APP),'rest_api_checker')) as cn:
        repo=Repository(cn)
        security=freeze.principal(cn)
        counts={t:len(rows(repo,t)) for t in before['database']['counts']}
        assert all(counts[t]==0 for t in ('experiments','experiment_runs','run_attempts','predictions','evaluation_reports'))
        references=portable(rows(repo,'reference_results'))
        schema=verify(cn)
        cn.rollback()
    os.environ['RAC_WEB_ENV_FILE']=str(APP); os.environ['RAC_WEB_DATABASE']='rest_api_checker'
    with TestClient(create_app()) as client:
        pages={path:client.get(path).status_code for path in ('/','/evaluation','/runs','/data/datasets','/data/cases','/data/references','/data/artifacts?kind=models')}
        assert set(pages.values())=={200}
    return dict(captured_at=datetime.now().astimezone().isoformat(),schema_version=schema,principal=security,
        counts=counts,references=references,protected_files=len(before['protected']),protected_drift=changed,
        runtime_drift=[],runtime_verification='Metadata/version/full shows/tags/host/binary SHA-256 only; no generation',
        credential_mode=oct(stat.S_IMODE(APP.stat().st_mode)),web_http_statuses=pages,
        research_commit=freeze.git(ROOT.parent/'bachelor_rest_api_checker','rev-parse','HEAD'),
        research_working_tree=freeze.git(ROOT.parent/'bachelor_rest_api_checker','status','--porcelain'))

if __name__=='__main__':
    value=inspect()
    (FOLDER/'setup_verified.json').write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:value[k] for k in ('counts','protected_files','protected_drift','runtime_drift','credential_mode','web_http_statuses')}))
