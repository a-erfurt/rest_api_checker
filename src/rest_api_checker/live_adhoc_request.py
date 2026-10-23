"""Approved prompt variants for isolated, non-scientific interactive runs.

The scientific v1/v2 builders and their artifact hashes stay unchanged. Reuse
the approved v1 prompt construction and add only the existing JSON transport.
"""
from dataclasses import dataclass
from pathlib import Path

from .experiment import parser, renderer
from .experiment.encoding import Blocked, check, digest, encode, loads
from .experiment.request import SEEDS, TIMEOUT, build_request
from .persistence.database import require

VERSION = 'live-adhoc-output-interface-v1'
REQUEST_VERSION = 'live-adhoc-ollama-chat-request-v1'
RENDERED_FIELDS = (
    'renderer_version', 'renderer_sha256', 'contract_identity', 'contract_sha256',
    'body_identity', 'body_sha256', 'responses_pointer', 'reference_closure_paths',
    'rendered_evidence_sha256',
)


def artifact_hash():
    root = Path(__file__).parent
    names = ('live_adhoc_request.py', 'experiment/request.py', 'experiment/encoding.py')
    return digest(b''.join(name.encode() + b'\0' + (root/name).read_bytes() + b'\0' for name in names))


def output_interface():
    return dict(version=VERSION, mode='format_json')


@dataclass(frozen=True, slots=True)
class AdhocRequest:
    body: bytes
    metadata: dict
    timeout: int = TIMEOUT


def build_request_adhoc(rendered, *, prompt_name, prompt, model, model_digest, repetition):
    base = build_request(rendered, prompt_name=prompt_name, prompt=prompt, model=model,
                         model_digest=model_digest, repetition=repetition)
    body = encode({**loads(base.body), 'format': 'json'})
    identity = dict(request_version=REQUEST_VERSION,
        output_interface_sha256=digest(encode(output_interface())),
        rendered_metadata_sha256=digest(encode({key: rendered.metadata[key] for key in RENDERED_FIELDS})),
        rendered_request_sha256=digest(body), model_digest=model_digest)
    return AdhocRequest(body, {**base.metadata, **identity,
        'output_interface_version': VERSION, 'output_interface_mode': 'format_json',
        'request_identity_sha256': digest(encode(identity)), 'request_builder_sha256': artifact_hash()})


def validate_request_adhoc(request):
    """Rebuild every payload field and derived sidecar field before dispatch."""
    check(type(request) is AdhocRequest and request.timeout == TIMEOUT,
          'ADHOC_REQUEST_OR_TIMEOUT_CHANGED')
    try:
        metadata = request.metadata
        system, user = loads(request.body)['messages']
        content = user['content'].encode('utf-8')
        check(digest(content) == metadata['rendered_evidence_sha256'], 'EVIDENCE_HASH_CHANGED')
        check(metadata['renderer_version'] == renderer.VERSION
              and metadata['renderer_sha256'] == renderer.artifact_hash(), 'ADHOC_RENDERER_CHANGED')
        evidence_metadata = {key: metadata[key] for key in RENDERED_FIELDS}
        rebuilt = build_request_adhoc(renderer.Rendered(content, evidence_metadata),
            prompt_name=metadata['prompt_name'], prompt=system['content'].encode('utf-8'),
            model=metadata['model'], model_digest=metadata['model_digest'], repetition=metadata['repetition'])
        check(request.body == rebuilt.body and metadata == rebuilt.metadata, 'ADHOC_REQUEST_BINDING_CHANGED')
    except (KeyError, TypeError, ValueError, UnicodeError, AttributeError) as exc:
        raise Blocked('ADHOC_REQUEST_VALIDATION_FAILED') from exc


def prepare(repo, run_id):
    """Read the persisted prompt selection inside a newly scoped ad-hoc run."""
    from .live_adhoc_runtime import require_scope

    inputs = repo.execution_inputs(run_id)
    setup, run = inputs['setup'], inputs['run']
    require_scope(setup, run['experiment_id'], run['dataset_id'])
    require(setup['parser_sha256'] == parser.artifact_hash(), 'Parser artifact drift')
    require(setup['renderer_sha256'] == renderer.artifact_hash(), 'Renderer artifact drift')
    require(setup['request_builder_sha256'] == artifact_hash(), 'Ad-hoc request builder drift')
    require(setup['output_interface'] == output_interface(), 'Ad-hoc output interface drift')
    require(run['seed'] == SEEDS.get(run['repetition']), 'Run seed drift')
    require(setup['prompt_selection'] == dict(prompt_id=run['prompt_id'],
            name=inputs['prompt_name'], sha256=digest(inputs['prompt'])), 'Ad-hoc prompt selection drift')
    rendered = renderer.render(inputs['evidence'], contract_identity=inputs['contract_identity'],
                               body_identity=inputs['body_identity'])
    req = build_request_adhoc(rendered, prompt_name=inputs['prompt_name'], prompt=inputs['prompt'],
        model=inputs['model']['name'], model_digest=inputs['model']['digest'], repetition=run['repetition'])
    validate_request_adhoc(req)
    return inputs, req
