"""Candidate safeguards; real HTTP is forbidden by the global test fixture."""
from collections import Counter
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from rest_api_checker import sensitivity_freeze as sf
from rest_api_checker.experiment import request, renderer, schedule
from rest_api_checker.experiment.encoding import digest, encode

ROOT=Path(__file__).resolve().parents[1]
RESEARCH=ROOT.parent/'bachelor_rest_api_checker'
spec=importlib.util.spec_from_file_location('sensitivity_prepare',ROOT/'tools/sensitivity_freeze/prepare.py')
prep=importlib.util.module_from_spec(spec);spec.loader.exec_module(prep)


def test_schedule_pairing_and_fixed_repetition_coverage():
    raw=sf.schedule_bytes();assert raw==sf.schedule_bytes()
    value=json.loads(raw);slots=value['slots']
    assert len(slots)==108 and [s['run_order'] for s in slots]==list(range(1,109))
    assert {(s['case'],s['model'],s['repetition'],s['seed']) for s in slots}=={
        (c,m,r,seed) for c in schedule.CASES for m in request.MODELS for r,seed in request.SEEDS.items()}
    assert Counter(s['model'] for s in slots)==dict.fromkeys(request.MODELS,36)
    assert all(s['prompt']==sf.PROMPT for s in slots)
    assert [(s['case'],s['model'],s['repetition']) for s in slots]==[
        (s.case,s.model,s.repetition) for s in schedule.comparison_schedule() if s.prompt=='P2']


def copied_research(tmp_path):
    for p in (RESEARCH/sf.BASE).rglob('*'):
        if p.is_file():
            target=tmp_path/p.relative_to(RESEARCH);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    return tmp_path


def test_exact_approval_and_historical_review():
    manifest,record,variant,parent=sf.read_approval(RESEARCH)
    assert len(variant)==5032 and digest(variant)==sf.SHA
    assert digest(parent)==sf.PARENT_SHA and record['frozen_for_sensitivity'] is False
    assert manifest['semantic_equivalence_review']['pass_count']==37


@pytest.mark.parametrize('field,value',[('sha256','0'*64),('id','P1'),('byte_length',5031)])
def test_reject_approval_identity_changes(tmp_path,field,value):
    r=copied_research(tmp_path);m=json.loads((r/sf.MANIFEST).read_bytes())
    path=r/m['approval']['exact_text_approval_record']['path'];a=json.loads(path.read_bytes())
    a['approved_candidates'][0][field]=value;path.write_bytes(encode(a))
    m['approval']['exact_text_approval_record']['sha256']=digest(path.read_bytes());(r/sf.MANIFEST).write_bytes(encode(m))
    with pytest.raises(ValueError):sf.read_approval(r)


@pytest.mark.parametrize('file',['p2_structured_checklist_sensitivity_v1.txt','p2_structured_checklist_v1.txt','semantic_equivalence_review_p2_sensitivity_v1.md'])
def test_reject_scientific_byte_drift(tmp_path,file):
    r=copied_research(tmp_path);p=r/sf.BASE/file;p.write_bytes(p.read_bytes()+b'\n')
    with pytest.raises(ValueError):sf.read_approval(r)


def test_request_only_changes_system_message_and_remains_outside_execution_allowlist():
    _,_,variant,parent=sf.read_approval(RESEARCH)
    content=b'{"fabricated_evidence":true}\n'
    rendered=renderer.Rendered(content,{'rendered_evidence_sha256':digest(content)})
    for model in request.MODELS:
        for repetition in request.SEEDS:
            kw=dict(model=model,model_digest='a'*64,repetition=repetition)
            base=request.build_request(rendered,prompt_name='P2',prompt=parent,**kw)
            value=sf.variant_request(rendered,parent=parent,variant=variant,**kw)
            expected=json.loads(base.body);expected['messages'][0]['content']=variant.decode()
            assert value.body==encode(expected)
            with pytest.raises(ValueError):request.validate_request(value)
            with pytest.raises(ValueError):sf.variant_request(rendered,parent=parent,variant=variant+b' ',**kw)


@pytest.mark.parametrize('url,payload',[
    ('http://127.0.0.1:11434/api/generate',{}),
    ('http://127.0.0.1:11434/api/chat',{'model':'qwen3.6:27b'}),
    ('http://127.0.0.1:11434/api/chat',{'_debug_render_only':False,'truncate':False}),
    ('http://127.0.0.1:11434/api/chat',{'_debug_render_only':True}),
    ('http://127.0.0.1:9999/completion',{}),
    ('http://example.com:9999/tokenize',{'content':'x','add_special':True,'parse_special':True}),
])
def test_http_guard_rejects_generation_before_network(url,payload):
    with pytest.raises(ValueError):prep.post(url,payload)


def test_candidate_cannot_be_declared_executable():
    with pytest.raises(ValueError):sf.verify_bundle({'format':sf.FORMAT,'status':'ACCEPTED'},None,None,None,None)
