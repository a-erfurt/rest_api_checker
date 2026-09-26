"""Fabricated responses only. Tests never instantiate a live network connection."""
from dataclasses import asdict, replace
from itertools import product
import json
from pathlib import Path

import pytest

from rest_api_checker.experiment.encoding import Blocked, digest, encode, loads
from rest_api_checker.experiment import parser, provider, renderer, request, schedule
from rest_api_checker.persistence.importer import load_development, PROMPT_HASHES

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT.parent / 'bachelor_rest_api_checker'
CANDIDATES = RESEARCH / '03_research_design/prompt_candidates_v1'
PROMPT_PATHS = dict(P1='p1_minimal_direct_v1.txt', P2='p2_structured_checklist_v1.txt',
                   P3='p3_explicit_contract_interpretation_v1.txt')
VALID = json.dumps({c: {'verdict': 'PASS', 'reason': ' fabricated evidence '} for c in ('c1','c2','c3')})


def sample(body=b'{ malformed\r\n', content_type=None):
    contract = {'openapi':'3.1.0','info':{'secret':'unrelated'},'paths':{'/x':{'post':{
        'responses':{'200':{'description':'ok','content':{'application/json':{'schema':{
            '$ref':'#/components/schemas/A'}}}}, '4XX':{'$ref':'#/components/responses/Error'}}},
        'get':{'secret':'unrelated'}}},'components':{
        'responses':{'Error':{'description':'error','content':{'text/json':{'schema':{'$ref':'#/components/schemas/B'}}}}},
        'schemas':{'A':{'type':'object','properties':{'b':{'$ref':'#/components/schemas/B'}}},
                   'B':{'type':'string','description':'contract annotation'},'Unused':{'secret':'unrelated'}}}}
    return renderer.Evidence(encode(contract),'post','/x',200,content_type,body)


def rendered(evidence=None):
    return renderer.render(evidence or sample(), contract_identity='SECRET_SOURCE', body_identity='SECRET_CASE')


def built(model=request.MODELS[0], repetition=1, prompt_name='P1'):
    return request.build_request(rendered(), prompt_name=prompt_name,
        prompt=(CANDIDATES/PROMPT_PATHS[prompt_name]).read_bytes(), model=model,
        model_digest='sha256:'+'a'*64, repetition=repetition)


@pytest.mark.parametrize('vector', tuple(product(parser.VERDICTS, repeat=3)))
def test_all_27_vectors_are_valid(vector):
    value = {c:{'verdict':v,'reason':' R '} for c,v in zip(('c1','c2','c3'),vector)}
    result = parser.parse(' \t\r\n'+json.dumps(value)+'\r\n ')
    assert result.status=='VALID_OUTPUT'
    assert [result.prediction[c] for c in ('c1','c2','c3')]==list(vector)
    assert result.prediction['c1_reason']==' R '


@pytest.mark.parametrize('content', ['', ' ', '{}', '[]', 'null', 'true', '0', VALID+VALID,
    '```json\n'+VALID+'\n```', 'answer: '+VALID, VALID+' prose', '<think>x</think>'+VALID,
    VALID.replace('"c1":', '"c1":{},"c1":',1),
    VALID.replace('"verdict": "PASS"','"verdict":"PASS","verdict":"PASS"',1),
    VALID.replace('"PASS"','"pass"',1),VALID.replace('"PASS"','" PASS"',1),
    VALID.replace('"PASS"','"PASS "',1),VALID.replace('"PASS"','"UNKNOWN"',1),
    VALID.replace('"PASS"','true',1),VALID.replace('"PASS"','null',1),
    VALID.replace('"PASS"','[]',1),VALID.replace('"PASS"','NaN',1),
    VALID.replace('" fabricated evidence "','" \\t\\n "',1),
    VALID.replace('" fabricated evidence "','42',1),
    VALID.replace('"c1":', '"extra":0,"c1":',1),
    VALID.replace('"reason":', '"extra":0,"reason":',1),
    VALID.replace('"reason":', '"other":',1),VALID[:-2], '\u00a0'+VALID])
def test_db15_strict_failures(content):
    assert parser.parse(content).status=='PARSER_FAILURE'
    assert parser.parse(content)==parser.parse(content)


def test_schema_and_parser_agree_on_normal_contract():
    from jsonschema import Draft202012Validator
    schema = json.loads((Path(parser.__file__).parent/'output_schema_v1.json').read_bytes())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(json.loads(VALID))
    assert len(parser.artifact_hash())==64


@pytest.mark.parametrize('body', [b'null',b'',b'{"x":1,"x":2}',b'{ malformed\r\n',
    ' \r\n"Grüße 🦊"\t\\\x00'.encode(),b'\xef\xbb\xbf{}'])
