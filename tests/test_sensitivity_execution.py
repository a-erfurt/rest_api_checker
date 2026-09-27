"""Final acceptance, request and freeze guards without any SQL/provider dispatch."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import shutil

import pytest
from rest_api_checker import freeze, sensitivity_candidate as sc, sensitivity_execution as sx
from rest_api_checker import sensitivity_evaluation as se, sensitivity_freeze as sf
from rest_api_checker.experiment import request, renderer
from rest_api_checker.experiment.encoding import digest,encode

ROOT=Path(__file__).resolve().parents[1];RESEARCH=ROOT.parent/'bachelor_rest_api_checker'


def approval(raw):
    return dict(decision='AUTHOR_ACCEPTED_FOR_P2_SENSITIVITY',candidate_sha256=digest(raw),
                author='FABRICATED TEST',accepted_at='2026-09-26T12:00:00+02:00')


def candidate_fixture(directory):
    source=ROOT/sf.DIRECTORY
    c=json.loads((source/'candidate.json').read_bytes())
    shutil.copytree(source,directory)
    c.update(format=sc.FORMAT,status='NOT ACCEPTED',execution_blockers=['EXACT_CANDIDATE_REVIEW_PENDING'],
        implementation_commit=freeze.git(ROOT,'rev-parse','HEAD'),
        research_commit=freeze.git(RESEARCH,'rev-parse','HEAD'),sources=sc.sources(ROOT,RESEARCH),
        parent_prompt_sha256=sf.PARENT_SHA,evaluator=dict(version=se.VERSION,sha256=se.artifact_hash()))
    context=json.loads((directory/'context.json').read_bytes())
    c['context_proofs']={str(r['run_order']):asdict(request.ContextProof(r['request_sha256'],r['model_digest'],
        r['template_sha256'],c['context_evidence_sha256'],r['input_tokens'])) for r in context['rows']}
    return c


@pytest.fixture
def candidate(tmp_path,monkeypatch):
    c=candidate_fixture(tmp_path/'candidate')
    git=freeze.git
    monkeypatch.setattr(freeze,'git',lambda root,*args:'' if root==ROOT and args[0]=='status' else git(root,*args))
    return c,tmp_path/'candidate'


def test_final_candidate_requires_separate_exact_acceptance(candidate):
    c,_=candidate;raw=encode(c)
    assert sx.require_acceptance(raw,approval(raw))
    for a in ({},approval(raw+b' '),dict(approval(raw),decision='AUTHOR_ACCEPTED_FOR_PROMPT_COMPARISON'),
              dict(approval(raw),author=''),dict(approval(raw),accepted_at=None)):
        with pytest.raises(ValueError):sx.require_acceptance(raw,a)
    preliminary=(ROOT/sf.DIRECTORY/'candidate.json').read_bytes()
    with pytest.raises(ValueError):sx.require_acceptance(preliminary,approval(preliminary))


def test_no_sql_or_provider_before_valid_acceptance(tmp_path,monkeypatch):
    raw=encode(dict(format=sc.FORMAT,status='NOT ACCEPTED',instruction='DO NOT EXECUTE',gate_b_complete=False,
                    execution_blockers=['EXACT_CANDIDATE_REVIEW_PENDING']))
    p=tmp_path/'candidate.json';p.write_bytes(raw);a=tmp_path/'acceptance.json';a.write_text('{}')
    def forbidden(*a,**kw):pytest.fail('Crossed SQL/provider boundary')
    monkeypatch.setattr(sx,'connect',forbidden);monkeypatch.setattr(freeze,'verify_live',forbidden)
    for action in ('prepare','run','reconcile'):
        with pytest.raises(ValueError):sx.main([action,'--candidate',str(p),'--acceptance',str(a)])


def test_all_requests_validate_only_on_sensitivity_path():
    _,_,variant,parent=sf.read_approval(RESEARCH)
    content=b'{"fabricated":true}\n';rendered=renderer.Rendered(content,dict(rendered_evidence_sha256=digest(content)))
    for model in request.MODELS:
        for rep in request.SEEDS:
            req=sf.variant_request(rendered,parent=parent,variant=variant,model=model,model_digest='a'*64,repetition=rep)
            sx.validate_request(req)
            with pytest.raises(ValueError):request.validate_request(req)
            body=json.loads(req.body);body['format']='json'
            with pytest.raises(ValueError):sx.validate_request(request.Request(encode(body),req.metadata))
            with pytest.raises(ValueError):sx.validate_request(request.Request(req.body,{**req.metadata,'seed':999}))


def test_final_offline_verification_and_historical_separation(candidate):
    c,d=candidate
    assert sc.verify(c,ROOT,RESEARCH,d)
    old=json.loads((ROOT/freeze.CANDIDATE).read_bytes())
    assert freeze.verify_historical(old,ROOT,RESEARCH)
    with pytest.raises(ValueError):freeze.verify_candidate(old,ROOT,RESEARCH)


@pytest.mark.parametrize('change',[
    lambda c:c.update(implementation_commit='0'*40),
    lambda c:c.update(research_commit='0'*40),
    lambda c:c['sources'].clear(),
    lambda c:c['configuration']['options'].update(num_predict=1024),
    lambda c:c['models'][0].update(digest='sha256:'+'a'*64),
    lambda c:c['prompt'].update(sha256='0'*64),
    lambda c:c['portable_schedule'][0].update(seed=999),
    lambda c:c['request_inventory'][0].update(request_sha256='0'*64),
    lambda c:c['context_proofs']['1'].update(input_tokens=1),
    lambda c:c['context_proofs'].pop('108'),
    lambda c:c['evaluator'].update(sha256='0'*64),
    lambda c:c['baseline'].update(candidate_sha256='0'*64),
])
def test_final_drift_rejected(candidate,change):
    c,d=candidate;change(c)
    with pytest.raises(ValueError):sc.verify(c,ROOT,RESEARCH,d)


def test_historical_inventory_and_commit_binding_rejected():
    old=json.loads((ROOT/freeze.CANDIDATE).read_bytes())
    for change in (lambda c:c['sources'].pop(next(iter(c['sources']))),
                   lambda c:c.update(implementation_commit=freeze.git(ROOT,'rev-parse','HEAD')),
                   lambda c:c['sources'].update({'implementation:src/rest_api_checker/freeze.py':'0'*64})):
        c=deepcopy(old);change(c)
        with pytest.raises(ValueError):freeze.verify_historical(c,ROOT,RESEARCH)


def test_current_execution_still_rejects_old_commit_even_with_current_sources(monkeypatch):
    old=json.loads((ROOT/freeze.CANDIDATE).read_bytes())
    old['sources']=freeze.source_hashes(ROOT,RESEARCH)
    monkeypatch.setattr(freeze.gate_b_closure,'inspect',lambda *a:{'Failure attribution':{'status':'PASS'}})
    with pytest.raises(ValueError,match='Execution commit drift'):
        freeze.verify_candidate(old,ROOT,RESEARCH)


def test_valid_acceptance_with_wrong_commit_stops_before_sql(candidate,tmp_path,monkeypatch):
    c,_=candidate;c['implementation_commit']='0'*40
    p=tmp_path/'bad.json';raw=encode(c);p.write_bytes(raw)
    a=tmp_path/'approval.json';a.write_bytes(encode(approval(raw)))
    def forbidden(*a,**kw):pytest.fail('SQL reached before freeze verification')
    monkeypatch.setattr(sx,'connect',forbidden)
    with pytest.raises(ValueError,match='Execution commit drift'):
        sx.main(['prepare','--candidate',str(p),'--acceptance',str(a)])
