"""Fabricated additive runtime envelopes; archived scientific requests stay exact."""
from copy import deepcopy
import json

import pytest

from rest_api_checker import main_v2 as main, main_v2_runtime as runtime, main_v2_release as release, main_v2_context as context
from rest_api_checker.experiment import request
from rest_api_checker.experiment.encoding import digest, encode
from persistence.main_v2_helpers import RESEARCH, make_release, prepared_context


def qualification(tmp_path, final):
    _, old, _, sources = main.authorities(final)
    pilot = RESEARCH/'08_evaluation_v2/output_interface_pilot_v2'
    # All modifications and acceptance claims below are FABRICATED test input.
    binding = deepcopy(old)
    identity = 'evaluation_v2_FABRICATED_0351'
    binding['runtime'].update(runtime_identity=identity, ollama={'version': '0.35.1'})
    evidence = {}
    for model in binding['models']:
        model['runtime_identity'] = identity
        for key in ('show', 'manifest'):
            previous = model[key]
            model[key] = identity+'/'+previous.split('/')[-1]
            evidence['runtime_namespace/'+model[key]] = sources['native/'+previous]
    for folder in ('prepared', 'context'):
        for p in (pilot/folder).rglob('*'):
            if p.is_file(): evidence[str(p.relative_to(pilot))] = p.read_bytes()
    evidence['context-proofs.json'] = (pilot/'context-proofs.json').read_bytes()
    evidence['runtime-binding.json'] = encode(binding)
    receipt = json.loads(sources['qualification'])
    receipt.update(runtime_identity=identity, runtime_binding_sha256=digest(evidence['runtime-binding.json']))
    evidence['qualification/complete.json'] = encode(receipt)
    evidence['qualification/version.json'] = encode(binding['runtime']['ollama'])
    evidence['qualification/native/probe_summary.json'] = encode([dict(model=m, historical_fabricated_render_equal=True,
        historical_fabricated_tokens_equal=True, qualification_generation_calls=0) for m in request.MODELS])
    fact = dict(runtime=binding['runtime'], current_runtime_identity=identity,
        runtime_binding_sha256=digest(evidence['runtime-binding.json']), qualification_receipt_sha256=digest(evidence['qualification/complete.json']),
        previous_runtime_binding_sha256=digest(sources['runtime']), qualification_status=receipt['status'],
        qualification_checks=dict(freeze_verify_live=True, no_overflow=True, all_18_render_and_token_sequences_match_prior=True,
            completion_calls=0, native_fabricated_parity_probes=3, exact_prior_DEV_request_context_proofs=18,
            output_budget=512, context_window=32768),
        model_checks=[dict(name=m['name'], digest=m['digest'], template_sha256=m['template_sha256'],
                           all_blobs_verified=True, parameter_semantics_unchanged=True) for m in binding['models']])
    evidence['requalification.json'] = encode(dict(fact=fact, fabricated=True))
    return evidence


def publish(tmp_path, evidence):
    directory = tmp_path/'FABRICATED-qualification'
    files = release.seal(evidence, 'manifest.json', format='main-v2-runtime-requalification-evidence-v1',
        requalification_receipt_sha256=digest(evidence['requalification.json']))
    release.publish(directory, files, research=RESEARCH)
    return runtime.selection(directory, digest(files['manifest.json']), digest(evidence['qualification/complete.json']))


def test_explicit_0351_preserves_historical_0350_and_all_exact_requests(tmp_path):
    final = make_release(tmp_path)
    old = main.request_files(final)
    selected = publish(tmp_path, qualification(tmp_path, final))
    new = main.request_files(final, selected)
    assert json.loads(old['authority/runtime'])['runtime']['ollama']['version'] == '0.35.0'
    assert json.loads(new['authority/runtime'])['runtime']['ollama']['version'] == '0.35.1'
    assert all(new[n] == b for n, b in old.items() if n.startswith(('requests/', 'provenance/')))
    assert main.request_files(final) == old  # Explicit historic default, never latest.
    prepared = tmp_path/'new-prepared'
    release.publish(prepared, new, research=RESEARCH)
    assert main.load_prepared(final, prepared)[2] == new['plan.json']


@pytest.mark.parametrize('change', ['manifest', 'receipt', 'missing', 'digest', 'template', 'status', 'blobs', 'parity', 'proof'])
def test_runtime_qualification_fail_closed(tmp_path, change):
    final = make_release(tmp_path)
    evidence = qualification(tmp_path, final)
    if change in ('digest', 'template'):
        obj = json.loads(evidence['runtime-binding.json'])
        obj['models'][0]['digest' if change == 'digest' else 'template_sha256'] = '0'*64
        evidence['runtime-binding.json'] = encode(obj)
        receipt = json.loads(evidence['qualification/complete.json'])
        receipt['runtime_binding_sha256'] = digest(evidence['runtime-binding.json'])
        evidence['qualification/complete.json'] = encode(receipt)
        handoff = json.loads(evidence['requalification.json'])
        handoff['fact'].update(runtime_binding_sha256=digest(evidence['runtime-binding.json']),
                               qualification_receipt_sha256=digest(evidence['qualification/complete.json']))
        evidence['requalification.json'] = encode(handoff)
    elif change == 'status':
        obj = json.loads(evidence['qualification/complete.json']); obj['status'] = 'PASS'
        evidence['qualification/complete.json'] = encode(obj)
    elif change == 'blobs':
        obj = json.loads(evidence['requalification.json']); obj['fact']['model_checks'][0]['all_blobs_verified'] = False
        evidence['requalification.json'] = encode(obj)
    elif change == 'parity':
        evidence['qualification/native/probe_summary.json'] = b'[]'
    elif change == 'proof':
        evidence['context-proofs.json'] = b'{}'
    selected = publish(tmp_path, evidence)
    if change == 'manifest': selected['manifest_sha256'] = '0'*64
    if change == 'receipt': selected['receipt_sha256'] = '0'*64
    if change == 'missing': selected['path'] += '-absent'
    with pytest.raises((ValueError, FileNotFoundError)):
        main.request_files(final, selected)


def test_new_runtime_cannot_reuse_historical_main_context_proofs(tmp_path):
    final, prepared, directory, _ = prepared_context(tmp_path)
    selected = publish(tmp_path, qualification(tmp_path, final))
    rebound = tmp_path/'rebound'
    release.publish(rebound, main.request_files(final, selected), research=RESEARCH)
    plan, files, raw = main.load_prepared(final, rebound)
    with pytest.raises(ValueError, match='Context/runtime/plan identity mismatch'):
        context.verify_context(plan, files, raw, directory)


@pytest.mark.parametrize('args', [(None, 'a'*64, 'b'*64), ('explicit', None, 'b'*64), ('explicit', 'a'*64, None)])
def test_no_implicit_runtime_selection(args):
    with pytest.raises(ValueError, match='Explicit runtime qualification'):
        runtime.selection(*args)