def test_deterministic_renderer_body_roundtrip(body):
    evidence=sample(body,' Application/JSON; charset=utf-8 ')
    a,b=rendered(evidence),rendered(evidence)
    assert a==b
    value=loads(a.content)
    assert value['observed_response']['body'].encode()==body
    assert value['observed_response']['content_type']==' Application/JSON; charset=utf-8 '
    assert value['openapi']['paths']['/x']['post']['responses']==loads(evidence.contract)['paths']['/x']['post']['responses']
    assert a.metadata['reference_closure_paths']==['/components/responses/Error','/components/schemas/A','/components/schemas/B']
    assert b'unrelated' not in a.content
    assert value['openapi']['components']['schemas']['A']['properties']['b']['$ref']=='#/components/schemas/B'


def test_db35_allowlist_and_metadata_leakage():
    evidence=sample()
    nearby={**asdict(evidence),'case_id':'SECRET_CASE','oracle':'SECRET_ORACLE','fault_id':'SECRET_FAULT',
            'family_id':'SECRET_FAMILY','expected':'SECRET_EXPECTED','approval':'SECRET_APPROVAL'}
    with pytest.raises(TypeError):
        renderer.Evidence(**nearby)
    with pytest.raises(Blocked,match='ALLOWLIST'):
        renderer.render(nearby,contract_identity='x',body_identity='x')
    result=rendered(evidence)
    assert b'SECRET' not in result.content
    assert result.metadata['body_identity']=='SECRET_CASE'
    assert loads(result.content)['observed_response']['content_type'] is None
    assert set(loads(result.content))=={'operation','openapi','observed_response'}
    assert b'SECRET_FAULT' in rendered(sample(b'SECRET_FAULT')).content  # Raw body is not scrubbed.


@pytest.mark.parametrize('kind', ['external','missing','cycle','sibling','dialect','array','invalid_utf8'])
def test_renderer_holds(kind):
    evidence=sample()
    doc=loads(evidence.contract)
    schema=doc['components']['schemas']['A']
    if kind=='external': schema['properties']['b']['$ref']='https://example.invalid/schema'
    if kind=='missing': schema['properties']['b']['$ref']='#/missing'
    if kind=='cycle': schema['properties']['b']['$ref']='#/components/schemas/A'
    if kind=='sibling': schema['properties']['b']['description']='unqualified sibling'
    if kind=='dialect': doc['jsonSchemaDialect']='https://example.invalid/dialect'
    if kind=='array':
        doc['components']['schemas']['B']={'anyOf':[{'type':'string'},{'type':'integer'}]}
        schema['properties']['b']['$ref']='#/components/schemas/B/anyOf/0'
    evidence=replace(evidence,contract=encode(doc),body=b'\xff' if kind=='invalid_utf8' else evidence.body)
    with pytest.raises(Blocked): rendered(evidence)


def test_exact_released_inputs_without_oracle_measurement(monkeypatch):
    from rest_api_checker import oracle
    monkeypatch.setattr(oracle,'evaluate_response',lambda *a,**k: pytest.fail('Oracle measurement forbidden'))
    manifest,files=load_development(ROOT/'artifacts/development_dataset_v1',ROOT/'docs/development_dataset_v1_release.json',RESEARCH)
    for case in manifest['cases']:
        contract=manifest['sources'][manifest['contracts'][case['api']]]
        evidence=renderer.Evidence(files[contract['path']],case['operation']['method'],case['operation']['path'],
                                  case['status'],case['content_type'],files[case['body']['path']])
        value=rendered(evidence)
        assert value==rendered(evidence)
        assert loads(value.content)['observed_response']['body'].encode()==evidence.body
        assert case['case_id'].encode() not in value.content


@pytest.mark.parametrize('prompt_name', ['P1','P2','P3'])
@pytest.mark.parametrize('model',request.MODELS)
@pytest.mark.parametrize('repetition',[1,2,3])
def test_db46_exact_request(prompt_name,model,repetition):
    value=built(model,repetition,prompt_name)
    payload=json.loads(value.body)
    assert set(payload)==({'model','stream','messages','options','think'} if model==request.MODELS[0] else {'model','stream','messages','options'})
    assert payload['options']=={**request.OPTIONS,'seed':request.SEEDS[repetition]}
    assert payload['stream'] is False and value.timeout==300
    assert payload['messages']==[{'role':'system','content':(CANDIDATES/PROMPT_PATHS[prompt_name]).read_bytes().decode()},
                                {'role':'user','content':rendered().content.decode()}]
    assert digest(payload['messages'][0]['content'].encode())==PROMPT_HASHES[prompt_name]
    assert ('think' in payload)==(model==request.MODELS[0])
    if 'think' in payload: assert payload['think'] is False
    assert b'SECRET' not in value.body


