"""Fabricated mechanical fixtures only; no Oracle or study-body evaluation."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/final_evaluation_candidates/prepare.py'
spec = importlib.util.spec_from_file_location('candidate_materializer', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def replacement(path, kind, **extra):
    return {'action':'replace_value','instance_pointer':path,'replacement_kind':kind,**extra}


@pytest.mark.parametrize('change,body,expected', [
    (replacement('/data/1/key','integer',replacement_literal=7),
     b'{"data":[{"key":null},{"key":"fabricated"}]}',b'{"data":[{"key":null},{"key":7}]}'),
    (replacement('/detail','null'),b'{"loc":"x","detail":[{"msg":"fabricated"}],"tail":1}',b'{"loc":"x","detail":null,"tail":1}'),
    (replacement('/detail/0/loc','string',replacement_literal='file'),
     b' {"detail":[{"loc" : ["fake", 9],"msg":"\\u00fc","ctx":{"error":{}}}]}\n',
     b' {"detail":[{"loc" : "file","msg":"\\u00fc","ctx":{"error":{}}}]}\n'),
    ({'action':'remove_member','instance_pointer':'/detail/1/msg'},
     b'{"detail":[{"msg":"keep"},{"loc":[],"msg":"remove","type":"keep"}]}',
     b'{"detail":[{"msg":"keep"},{"loc":[],"type":"keep"}]}'),
])
def test_planned_body_mechanisms_preserve_exact_other_bytes(change,body,expected):
    actual,status,media,edit=m.transform(body,422,'application/json',change)
    assert actual==expected and status==422 and media=='application/json'
    assert body[:edit['start_byte']]+bytes.fromhex(edit['replacement_hex'])+body[edit['end_byte_exclusive']:]==expected
    assert edit['outside_span_identical'] and edit['parsed_tree_exactly_planned']


@pytest.mark.parametrize('body,pointer,expected',[
    (b'{ "x":1, "y":2 }','/x',b'{ "y":2 }'),
    (b'{"y":2 , "x":1 }','/x',b'{"y":2  }'),
    (b'{ "x":1 }','/x',b'{  }'),
    ('{"ü":"ß","a/b":{"~":"z"}}'.encode(),'/a~1b/~0','{"ü":"ß","a/b":{}}'.encode()),
])
def test_remove_delimiters_and_unicode_offsets(body,pointer,expected):
    after,_=m.splice(body,{'action':'remove_member','instance_pointer':pointer})
    assert after==expected


@pytest.mark.parametrize('change,status,media',[
    ({'action':'replace_http_status','literal':500},500,'application/json'),
    ({'action':'replace_content_type','literal':'text/plain'},200,'text/plain'),
    ({'action':'replace_content_type','literal':'application/xml'},200,'application/xml'),
    (None,200,'application/json'),
])
def test_envelope_edits_and_identity_never_reserialize(change,status,media):
    body=b' \n{ "detail" : [ 1, "\\u00e4" ] }\n'
    result=m.transform(body,200,'application/json',change)
    assert result==(body,status,media,None)


@pytest.mark.parametrize('body',[b'{broken',b'{"x":1,"x":2}',b'NaN',b'\xff',b'{} trailing'])
def test_bad_json_rejected(body):
    with pytest.raises((ValueError,UnicodeError)):
        m.transform(body,200,'application/json',None)


@pytest.mark.parametrize('body,change',[
    (b'{"x":[]}',replacement('/missing','null')),
    (b'{"x":1}',replacement('/x','null')),
    (b'{"x":"a"}',replacement('/x','integer',replacement_literal=True)),
    (b'{}',{'action':'replace_http_status','literal':200}),
    (b'{"x":[]}',{'action':'unsupported','instance_pointer':'/x'}),
])
def test_unsupported_or_noop_edit_rejected(body,change):
    with pytest.raises(ValueError):m.transform(body,200,'application/json',change)


def minimal_case(ident='FC-HTTS-009',**extra):
    return {'case_id':ident,'base_template_id':None,'supplied_http_status':422,
            'raw_content_type':'application/json','cap_family_id':'fabricated',**extra}


def corpus(row,excluded=True):
    return {'pilot_comparisons':[row] if excluded else [],'development_comparisons':[],
            'qualification_comparisons':[],'supplemental_static_literals':[],
            'observations':[] if excluded else [row],'spike_instance_structures':[],
            'supplemental_dynamic_source_review':[]}


def comparison_row(body,ident='fabricated',group='pilot'):
    return {'id':ident,'group':group,'body_hex':body.hex(),'body_sha256':m.sha(body),
            'http_status':422,'content_type':'application/json'}


@pytest.mark.parametrize('other',[b'{"x":42}',b'{ "x" : 42 }',b'{"x":99}'])
def test_excluded_bytes_formatting_and_cosmetic_values_are_blocked(other):
    c=minimal_case();body=b'{"x":42}'
    report=m.compare([c],{c['case_id']:body},corpus(comparison_row(other)),{})
    assert report['blockers']


def test_natural_copy_only_allowed_for_registered_natural_candidate():
    body=b'{"fabricated":true}';row=comparison_row(body,'HTTS-PO-0003','wave1')
    c=minimal_case()
    assert not m.compare([c],{c['case_id']:body},corpus(row,False),{})['blockers']
    c['case_id']='FC-HTTS-010'
    assert m.compare([c],{c['case_id']:body},corpus(row,False),{})['blockers']


def test_shared_body_envelope_dependency_and_duplicate_triple():
    body=b'{"fabricated":true}';empty=corpus(comparison_row(body));empty['pilot_comparisons']=[]
    a=minimal_case('A');b=minimal_case('B',supplied_http_status=500)
    report=m.compare([a,b],{'A':body,'B':body},empty,{})
    assert not report['blockers'] and len(report['shared_body_dependencies'])==1
    b['supplied_http_status']=422
    assert m.compare([a,b],{'A':body,'B':body},empty,{})['blockers']


def fabricated_groups():
    cases=[];ids=sorted(m.AUTHORIZED)
    keys=('api','operation','provenance_class','base_template_id','base_group_id','construction_family_id',
          'structural_pattern_group_id','parent_observation_id','parent_family_id','root_id','immediate_parent_id',
          'fault_control_family','variant','dependency_relation')
    for i,ident in enumerate(ids):
        c={k:'fabricated' for k in keys};c.update(case_id=ident,cap_family_id=f'family-{i//2}',
           structural_pattern_group_id=f'group-{(i//2)%4}',sibling_ids=[ids[i^1]])
        cases.append(c)
    plan={'primary_candidates':copy.deepcopy(cases),'families':[{'family_id':f'family-{i}',
          'primary_case_ids':ids[2*i:2*i+2]} for i in range(7)]}
    return cases,plan


def test_group_consistency_and_mapping_drift():
    cases,plan=fabricated_groups();assert m.group_check(cases,plan)['max_two_verified']
    cases[0]['variant']='drift'
    with pytest.raises(ValueError,match='mapping mismatch'):m.group_check(cases,plan)


def test_group_cap_and_extra_identifier_rejected():
    cases,plan=fabricated_groups();cases[0]['cap_family_id']=cases[2]['cap_family_id']
    with pytest.raises(ValueError):m.group_check(cases,plan)
    cases,plan=fabricated_groups();cases.append(copy.deepcopy(cases[0]))
    with pytest.raises(ValueError):m.group_check(cases,plan)


def test_standalone_has_no_application_import_or_network_use():
    subprocess.run([sys.executable,'-S','-c',
       'import runpy,sys,socket; '
       'socket.socket=lambda *a,**k: (_ for _ in ()).throw(RuntimeError("network forbidden")); '
       'runpy.run_path(sys.argv[1]); '
       'assert not any(x.startswith(("rest_api_checker","jsonschema","openapi_schema_validator")) for x in sys.modules)',str(SCRIPT)],check=True)


def test_wrong_plan_and_existing_output_fail_before_writes(tmp_path):
    research=tmp_path/'research';p=research/m.PLAN;p.parent.mkdir(parents=True);p.write_bytes(b'{}')
    output=tmp_path/'output'
    with pytest.raises(ValueError,match='binding mismatch'):m.prepare(research,tmp_path,output,materialized_at='fixed')
    assert not output.exists()
    output.mkdir();marker=output/'keep';marker.write_bytes(b'keep')
    with pytest.raises(ValueError,match='must not exist'):m.prepare(research,tmp_path,output,materialized_at='fixed')
    assert marker.read_bytes()==b'keep'
