"""Offline validation of captured Gate-B evidence, never authority to dispatch.

A capture is scoped to its recorded host/time and bound source bytes. The dispatch
callback must still reverify live runtime identity; author acceptance is separate.
"""
import json
from pathlib import Path
import struct
import subprocess

from .experiment.encoding import digest, encode
from .experiment.request import MODELS, OPTIONS, SEEDS, TIMEOUT
from .persistence.database import require

DIRECTORY = 'docs/runtime_qualification_2026-09-26'


def source_bytes(root, relative, implementation_commit=None):
    """Optional historical code lookup; captured evidence stays on disk."""
    if implementation_commit is not None and relative.startswith(('src/','tests/','tools/')):
        return subprocess.check_output(['git','-C',str(root),'show',implementation_commit+':'+relative])
    return (root/relative).read_bytes()


def inspect(root, research, *, implementation_commit=None):
    folder = root / DIRECTORY
    if not (folder/'bundle.json').exists():
        return {}
    bundle = json.loads((folder/'bundle.json').read_bytes())
    require(bundle['format'] == 'gate-b-runtime-evidence-v1', 'Runtime evidence format')
    require(bundle['author_acceptance'] is False, 'Runtime capture cannot approve Gate B')
    require({'implementation:src/rest_api_checker/experiment/'+name+'.py'
             for name in ('request','provider','renderer','parser','schedule')} <= set(bundle['sources']),
            'Missing implementation source bindings')
    require('research:03_research_design/prompt_development_protocol_v1.md' in bundle['sources'],
            'Missing protocol binding')
    for name, sha in bundle['files'].items():
        require(Path(name).name == name, 'Unsafe evidence path')
        require(digest((folder/name).read_bytes()) == sha, 'Runtime evidence drift: '+name)
    for name, sha in bundle['sources'].items():
        base, relative = name.split(':', 1)
        require(base in ('implementation','research') and not Path(relative).is_absolute()
                and '..' not in Path(relative).parts, 'Unsafe source binding')
        raw = source_bytes(root,relative,implementation_commit) if base=='implementation' else (research/relative).read_bytes()
        require(digest(raw) == sha, 'Runtime source drift: '+name)
    def read(name):
        require(name in bundle['files'], 'Unbound runtime evidence: '+name)
        return json.loads((folder/name).read_bytes())
    identities = read('identities.json')
    tags = read('tags.json')['models']
    host = read('host.json')
    require([i['name'] for i in identities] == list(MODELS), 'Runtime model roster')
    require(host['ollama']['version'] and host['architecture'] and host['cpu']
            and host['ram_bytes'] > 0 and host['hardware'] and host['binaries'], 'Host identity incomplete')
    for identity in identities:
        manifest = read(identity['manifest'])
        require(digest((folder/identity['manifest']).read_bytes()) == identity['digest'], 'Manifest identity')
        tag = next((t for t in tags if t['name'] == identity['name']), {})
        require(tag.get('digest') == identity['digest'], 'Tag identity')
        expected = [manifest['config']]+manifest['layers']
        require(identity['layers'] == [{k:layer[k] for k in ('digest','size','mediaType')}
                                     for layer in expected], 'Measured blob identity/size mismatch')
        show = read(identity['show'])
        info = show['model_info']
        arch = info['general.architecture']
        require(show['details']['quantization_level'] == 'Q4_K_M'
                and info['general.file_type'] == 15, 'Measured quantization mismatch')
        require(info['general.parameter_count'] > 0 and info[arch+'.context_length'] >= OPTIONS['num_ctx'],
                'Model capability missing')
        require(digest(show['template'].encode()) == identity['template_sha256'], 'Native template identity')
    result = {'Full model identities': dict(status='PASS', detail=f'Captured {host["captured_at"]}: full manifests/blobs, Q4_K_M, host and Ollama {host["ollama"]["version"]}; snapshot, not live dispatch approval')}
    for identity, short in zip(identities, ('qwen','gemma','mistral')):
        diagnostic = read(short+'_diagnostic_request.json')
        response = read(short+'_diagnostic_result.json')
        slots = read(short+'_slots.json')
        props = read(short+'_props.json')
        model_blob = next(layer['digest'] for layer in identity['layers']
                          if layer['mediaType']=='application/vnd.ollama.image.model')
        require(Path(props['model_path']).name == model_blob.replace(':','-'), 'Runner model binding')
        require(len(slots) == 1, 'Ambiguous diagnostic runner slot')
        slot, params = slots[0], slots[0]['params']
        require(diagnostic['options'] == {**OPTIONS, 'seed':101}, 'Diagnostic requested options')
        require(diagnostic['model'] == identity['name'] and diagnostic['stream'] is False,
                'Diagnostic request boundary')
        require([m['role'] for m in diagnostic['messages']] == ['system','user']
                and set(diagnostic) == ({'model','stream','messages','options','think'} if short=='qwen'
                                       else {'model','stream','messages','options'}), 'Diagnostic message boundary')
        require((diagnostic.get('think') is False) if short=='qwen' else 'think' not in diagnostic,
                'Thinking policy')
        require(response['transport']['complete'] and response['transport']['http_status'] == 200
                and response['timeout_seconds'] == TIMEOUT and response['thinking_bytes'] == 0,
                'Runtime diagnostic completion/thinking')
        require(response['request_sha256'] == digest(encode(diagnostic)), 'Diagnostic request digest')
        for key in ('temperature','top_p','top_k','min_p','repeat_penalty','repeat_last_n'):
            # Runner exposes float32 values; do not pretend their decimals are exact.
            effective = struct.unpack('f', struct.pack('f', OPTIONS[key]))[0]
            require(params[key] == effective,
                    'Effective option mismatch: '+key)
        require(params['seed'] == 101 and params['n_predict'] == OPTIONS['num_predict']
                and slot['n_ctx'] == OPTIONS['num_ctx'] and slot['speculative'] is False
                and params['speculative.types'] == 'none', 'Effective seed/context/output/draft mismatch')
        rendered = read(short+'_diagnostic_render.json')['_debug_info']['rendered_template']
        require(all(m['content'] in rendered for m in diagnostic['messages']), 'Native rendering lost message content')
        parity = read(short+'_token_parity.json')
        require(next(p for p in parity if p['add_special'])['count'] == response['envelope']['prompt_eval_count'],
                'Native tokenizer/BOS parity mismatch')
        for seed in (202,303):
            seeded = read(short+'_seed'+str(seed)+'_diagnostic_request.json')
            observed = read(short+'_seed'+str(seed)+'_slots.json')
            completed = read(short+'_seed'+str(seed)+'_diagnostic_result.json')
            require(seeded == {**diagnostic, 'options':{**OPTIONS,'seed':seed}}
                    and len(observed)==1 and observed[0]['params']['seed']==seed
                    and completed['transport']['http_status']==200
                    and completed['transport']['complete'], 'Effective repetition seed mismatch')
            for option in ('temperature','top_p','top_k','min_p','repeat_penalty','repeat_last_n','n_predict'):
                require(observed[0]['params'][option] == params[option], 'Seeded effective option mismatch')
            require(read(short+'_seed'+str(seed)+'_diagnostic_render.json')['_debug_info']['rendered_template']
                    == rendered, 'Seed altered native rendering')
    result['Template and effective options'] = dict(status='PASS', detail='Native rendered diagnostics and runner slots verify D07 and seeds 101/202/303; float32 values retained; outer stream=false, internal stream=true; thinking false/omitted')
    inventory = read('request_inventory.json')
    context = read('context.json')
    require(inventory['dispatched'] is False and context['study_generation_calls'] == 0,
            'Context evidence crossed generation boundary')
    rows = context['rows']
    expected = {(m, p, f'DEV-{c:02}', r) for m in MODELS for p in ('P1','P2','P3')
                for c in range(1,13) for r in SEEDS}
    key = lambda row: (row['model'],row['prompt'],row['case'],row['repetition'])
    require(len(rows)==324 and {key(r) for r in rows}==expected, 'Incomplete context coverage')
    require(len(inventory['requests'])==324 and {key(r) for r in inventory['requests']}==expected,
            'Incomplete request inventory')
    requests = {key(r):r for r in inventory['requests']}
    for row in rows:
        identity = next(i for i in identities if i['name']==row['model'])
        require(row['request_sha256'] == requests[key(row)]['request_sha256']
                and row['model_digest']==identity['digest']
                and row['template_sha256']==identity['template_sha256'], 'Context request/model/template binding')
        require(type(row['input_tokens']) is int and row['input_tokens']>0, 'Missing actual token count')
        require(row['total_tokens']==row['input_tokens']+OPTIONS['num_predict']
                and row['margin']==OPTIONS['num_ctx']-row['total_tokens'] and row['margin']>=0,
                'Context overflow or arithmetic mismatch')
    result['Context fit'] = dict(status='PASS', detail='108 native render/tokenize-only measurements cover all 324 requests; maximum '+str(max(r['total_tokens'] for r in rows))+' tokens including output; no study generation')
    failures = read('failures.json')
    result['Failure attribution'] = dict(status='BLOCKED', detail=failures['limitation']+' Transport, bounded timeout, synthetic HTTP/parser outcomes and actual configuration rejection captured; retry/denominator verified by SQL tests.')
    return result
