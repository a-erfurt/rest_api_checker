"""Author boundary and captured technical evidence remain distinct."""
import json
from pathlib import Path
import shutil

import pytest

from rest_api_checker import freeze, gate_b_closure
from rest_api_checker.experiment.encoding import digest

ROOT=Path(__file__).resolve().parents[1]
RESEARCH=ROOT.parent/'bachelor_rest_api_checker'


def test_missing_closure_has_no_inferred_pass(tmp_path):
    assert gate_b_closure.inspect(tmp_path,tmp_path)=={}


@pytest.mark.parametrize('record',[{}, {'decision':'AUTHOR_ACCEPTED_FOR_PROMPT_COMPARISON'},
    {'decision':'AUTHOR_ACCEPTED_FOR_PROMPT_COMPARISON','candidate_sha256':digest(b'candidate'),
     'failure_qualification':'ACCEPT_BOUNDED_EVIDENCE_WITH_UNOBSERVED_CRASH_OOM','author':'','accepted_at':'2026-09-26T12:00:00+02:00'},
    {'decision':'AUTHOR_ACCEPTED_FOR_PROMPT_COMPARISON','candidate_sha256':digest(b'candidate'),
     'failure_qualification':'ACCEPT_BOUNDED_EVIDENCE_WITH_UNOBSERVED_CRASH_OOM','author':'FABRICATED UNIT TEST','accepted_at':'2026-09-26T12:00:00'},
])
def test_no_implicit_or_incomplete_author_acceptance(record):
    with pytest.raises((ValueError,KeyError)): freeze.require_acceptance(b'candidate',record)


def test_acceptance_binds_exact_bytes_only():
    record=dict(decision='AUTHOR_ACCEPTED_FOR_PROMPT_COMPARISON',candidate_sha256=digest(b'FABRICATED'),
        failure_qualification='ACCEPT_BOUNDED_EVIDENCE_WITH_UNOBSERVED_CRASH_OOM',author='FABRICATED UNIT TEST',accepted_at='2026-09-26T12:00:00+02:00')
    assert freeze.require_acceptance(b'FABRICATED',record)
    with pytest.raises(ValueError): freeze.require_acceptance(b'FABRICATED changed',record)


def test_unaccepted_adapter_never_connects_or_dispatches(tmp_path,monkeypatch):
    from rest_api_checker import accepted_comparison
    candidate=tmp_path/'candidate.json'; candidate.write_text('{"status":"NOT AUTHOR-ACCEPTED"}')
    approval=tmp_path/'approval.json'; approval.write_text('{}')
    def forbidden(*args,**kwargs): pytest.fail('Unaccepted execution crossed SQL/network boundary')
    monkeypatch.setattr(accepted_comparison,'connect',forbidden)
    monkeypatch.setattr(accepted_comparison.freeze,'verify_live',forbidden)
    for action in ('prepare','run','reconcile'):
        with pytest.raises(ValueError,match='author acceptance'):
            accepted_comparison.main([action,'--candidate',str(candidate),'--acceptance',str(approval)])


def test_accepted_setup_archives_exact_review_bytes_only():
    from rest_api_checker.accepted_comparison import accepted_setup
    raw=b'FABRICATED'; approval=json.dumps(dict(decision='AUTHOR_ACCEPTED_FOR_PROMPT_COMPARISON',
        candidate_sha256=digest(raw),failure_qualification='ACCEPT_BOUNDED_EVIDENCE_WITH_UNOBSERVED_CRASH_OOM',
        author='FABRICATED UNIT TEST',accepted_at='2026-09-26T12:00:00+02:00')).encode()
    class Repository:
        def __init__(self): self.files=[]
        def archive(self,name,body): self.files.append(body); return len(self.files)
    repo=Repository()
    value=accepted_setup(repo,raw,approval,{'files':[]})
    assert repo.files==[raw,approval] and value['gate_b_complete'] is True
    assert value['author_candidate_sha256']==digest(raw) and value['fabricated'] is False


def test_technical_review_is_exact_spool_bound(monkeypatch):
    from rest_api_checker import accepted_comparison
    monkeypatch.setattr(accepted_comparison.spool,'read',lambda p:(b'FABRICATED',{},None))
    record=dict(spool_sha256=digest(b'FABRICATED'),attribution='isolated',reviewer='FABRICATED UNIT TEST',
        reason='isolated fabricated connection loss',reviewed_at='2026-09-26T12:00:00+02:00')
    assert accepted_comparison.technical_review('unused',record)=='isolated'
    for changed in (dict(record,spool_sha256='0'*64),dict(record,reviewer=''),dict(record,attribution='valid')):
        with pytest.raises(ValueError): accepted_comparison.technical_review('unused',changed)


