"""Register already-qualified identities/configurations, never an experiment/schedule."""
from contextlib import closing
from decimal import Decimal
import json
from pathlib import Path

from rest_api_checker import runtime_evidence
from rest_api_checker.experiment.request import MODELS
from rest_api_checker.persistence.database import connect, read_settings
from rest_api_checker.persistence.inspection import portable, rows
from rest_api_checker.persistence.repository import D07, Repository

ROOT=Path(__file__).resolve().parents[2]
RESEARCH=ROOT.parent/'bachelor_rest_api_checker'
EVIDENCE=ROOT/runtime_evidence.DIRECTORY
OUTPUT=ROOT/'docs/gate_b_closure_2026-09-26'


def register():
    verified=runtime_evidence.inspect(ROOT,RESEARCH)
    assert all(verified[name]['status']=='PASS' for name in ('Full model identities','Template and effective options','Context fit'))
    settings=read_settings(Path.home()/'.config/rest-api-checker/application-credentials.env')
    identities=json.loads((EVIDENCE/'identities.json').read_bytes())
    with closing(connect(settings,'rest_api_checker')) as cn:
        repo=Repository(cn)
        assert not rows(repo,'experiments') and not rows(repo,'models') and not rows(repo,'run_configs')
        maps={'models':{},'configs':{}}
        with repo.transaction():
            for identity in identities:
                show=json.loads((EVIDENCE/identity['show']).read_bytes())
                name=identity['name']; arch=show['model_info']['general.architecture']
                # Preserve the runtime's reported B value; exact integer count
                # remains in the unmodified /api/show metadata artifact.
                reported=show['details']['parameter_size']; assert reported.endswith('B')
                metadata_id=repo.archive(identity['show'],(EVIDENCE/identity['show']).read_bytes())
                maps['models'][name]=repo.model(name=name,family=show['details']['family'],
                    parameters_b=Decimal(reported[:-1]),quantization=show['details']['quantization_level'],
                    context_length=show['model_info'][arch+'.context_length'],digest=identity['digest'],
                    architecture=arch,metadata_file_id=metadata_id)
                maps['configs'][name]=repo.configuration(think=False if name==MODELS[0] else None,**D07)
        result={**maps,'model_rows':portable(rows(repo,'models')),'config_rows':portable(rows(repo,'run_configs')),
                'experiments':len(rows(repo,'experiments')),'runs':len(rows(repo,'experiment_runs')),'predictions':len(rows(repo,'predictions'))}
        cn.rollback()
    (OUTPUT/'registrations.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('Registered 3 qualified models and 3 explicit D07 configurations; no experiment, run or prediction.')

if __name__=='__main__': register()
