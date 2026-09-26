"""Fabricated runtime probes only. Never imports released inputs or persists predictions."""
from datetime import datetime
import json
import subprocess
import sys
from unittest.mock import patch
import urllib.request
from capture import OUT, api, save, digest
from rest_api_checker.experiment import provider, request
from rest_api_checker.experiment.encoding import encode

model=sys.argv[1]
assert model in request.MODELS
short=dict(zip(request.MODELS,('qwen','gemma','mistral')))[model]
seed=int(sys.argv[2]) if len(sys.argv)>2 else 101
assert seed in request.SEEDS.values()
if seed!=101: short += '_seed'+str(seed)
payload={'model':model,'stream':False,'messages':[{'role':'system','content':'DIAGNOSTIC RUNTIME QUALIFICATION. Fabricated non-study content. Reply with the word READY only.'},{'role':'user','content':'Fabricated diagnostic: purple teapot 7301.'}],'options':{**request.OPTIONS,'seed':101}}
if model==request.MODELS[0]: payload['think']=False
payload['options']['seed']=seed
save(short+'_diagnostic_request.json',payload)
# Explicit test seam admits fabricated messages; the production guard is unchanged.
# The same real send()/deadline/HTTP path is exercised, with no repository or SQL calls.
with patch.object(provider,'validate_request',lambda r: None):
    receipt=provider.OllamaClient().send(request.Request(encode(payload),{}),on_start=lambda t:None)
result=provider.classify(receipt)
envelope=json.loads(receipt.raw) if receipt.raw else {}
message=envelope.pop('message',{})
# Do not display, score or retain semantic generated text.
summary=dict(captured_at=datetime.now().astimezone().isoformat(),scope='FABRICATED_RUNTIME_DIAGNOSTIC',transport=receipt.transport,classification=dict(kind=result.kind,code=result.code),envelope=envelope,content_bytes=len(message.get('content','').encode()),content_sha256=digest(message.get('content','').encode()),thinking_present='thinking' in message,thinking_bytes=len(message.get('thinking','').encode()),response_sha256=digest(receipt.raw or b''),request_sha256=digest(encode(payload)),timeout_seconds=request.TIMEOUT)
save(short+'_diagnostic_result.json',summary)
# Render-only path is checked on fabricated content before any possible study use.
rendered=api('/api/chat',{**payload,'_debug_render_only':True,'truncate':False})
save(short+'_diagnostic_render.json',rendered)
save(short+'_ps.json',api('/api/ps'))
processes=subprocess.check_output(['ps','-axo','pid,args'],text=True)
runners=[line.strip() for line in processes.splitlines() if '/llama-server ' in line and '--port' in line]
save(short+'_runner.json',runners)
print(short,summary['classification'],summary['transport']['http_status'], 'render keys',list(rendered),flush=True)