@pytest.mark.parametrize('drift',['version','digest','template','binary','cpu','ram','os'])
def test_live_metadata_identity_drift_blocks_without_generation(monkeypatch,tmp_path,drift):
    from rest_api_checker import runtime_evidence
    identity={'name':'fabricated-model','digest':'1'*64,'show':'model.json'}
    folder=tmp_path/runtime_evidence.DIRECTORY; folder.mkdir(parents=True)
    (folder/'model.json').write_text('{"template":"native"}')
    binary=tmp_path/'runner'; binary.write_bytes(b'fabricated binary')
    candidate=dict(models=[identity],runtime=dict(ollama={'version':'fabricated'},architecture='fabricated',
        os='fabricated OS',cpu='fabricated CPU',python='fabricated Python',hardware='fabricated GPU',ram_bytes=123,binaries={str(binary):{'sha256':digest(binary.read_bytes())}}))
    observed=[]
    def api(path,data=None):
        observed.append(path)
        if path=='/api/version': return {'version':'changed' if drift=='version' else 'fabricated'}
        if path=='/api/tags': return {'models':[dict(identity,digest='2'*64 if drift=='digest' else identity['digest'])]}
        if path=='/api/show': return {'template':'changed' if drift=='template' else 'native'}
        pytest.fail('Generation/loading endpoint called')
    monkeypatch.setattr(freeze.platform,'machine',lambda:'fabricated')
    monkeypatch.setattr(freeze.platform,'python_version',lambda:'fabricated Python')
    def command(args,**kwargs):
        if args==['sw_vers']: return 'changed' if drift=='os' else 'fabricated OS'
        if args==['system_profiler','SPDisplaysDataType']: return 'fabricated GPU'
        if args[-1]=='machdep.cpu.brand_string': return 'changed' if drift=='cpu' else 'fabricated CPU'
        return '999' if drift=='ram' else '123'
    monkeypatch.setattr(freeze.subprocess,'check_output',command)
    if drift=='binary': binary.write_bytes(b'changed')
    with pytest.raises(ValueError,match='drift'): freeze.verify_live(candidate,tmp_path,api)
    assert set(observed)<= {'/api/version','/api/tags','/api/show'}


@pytest.fixture
def closure_copy(tmp_path):
    folder=tmp_path/gate_b_closure.DIRECTORY
    shutil.copytree(ROOT/gate_b_closure.DIRECTORY,folder)
    bundle=json.loads((folder/'bundle.json').read_bytes())
    research=tmp_path/'research'
    for key in bundle['sources']:
        namespace,relative=key.split(':',1)
        source=(ROOT if namespace=='implementation' else RESEARCH)/relative
        target=(tmp_path if namespace=='implementation' else research)/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        commit=json.loads((ROOT/freeze.CANDIDATE).read_bytes())['implementation_commit']
        target.write_bytes(gate_b_closure.runtime_evidence.source_bytes(ROOT,relative,commit)
                          if namespace=='implementation' else source.read_bytes())
    return tmp_path,research,folder,bundle


def test_closure_evidence_drift_never_passes(closure_copy):
    root,research,folder,_=closure_copy
    (folder/'test_results.json').write_text('{}')
    with pytest.raises(ValueError,match='Closure evidence drift'):
        gate_b_closure.inspect(root,research)


@pytest.mark.parametrize('mutation', ['author','crash','skipped','missing_group'])
def test_resealed_overclaim_or_incomplete_tests_rejected(closure_copy,monkeypatch,mutation):
    root,research,folder,bundle=closure_copy
    monkeypatch.setattr(gate_b_closure.runtime_evidence,'inspect',lambda *a,**kw:{name:{'status':'PASS'} for name in
        ('Full model identities','Template and effective options','Context fit')})
    old=root/gate_b_closure.runtime_evidence.DIRECTORY; old.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/gate_b_closure.runtime_evidence.DIRECTORY/'failures.json',old/'failures.json')
    name='failure_decision.json' if mutation in ('author','crash') else 'test_results.json'
    value=json.loads((folder/name).read_bytes())
    if mutation=='author': value['accepted_option']='A'
    if mutation=='crash': value['crash_oom_observed']=True
    if mutation=='skipped': value['full']['skipped']=1
    if mutation=='missing_group': del value['full']['test_counts_by_class']['tests.persistence.test_application_security']
    (folder/name).write_text(json.dumps(value))
    bundle['files'][name]=digest((folder/name).read_bytes())
    (folder/'bundle.json').write_text(json.dumps(bundle))
    with pytest.raises(ValueError): gate_b_closure.inspect(root,research)
