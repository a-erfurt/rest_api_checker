"""Synthetic isolated faults. No study input, persistence, process kills or network changes."""
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading
import time
from unittest.mock import patch
from capture import save, api
from rest_api_checker.experiment import provider, request, orchestration
from rest_api_checker.experiment.encoding import encode

payload={'model':'qwen3.6:27b','stream':False,'messages':[{'role':'system','content':'FABRICATED RUNTIME DIAGNOSTIC'},{'role':'user','content':'Fabricated test only'}],'options':{**request.OPTIONS,'seed':101},'think':False}
req=request.Request(encode(payload),{})
valid=json.dumps({k:dict(verdict='PASS',reason='fabricated parser fixture') for k in ('c1','c2','c3')})
class Handler(BaseHTTPRequestHandler):
 mode=''
 def log_message(self,*args): pass
 def do_POST(self):
  self.rfile.read(int(self.headers['Content-Length']))
  if self.mode=='timeout': time.sleep(.15)
  status=500 if self.mode=='server' else 200
  data={'error':'FABRICATED isolated runtime failure'} if status==500 else {'done':True,'message':{'role':'assistant','content':valid if self.mode=='valid' else '{'}}
  body=encode(data); self.send_response(status); self.send_header('Content-Length',str(len(body))); self.end_headers()
  try: self.wfile.write(body)
  except (BrokenPipeError,ConnectionResetError): pass

rows=[]
with patch.object(provider,'validate_request',lambda r:None):
 # Reserve a port then close it immediately: connect to a closed loopback port.
 with socket.socket() as unavailable:
  unavailable.bind(('127.0.0.1',0))
  port=unavailable.getsockname()[1]
  unavailable.close()
  receipt=provider.OllamaClient(f'http://127.0.0.1:{port}/api/chat').send(req,on_start=lambda t:None)
  assert receipt.transport['error_kind']=='transport'
  rows.append(('transport',receipt,'real_loopback_transport'))
 for mode in ('timeout','server','parser','valid'):
  Handler.mode=mode
  with ThreadingHTTPServer(('127.0.0.1',0),Handler) as server:
   thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
   try:
    # Bounded synthetic timeout tests the unchanged deadline implementation.
    with patch.object(provider,'TIMEOUT',.05 if mode=='timeout' else request.TIMEOUT):
     receipt=provider.OllamaClient(f'http://127.0.0.1:{server.server_port}/api/chat').send(req,on_start=lambda t:None)
    rows.append((mode,receipt,'isolated_synthetic_http_server'))
   finally: server.shutdown(); thread.join()
results=[]
for name,receipt,scope in rows:
 classified=provider.classify(receipt)
 outcomes=[]
 for attempt in (1,2):
  outcome=orchestration.outcome_for(receipt,run_id=0,attempt_id=0,request_sha256='0'*64,spool_sha256='0'*64,attempt_number=attempt,review_failure=lambda r,p:'isolated')
  outcomes.append(dict(attempt=attempt,result=outcome['result'],retry_eligible=outcome['diagnostics']['retry_eligible']))
 holds={}
 if classified.kind=='TECHNICAL_FAILURE':
  for attribution in ('systematic','ambiguous'):
   try: orchestration.outcome_for(receipt,run_id=0,attempt_id=0,request_sha256='0'*64,spool_sha256='0'*64,attempt_number=1,review_failure=lambda r,p:attribution)
   except orchestration.Paused as e: holds[attribution]=str(e)
 results.append(dict(name=name,evidence_scope=scope,transport=receipt.transport,provider_kind=classified.kind,provider_code=classified.code,outcomes=outcomes,holds=holds))
# Invalid known option is rejected before inference. Preserve real runtime error,
# never call it an isolated crash or grant retry.
import urllib.error
try:
 api('/api/chat',{**payload,'options':{**payload['options'],'top_k':'FABRICATED_INVALID_TYPE'}})
 raise AssertionError('Invalid top_k unexpectedly accepted')
except urllib.error.HTTPError as e:
 raw=e.read(); receipt=provider.Receipt(raw,dict(complete=True,http_status=e.code,error_kind=None),datetime.now().astimezone().isoformat(),datetime.now().astimezone().isoformat())
 result=provider.classify(receipt)
 results.append(dict(name='invalid_option',evidence_scope='actual_ollama_configuration_rejection_no_generation',http_status=e.code,response=json.loads(raw),provider_kind=result.kind,provider_code=result.code,attribution='systematic deliberately invalid configuration; no retry'))
save('failures.json',dict(captured_at=datetime.now().astimezone().isoformat(),scope='FABRICATED_RUNTIME_QUALIFICATION',application_timeout_seconds=300,synthetic_timeout_seconds=.05,sql_writes=0,results=results,limitation='No genuine Ollama crash/OOM induced or observed; their isolated/systematic attribution is not qualified.'))
print([(x['name'],x['provider_code']) for x in results])
