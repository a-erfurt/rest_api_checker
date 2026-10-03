"""Explicit additive runtime selection for Main preparation, never permission to infer."""
import json
from pathlib import Path

from . import main_v2_release as release
from .experiment import request, request_v2
from .experiment.encoding import digest
from .persistence.database import require


def selection(path, manifest_sha256, receipt_sha256):
    require(path is not None and manifest_sha256 and receipt_sha256,
            'Explicit runtime qualification path, manifest hash and receipt hash required')
    return dict(path=str(Path(path).resolve()), manifest_sha256=manifest_sha256,
                receipt_sha256=receipt_sha256)


def load(selected, historical, code_identities):
    """Keep the pilot status literal; Main still needs its own contexts and human gates."""
    root = Path(selected['path'])
    raw = (root/'manifest.json').read_bytes()
    require(digest(raw) == selected['manifest_sha256'], 'Runtime qualification manifest hash mismatch')
    manifest, evidence, _ = release.checked_package(root, 'manifest.json')
    require(manifest['format'] == 'main-v2-runtime-requalification-evidence-v1', 'Unsupported runtime qualification scope')
    receipt_raw = evidence['qualification/complete.json']
    require(digest(receipt_raw) == selected['receipt_sha256'], 'Runtime qualification receipt hash mismatch')
    receipt = json.loads(receipt_raw)
    binding_raw = evidence['runtime-binding.json']
    binding = json.loads(binding_raw)
    host = binding['runtime']
    identity = host['runtime_identity']
    require(identity.startswith('evaluation_v2_') and identity != historical['runtime']['runtime_identity']
            and host['format'] == 'evaluation-v2-runtime-identity-v1', 'Separate qualified runtime identity required')
    require(receipt['format'] == 'evaluation-v2-runtime-qualification-v1'
            and receipt['status'] == 'PASS_FOR_BOUNDED_INTERFACE_PILOT'
            and receipt['runtime_identity'] == identity
            and receipt['runtime_binding_sha256'] == digest(binding_raw), 'Unapproved runtime qualification')
    require(receipt['qualification_generation_calls'] == 0 and receipt['exact_context_proofs'] == 18
            and receipt['generation_settings'] == request.OPTIONS and receipt['seed'] == request.SEEDS[1],
            'Incomplete no-generation qualification or generation configuration drift')
    require(receipt['context_measurement_sha256'] == digest(evidence['context/measurement.json'])
            and receipt['context_proofs_sha256'] == digest(evidence['context-proofs.json']), 'Qualification context drift')
    qualified_plan = json.loads(evidence['prepared/manifest.json'])
    require(all(qualified_plan[k] == v for k, v in code_identities.items()), 'Qualified scientific implementation drift')
    proofs = json.loads(evidence['context-proofs.json'])
    require(len(qualified_plan['slots']) == len(proofs) == 18, 'Incomplete qualification proof coverage')
    for slot in qualified_plan['slots']:
        req = request_v2.RequestV2(evidence['prepared/'+slot['request_path']],
                                  json.loads(evidence['prepared/'+slot['provenance_path']]))
        request_v2.validate_request_v2(req)
        proof = request.ContextProof(**proofs[digest(req.body)])
        proof.verify(req)
        model = next(m for m in binding['models'] if m['name'] == req.metadata['model'])
        require(proof.measurement_sha256 == receipt['context_measurement_sha256']
                and proof.model_digest == model['digest'] and proof.template_sha256 == model['template_sha256'],
                'Qualification request/model/template proof drift')
    handoff = json.loads(evidence['requalification.json'])
    fact = handoff['fact']
    require(manifest['requalification_receipt_sha256'] == digest(evidence['requalification.json'])
            and fact['runtime'] == host and fact['current_runtime_identity'] == identity
            and fact['runtime_binding_sha256'] == digest(binding_raw)
            and fact['qualification_receipt_sha256'] == digest(receipt_raw), 'Requalification identity drift')
    require(fact['previous_runtime_binding_sha256'] == digest(historical['_raw'])
            and fact['qualification_status'] == receipt['status'], 'Historical qualification linkage drift')
    for field in ('architecture', 'os', 'cpu', 'ram_bytes', 'python'):
        require(host[field] == historical['runtime'][field], 'Unexpected qualified host drift: '+field)
    require(host['hardware'].split('      Displays:')[0] == historical['runtime']['hardware'].split('      Displays:')[0],
            'Qualified accelerator drift')
    require(host['ollama']['version'] and host['binaries']
            and json.loads(evidence['qualification/version.json']) == host['ollama'], 'Runtime version evidence drift')
    checks = fact['qualification_checks']
    require(all(checks[k] is True for k in ('freeze_verify_live', 'no_overflow', 'all_18_render_and_token_sequences_match_prior'))
            and checks['completion_calls'] == 0 and checks['native_fabricated_parity_probes'] == 3
            and checks['exact_prior_DEV_request_context_proofs'] == 18
            and checks['output_budget'] == request.OPTIONS['num_predict']
            and checks['context_window'] == request.OPTIONS['num_ctx'], 'Incomplete native qualification')
    parity = json.loads(evidence['qualification/native/probe_summary.json'])
    require([m['model'] for m in parity] == list(request.MODELS)
            and all(m['historical_fabricated_render_equal'] is True and m['historical_fabricated_tokens_equal'] is True
                    and m['qualification_generation_calls'] == 0 for m in parity), 'Native parity qualification missing')
    require([m['name'] for m in binding['models']] == list(request.MODELS), 'Model roster drift')
    native = {}
    for old, model, checked in zip(historical['models'], binding['models'], fact['model_checks'], strict=True):
        for key in ('name', 'digest', 'template_sha256', 'layers'):
            require(old[key] == model[key], 'Qualified model/template/blob drift: '+key)
        require(checked['name'] == model['name'] and checked['digest'] == model['digest']
                and checked['template_sha256'] == model['template_sha256']
                and checked['all_blobs_verified'] is True and checked['parameter_semantics_unchanged'] is True,
                'Expected model blobs or parameters unverified')
        require(model['runtime_identity'] == identity, 'Model/runtime identity drift')
        for key in ('show', 'manifest'):
            name = model[key]
            require(Path(name).parts[0] == identity, 'Separate native namespace required')
            native['native/'+name] = evidence['runtime_namespace/'+name]
        show = json.loads(native['native/'+model['show']])
        model_manifest_raw = native['native/'+model['manifest']]
        model_manifest = json.loads(model_manifest_raw)
        require(digest(show['template'].encode()) == model['template_sha256'], 'Native template drift')
        require(digest(model_manifest_raw) == model['digest']
                and [{k: layer[k] for k in ('digest', 'mediaType', 'size')}
                     for layer in [model_manifest['config'], *model_manifest['layers']]] == model['layers'], 'Model manifest/blob drift')
    # Archive the complete hash-verified qualification, retaining its original bytes.
    sources = {'runtime': binding_raw, 'qualification': receipt_raw, 'qualified_plan': evidence['prepared/manifest.json'],
               'runtime-qualification/manifest.json': raw,
               **{'runtime-qualification/'+n: b for n, b in evidence.items()}, **native}
    return binding, sources
