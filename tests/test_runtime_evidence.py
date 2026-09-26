"""Recorded evidence validation and fail-closed regression tests; no live runtime."""
import json
from pathlib import Path
import shutil

import pytest

from rest_api_checker import preflight, runtime_evidence, gate_b_closure, freeze
from rest_api_checker.experiment.encoding import digest

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT.parent/'bachelor_rest_api_checker'
HISTORICAL_COMMIT = json.loads((ROOT/freeze.CANDIDATE).read_bytes())['implementation_commit']


@pytest.fixture
def capture(tmp_path):
    root, research = tmp_path/'implementation', tmp_path/'research'
    folder=root/runtime_evidence.DIRECTORY
    shutil.copytree(ROOT/runtime_evidence.DIRECTORY,folder)
    bundle=json.loads((folder/'bundle.json').read_bytes())
    for name in bundle['sources']:
        base,relative=name.split(':',1)
        source=(ROOT if base=='implementation' else RESEARCH)/relative
        target=(root if base=='implementation' else research)/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(runtime_evidence.source_bytes(ROOT,relative,HISTORICAL_COMMIT)
                          if base=='implementation' else source.read_bytes())
    return root,research,folder,bundle


def rewrite(capture,name,change):
    root,research,folder,bundle=capture
    value=json.loads((folder/name).read_bytes())
    change(value)
    (folder/name).write_text(json.dumps(value))
    bundle['files'][name]=digest((folder/name).read_bytes())
    (folder/'bundle.json').write_text(json.dumps(bundle))


def test_no_capture_never_infers_readiness(tmp_path):
    assert runtime_evidence.inspect(tmp_path,tmp_path)=={}


def test_captured_readiness_preserves_limitations_and_author_gate():
    result=preflight.check(ROOT,RESEARCH)
    checks={c['check']:c['status'] for c in result['checks']}
    assert result['status']=='BLOCKED' and result['inference_performed'] is False
    for name in ('Full model identities','Template and effective options','Context fit'):
        assert checks[name]=='PASS'
    assert runtime_evidence.inspect(ROOT,RESEARCH,implementation_commit=HISTORICAL_COMMIT)['Failure attribution']['status']=='BLOCKED'
    closure=gate_b_closure.inspect(ROOT,RESEARCH,implementation_commit=HISTORICAL_COMMIT)
    assert checks['Failure attribution']==closure.get('Failure attribution',{'status':'BLOCKED'})['status']
    assert checks['Gate-B artifact acceptance']=='BLOCKED'


def test_evidence_byte_drift_rejected(capture):
    root,research,folder,_=capture
    with (folder/'qwen_show.json').open('a') as f: f.write(' ')
    with pytest.raises(ValueError,match='Runtime evidence drift'):
        runtime_evidence.inspect(root,research)


def test_implementation_drift_rejected(capture):
    root,research,_,_=capture
    with (root/'src/rest_api_checker/experiment/request.py').open('a') as f: f.write('\n# drift\n')
    with pytest.raises(ValueError,match='Runtime source drift'):
        runtime_evidence.inspect(root,research)


@pytest.mark.parametrize('name,change,match',[
    ('qwen_show.json',lambda d:d['details'].update(quantization_level='Q8_0'),'quantization'),
    ('qwen_slots.json',lambda d:d[0]['params'].update(top_k=99),'Effective option'),
    ('gemma_seed202_slots.json',lambda d:d[0]['params'].update(seed=303),'repetition seed'),
    ('mistral_token_parity.json',lambda d:d[1].update(count=999),'parity'),
    ('context.json',lambda d:d['rows'].pop(),'coverage'),
    ('context.json',lambda d:d['rows'][0].update(input_tokens=32768,total_tokens=33280,margin=-512),'overflow'),
    ('context.json',lambda d:d['rows'][0].update(request_sha256='0'*64),'binding'),
    ('context.json',lambda d:d.update(study_generation_calls=1),'generation boundary'),
])
def test_resealed_inconsistent_evidence_is_not_a_pass(capture,name,change,match):
    rewrite(capture,name,change)
    with pytest.raises(ValueError,match=match):
        runtime_evidence.inspect(capture[0],capture[1])


def test_corruption_reported_as_fail_without_dispatch(capture):
    root,research,folder,_=capture
    (folder/'context.json').unlink()
    result=preflight.check(root,research)
    checks={c['check']:c['status'] for c in result['checks']}
    assert checks['Context fit']=='FAIL'
    assert checks['Gate-B artifact acceptance']=='BLOCKED'
    assert result['inference_performed'] is False
