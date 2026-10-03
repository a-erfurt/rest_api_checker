"""Separate native render/tokenize evidence preparation. Never requests generation.

Uses the already qualified Evaluation-v2 render-only path and native tokenizer.
This command is intentionally separate from the offline materializer.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

from . import freeze, main_v2, main_v2_release as release
from .experiment import request, request_v2
from .experiment.encoding import digest, encode
from .persistence.database import require


def request_at(plan, files, slot):
    req = request_v2.RequestV2(files[slot['request_path']], json.loads(files[f"provenance/{slot['run_order']:06}.json"]))
    request_v2.validate_request_v2(req)
    require(digest(req.body) == slot['sha256'] and req.metadata['request_identity_sha256'] == slot['request_identity_sha256'], 'Request inventory drift')
    return req


def http(url, payload):
    with urllib.request.urlopen(urllib.request.Request(url, data=encode(payload),
            headers={'Content-Type': 'application/json'}), timeout=request.TIMEOUT) as response:
        return response.read()


def native_runner(identity):
    blob = next(l['digest'] for l in identity['layers'] if l['mediaType'] == 'application/vnd.ollama.image.model').replace(':', '-')
    lines = subprocess.check_output(['ps', '-axo', 'pid,args'], text=True).splitlines()
    matches = [line.strip() for line in lines if '/llama-server ' in line and '--model ' in line and blob in line]
    require(len(matches) == 1, 'Exact qualified native model runner required')
    match = re.search(r'--port (\d+)', matches[0])
    require(match is not None, 'Native tokenizer port missing')
    return matches[0], 'http://127.0.0.1:'+match[1]+'/tokenize'


def validate_measurement(req, identity, render_request, render_response, token_request, token_response):
    payload = json.loads(req.body)
    require(render_request == {**payload, '_debug_render_only': True, 'truncate': False}, 'Render-only request mismatch')
    require(not render_response.get('done') and not render_response.get('eval_count')
            and not render_response.get('message', {}).get('content')
            and not render_response.get('message', {}).get('thinking'), 'Unexpected generation in context evidence')
    debug = render_response['_debug_info']
    require(not debug.get('image_count'), 'Unexpected image context')
    rendered = debug['rendered_template']
    require(type(rendered) is str and all(m['content'].strip() in rendered for m in payload['messages']), 'Truncated native context')
    require(token_request == dict(content=rendered, add_special=True, parse_special=True), 'Native tokenizer request mismatch')
    tokens = token_response['tokens']
    require(type(tokens) is list and tokens and all(type(t) is int for t in tokens), 'Native token evidence missing')
    require(identity['digest'] == req.metadata['model_digest'], 'Native model identity drift')
    return len(tokens)


def measure(final, prepared, output, *, root, research, confirm=False, transport=http,
            runner=native_runner, live_check=freeze.verify_live):
    require(confirm is True, 'Explicit native render/tokenize-only confirmation required')
    plan, files, plan_raw = main_v2.load_prepared(final, prepared)
    output = Path(output)
    require(not output.resolve().is_relative_to(Path(research).resolve()) and not output.exists(), 'Separate new context output directory required')
    main_v2.restore_native(files, root)
    binding = json.loads(files['authority/runtime'])
    require(live_check(binding, Path(root)) is True, 'Qualified live runtime drift')
    output.mkdir(parents=True)
    evidence, measured = {}, []
    def save(name, raw):
        evidence[name] = raw
        target = release.safe_path(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    # Native preparation can avoid repeated model reloads; persisted execution
    # order remains the reviewed case/model/repetition sequence.
    slots = sorted(plan['slots'], key=lambda s: (request.MODELS.index(s['model']), s['run_order']))
    for step, slot in enumerate(slots, 1):
        req = request_at(plan, files, slot)
        identity = next(m for m in binding['models'] if m['name'] == slot['model'])
        require(live_check(binding, Path(root)) is True, 'Runtime changed before native context measurement')
        prefix = f"native/{slot['run_order']:06}"
        render_request = {**json.loads(req.body), '_debug_render_only': True, 'truncate': False}
        save(prefix+'-render-request.json', encode(render_request))
        raw = transport('http://127.0.0.1:11434/api/chat', render_request)
        save(prefix+'-render-response.json', raw)
        rendered = json.loads(raw)
        require(not rendered.get('done') and not rendered.get('eval_count')
                and not rendered.get('message', {}).get('content') and not rendered.get('message', {}).get('thinking'), 'Unexpected generation')
        command, url = runner(identity)
        token_request = dict(content=rendered['_debug_info']['rendered_template'], add_special=True, parse_special=True)
        save(prefix+'-token-request.json', encode(token_request))
        token_raw = transport(url, token_request)
        save(prefix+'-token-response.json', token_raw)
        count = validate_measurement(req, identity, render_request, rendered, token_request, json.loads(token_raw))
        proof = request.ContextProof(digest(req.body), identity['digest'], identity['template_sha256'], digest(token_raw), count)
        proof.verify(req)
        measured.append(dict(run_order=slot['run_order'], request_sha256=digest(req.body), model_digest=identity['digest'],
            template_sha256=identity['template_sha256'], input_tokens=count, prefix=prefix, runner_command=command))
        print(f"Native context {step}/{plan['planned']} (run {slot['run_order']}): {count} input tokens; generation calls: 0", file=sys.stderr, flush=True)
    require(live_check(binding, Path(root)) is True, 'Runtime changed during context measurement')
    sealed = release.seal(evidence, 'manifest.json', format='main-v2-native-context-v1',
        prepared_plan_sha256=digest(plan_raw), runtime_binding_sha256=digest(files['authority/runtime']),
        method='Qualified Evaluation-v2 native render-only and llama-server tokenize; add_special=true parse_special=true',
        measurement_code_sha256=digest(Path(__file__).read_bytes()),
        generation_calls=0, rows=sorted(measured, key=lambda r: r['run_order']))
    for name in ('manifest.json', 'manifest.sha256'):
        with (output/name).open('xb') as stream:
            stream.write(sealed[name])
    verify_context(plan, files, plan_raw, output)


def verify_context(plan, files, plan_raw, directory):
    manifest, evidence, raw = release.checked_package(directory, 'manifest.json')
    require(manifest.get('format') == 'main-v2-native-context-v1' and manifest.get('generation_calls') == 0
            and manifest.get('measurement_code_sha256') == digest(Path(__file__).read_bytes())
            and manifest['prepared_plan_sha256'] == digest(plan_raw)
            and manifest['runtime_binding_sha256'] == digest(files['authority/runtime']), 'Context/runtime/plan identity mismatch')
    require([r['run_order'] for r in manifest['rows']] == [s['run_order'] for s in plan['slots']], 'Incomplete context proof coverage')
    identities = json.loads(files['authority/runtime'])['models']
    proofs = {}
    for row, slot in zip(manifest['rows'], plan['slots'], strict=True):
        req = request_at(plan, files, slot)
        identity = next(m for m in identities if m['name'] == slot['model'])
        prefix = row['prefix']
        values = [json.loads(evidence[prefix+'-'+suffix+'.json']) for suffix in
                  ('render-request', 'render-response', 'token-request', 'token-response')]
        count = validate_measurement(req, identity, *values)
        require(row['input_tokens'] == count and row['request_sha256'] == digest(req.body)
                and row['model_digest'] == identity['digest'] and row['template_sha256'] == identity['template_sha256'], 'Native context evidence drift')
        proof = request.ContextProof(digest(req.body), identity['digest'], identity['template_sha256'], digest(raw), count)
        proof.verify(req)
        proofs[str(slot['run_order'])] = asdict(proof)
    return proofs, evidence, raw


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--release', type=Path, required=True)
    cli.add_argument('--prepared', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    cli.add_argument('--root', type=Path, default=main_v2.ROOT)
    cli.add_argument('--research', type=Path, default=main_v2.RESEARCH)
    cli.add_argument('--confirm-native-render-tokenize-only', action='store_true')
    args = cli.parse_args(argv)
    measure(release.load_release(args.release), args.prepared, args.output, root=args.root, research=args.research,
            confirm=args.confirm_native_render_tokenize_only)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