def test_prompt_mismatch_and_context_overflow():
    with pytest.raises(Blocked,match='PROMPT_HASH'):
        request.build_request(rendered(),prompt_name='P1',prompt=b'changed',model=request.MODELS[0],model_digest='a'*64,repetition=1)
    req=built()
    proof=request.ContextProof(digest(req.body),req.metadata['model_digest'],'b'*64,'c'*64,32256)
    proof.verify(req)
    with pytest.raises(Blocked,match='OVERFLOW'): replace(proof,input_tokens=32257).verify(req)
    with pytest.raises(Blocked,match='IDENTITY'): replace(proof,request_sha256='0'*64).verify(req)


def receipt(content=VALID, **envelope):
    value={'done':True,'message':{'role':'assistant','content':content}, **envelope}
    return provider.Receipt(encode(value),{'complete':True,'error_kind':None,'http_status':200,'duration_ms':7},
                            '2026-09-26T12:00:00+00:00','2026-09-26T12:00:01+00:00')


@pytest.mark.parametrize('content', ['', ' ', '{', '<think>x</think>'+VALID, VALID])
def test_db49_final_content_boundary(content):
    response=receipt(content,done_reason='length')
    result=provider.classify(response)
    assert result.kind=='FINAL'
    assert (parser.parse(result.content).status=='VALID_OUTPUT')==(content==VALID)


def test_separate_thinking_never_parsed():
    response=receipt(message={'role':'assistant','content':'','thinking':VALID})
    result=provider.classify(response)
    assert result.thinking==VALID and parser.parse(result.content).status=='PARSER_FAILURE'
    assert provider.classify(receipt(message={'role':'assistant','thinking':VALID})).kind=='BLOCKED'
    assert provider.classify(receipt(done=False)).kind=='BLOCKED'
    assert provider.classify(replace(receipt(),raw=b'{')).kind=='BLOCKED'
    assert provider.classify(replace(receipt(),transport={'complete':False,'error_kind':'transport'})).kind=='TECHNICAL_FAILURE'
    assert provider.classify(replace(receipt(),transport={'complete':True,'http_status':503})).kind=='TECHNICAL_FAILURE'
    assert provider.classify(replace(receipt(),transport={'complete':True,'http_status':400})).kind=='BLOCKED'


def test_schedule_exact_deterministic():
    rows=schedule.comparison_schedule()
    schedule.validate(rows)
    assert len(rows)==len(set(rows))==324
    assert schedule.dry_run_bytes()==schedule.dry_run_bytes()
    assert {s.repetition for s in rows if s.case=='DEV-01' and s.prompt=='P1' and s.model==request.MODELS[0]}=={1,2,3}
    assert all({s.prompt for s in rows[i:i+36]}==set(schedule.PROMPTS) for i in (0,108,216))
    with pytest.raises(Blocked): schedule.validate(rows[:-1])


class FakeConnection:
    calls=[]
    sock=None
    def __init__(self,*args,**kwargs): self.calls.append(('init',args,kwargs))
    def connect(self): pass
    def request(self,*args,**kwargs):
        self.calls.append(('request',args,kwargs))
        raise ConnectionResetError('fabricated connection reset')
    def close(self): self.calls.append(('close',))


def test_http_client_no_automatic_retries():
    FakeConnection.calls=[]
    client=provider.OllamaClient(connection_factory=FakeConnection)
    starts=[]
    response=client.send(built(),on_start=starts.append)
    assert len(starts)==1 and sum(x[0]=='request' for x in FakeConnection.calls)==1
    assert provider.classify(response).kind=='TECHNICAL_FAILURE'
    assert FakeConnection.calls[0][2]['timeout']==300
    assert FakeConnection.calls[1][2]['body']==built().body


@pytest.mark.parametrize('change', ['format','tools','images','history','seed','think','timeout','prompt'])
def test_http_boundary_rejects_changed_requests(change):
    req=built()
    payload=json.loads(req.body)
    if change=='format': payload['format']='json'
    if change=='tools': payload['tools']=[]
    if change=='images': payload['messages'][1]['images']=[]
    if change=='history': payload['messages'].append({'role':'assistant','content':'previous'})
    if change=='seed': payload['options']['seed']=999
    if change=='think': payload.pop('think')
    if change=='prompt': payload['messages'][0]['content']+='changed'
    changed=replace(req,body=encode(payload),timeout=301 if change=='timeout' else 300)
    FakeConnection.calls=[]
    client=provider.OllamaClient(connection_factory=FakeConnection)
    with pytest.raises(Blocked): client.send(changed,on_start=lambda at:None)
    assert FakeConnection.calls==[]


