"""No provider clients; real final bytes in disposable SQL only."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from rest_api_checker import main_freeze as main, main_execution
from rest_api_checker.experiment import parser, renderer, request
from rest_api_checker.experiment.encoding import digest, encode
from rest_api_checker.persistence.database import IntegrityViolation
from rest_api_checker.persistence.inspection import rows
from rest_api_checker.persistence.repository import D07
from rest_api_checker.sensitivity_freeze import snapshot

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT.parent/'bachelor_rest_api_checker'


def test_schedule_is_fixed_complete_and_has_approved_known_prefix():
    slots = main.order()
    assert len(slots) == len(set(slots)) == 126
    assert slots[:3] == [('FC-HTTS-005','qwen3.6:27b',3), ('FC-HTTS-004','qwen3.6:27b',1), ('FC-EDX-002','qwen3.6:27b',1)]
    assert [sum(s[1] == model for s in slots) for model in request.MODELS] == [42]*3


def test_release_projection_is_lossless_without_new_references():
    release = main.Release(RESEARCH, ROOT)
    projection = release.projection()
    assert len(projection['parents']) == 7 and len(projection['cases']) == 14
    assert all('oracle' not in p for p in projection['parents'])
    for row, source in zip(projection['cases'], release.manifest['cases'], strict=True):
        assert row['original_release_case'] == source
        assert row['reference_rationale'] == json.loads(release.raw(source['oracle_result']))['rationale']


def test_changed_source_rejected_before_projection():
    release = main.Release(RESEARCH, ROOT)
    desc = release.manifest['cases'][0]['response_artifacts']['response_body.bin']
    release.sources['research',desc['path']] += b' '
    with pytest.raises(IntegrityViolation, match='Descriptor mismatch'):
        release.projection()


@pytest.mark.parametrize('record',[{}, {'decision':'AUTHOR_AUTHORIZED_126_MAIN_RUNS','freeze_root':'0'*64}])
def test_no_execution_without_exact_authorization(record):
    raw = encode(dict(format='main-evaluation-freeze-v1',status='FROZEN_READY_FOR_EXECUTION',
                      name=main.NAME,version='1.0',experiment_id=3))
    with pytest.raises(IntegrityViolation, match='authorization required'):
        main_execution.require_acceptance(raw,record)


@pytest.mark.sqlserver
def test_import_plan_idempotence_roundtrip_and_rollback(repo):
    release = main.Release(RESEARCH, ROOT)
    imported = main.import_release(repo,release)
    before = snapshot(repo)
    assert main.import_release(repo,release) == imported
    assert snapshot(repo) == before
    assert len(rows(repo,'test_cases')) == 21 and len(rows(repo,'reference_results')) == 14
    assert len(rows(repo,'dataset_cases')) == 14
    p = (RESEARCH/'03_research_design/final_prompt_freeze_v1/final_prompt_v1.txt').read_bytes()
    prompt = repo.prompt('P2','v1','checklist',repo.archive('P2.txt',p))
    models, configs = {}, {}
    for n,name in enumerate(request.MODELS,1):
        models[name] = repo.model(name=name,family='fixture',parameters_b=None,quantization='Q4_K_M',
            context_length=32768,digest=str(n)*64,architecture='fixture')
        configs[name] = repo.configuration(think=False if n==1 else None,**D07)
    schedule = [dict(dataset_case_id=imported['memberships'][c],model_id=models[m],prompt_id=prompt,
        run_config_id=configs[m],repetition=r,seed=request.SEEDS[r],run_order=n)
        for n,(c,m,r) in enumerate(main.order(),1)]
    setup = dict(format='main-evaluation-setup-v1',version='1.0',dataset_root=main.ROOT,
        dataset_id=imported['dataset_id'],execution_authorized=False,metrics_version='main-evaluation-metrics-v1',
        parser_sha256=parser.artifact_hash(),renderer_sha256=renderer.artifact_hash(),
        schedule=schedule,schedule_seed=main.SEED,schedule_version=main.SCHEDULE,
        model_digests={m:str(n)*64 for n,m in enumerate(request.MODELS,1)},
        files=[dict(file_id=imported['source_file_id'],sha256=imported['projection_sha256'])])
    changed = deepcopy(setup); changed['schedule'][0]['seed'] = 202
    with pytest.raises(IntegrityViolation, match='schedule drift'):
        main.plan_main(repo, imported, changed)
    assert not rows(repo,'experiments')
    experiment, runs = main.plan_main(repo,imported,setup)
    planned = snapshot(repo)
    assert main.plan_main(repo,imported,setup) == (experiment,runs)
    assert snapshot(repo) == planned
    assert main.pristine(repo,experiment)['executed'] == 0
    changed = deepcopy(setup); changed['version'] = '2.0'
    with pytest.raises(IntegrityViolation):
        main.plan_main(repo,imported,changed)
    source = release.manifest['cases'][0]['response_artifacts']['response_body.bin']
    release.sources['research',source['path']] += b' '
    with pytest.raises(IntegrityViolation):
        main.import_release(repo,release)
    assert snapshot(repo) == planned