class FakeResponse:
    status=200
    length=None
    def __init__(self,chunks): self.chunks=iter(chunks)
    def getheaders(self): return [('Content-Type','application/json')]
    def read1(self,n):
        value=next(self.chunks,b'')
        if isinstance(value,Exception): raise value
        return value


@pytest.mark.parametrize('chunks,kind', [([receipt().raw,b''],'FINAL'),
    ([b'partial',provider.http.client.IncompleteRead(b' tail')],'TECHNICAL_FAILURE')])
def test_raw_http_envelope_and_partial_retention(chunks,kind):
    class Connection(FakeConnection):
        def request(self,*args,**kwargs): self.calls.append(('request',args,kwargs))
        def getresponse(self): return FakeResponse(chunks)
    Connection.calls=[]
    result=provider.OllamaClient(connection_factory=Connection).send(built(),on_start=lambda at:None)
    assert provider.classify(result).kind==kind
    assert result.raw==(receipt().raw if kind=='FINAL' else b'partial tail')
    assert sum(x[0]=='request' for x in Connection.calls)==1


def test_reference_pointer_escapes_and_non_schema_targets():
    ev=sample()
    doc=loads(ev.contract)
    doc['components']['schemas']['slash/name~']={'type':'string'}
    doc['components']['schemas']['B']={'$ref':'#/components/schemas/slash~1name~0'}
    value=rendered(replace(ev,contract=encode(doc)))
    assert '/components/schemas/slash~1name~0' in value.metadata['reference_closure_paths']
    assert loads(value.content)['openapi']['components']['responses']['Error']==doc['components']['responses']['Error']


def test_rendering_does_not_select_status_media_or_body():
    a=loads(rendered(sample(b'one','application/json')).content)['openapi']
    b=loads(rendered(replace(sample(b'two','text/plain'),status=599)).content)['openapi']
    assert a==b


def test_contract_number_serialization_is_lossless():
    ev=sample()
    raw=ev.contract.replace(b'"description":"ok"',b'"description":"ok","x-number":0.12345678901234567890123456789')
    result=rendered(replace(ev,contract=raw))
    assert b'0.12345678901234567890123456789' in result.content


def test_frozen_stage_artifacts_and_schedule_bytes():
    evidence=ROOT/'docs/experiment_evidence'
    recorded=json.loads((evidence/'artifact_verification.json').read_bytes())
    assert recorded['renderer_sha256']==renderer.artifact_hash()
    assert recorded['parser_sha256']==parser.artifact_hash()
    assert recorded['prompt_hashes']==PROMPT_HASHES
    assert recorded['schedule_count']==324 and recorded['non_dispatched'] is True
    assert (evidence/'comparison_schedule_v1.json').read_bytes()==schedule.dry_run_bytes()
    assert digest(schedule.dry_run_bytes())=='a2c797b3d92a1e167515ce3fd1c559a79d2efe0849e0968c0127e499b424c145'
    manifest,files=load_development(ROOT/'artifacts/development_dataset_v1',ROOT/'docs/development_dataset_v1_release.json',RESEARCH)
    for c,record in zip(manifest['cases'],recorded['inputs'],strict=True):
        contract=manifest['sources'][manifest['contracts'][c['api']]]
        ev=renderer.Evidence(files[contract['path']],c['operation']['method'],c['operation']['path'],
                            c['status'],c['content_type'],files[c['body']['path']])
        actual=renderer.render(ev,contract_identity=contract['path'],body_identity=c['body']['path'])
        assert record==dict(case=c['case_id'],**actual.metadata)


def test_eof_after_total_deadline_is_timeout(monkeypatch):
    class Connection(FakeConnection):
        def request(self,*args,**kwargs): pass
        def getresponse(self): return FakeResponse([receipt().raw,b''])
    clock=iter([0,1,2,3,301,302])
    monkeypatch.setattr(provider.time,'monotonic',lambda:next(clock))
    result=provider.OllamaClient(connection_factory=Connection).send(built(),on_start=lambda at:None)
    assert result.transport['error_kind']=='timeout'
    assert result.raw==receipt().raw
    assert provider.classify(result).kind=='TECHNICAL_FAILURE'


def test_content_length_completion_does_not_touch_closed_socket():
    class Socket:
        closed=False
        def settimeout(self,value):
            if self.closed: raise OSError('socket already closed by complete response')
    sock=Socket()
    class Response(FakeResponse):
        def read1(self,n):
            self.length=0
            sock.closed=True
            return receipt().raw
    class Connection(FakeConnection):
        def __init__(self,*a,**k): self.sock=sock
        def request(self,*a,**k): pass
        def getresponse(self): return Response([])
    result=provider.OllamaClient(connection_factory=Connection).send(built(),on_start=lambda at:None)
    assert provider.classify(result).kind=='FINAL'
    assert result.raw==receipt().raw
