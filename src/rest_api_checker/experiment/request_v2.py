"""Explicit P2 output-interface comparison; independent of historical v1 dispatch."""
from dataclasses import dataclass
from pathlib import Path
import re

from ..persistence.importer import PROMPT_HASHES
from .encoding import Blocked, check, digest, encode, loads
from .renderer import Rendered
from .request import MODELS, OPTIONS, SEEDS, TIMEOUT

VERSION = 'output-interface-v2'
REQUEST_VERSION = 'ollama-chat-request-v2'
MODES = ('prompt_only', 'format_json', 'json_schema')
SCHEMA_PATH = Path(__file__).with_name('output_transport_schema_v2.json')


def transport_schema():
    """Structure only: no reference labels or cross-category dependencies."""
    return loads(SCHEMA_PATH.read_bytes())


def artifact_hash():
    root = Path(__file__).parent
    names = ('request_v2.py', SCHEMA_PATH.name, 'request.py', 'encoding.py')
    return digest(b''.join(n.encode() + b'\0' + (root/n).read_bytes() + b'\0' for n in names))


@dataclass(frozen=True, slots=True)
class OutputInterfaceV2:
    mode: str  # Required; an existing v1 configuration is never implicitly upgraded.
    version: str = VERSION

    def __post_init__(self):
        check(type(self.mode) is str and self.mode in MODES, 'V2_OUTPUT_INTERFACE_MODE_REQUIRED')
        check(self.version == VERSION, 'V2_OUTPUT_INTERFACE_VERSION_REQUIRED')

    def binding(self):
        return dict(version=self.version, mode=self.mode,
                    transport_schema_sha256=digest(SCHEMA_PATH.read_bytes())
                    if self.mode == 'json_schema' else None)


@dataclass(frozen=True, slots=True)
class RequestV2:
    body: bytes
    metadata: dict  # Persisted sidecar only; never sent as model input.
    timeout: int = TIMEOUT


def build_request_v2(rendered: Rendered, *, interface: OutputInterfaceV2,
                     prompt: bytes, model, model_digest, repetition) -> RequestV2:
    check(type(interface) is OutputInterfaceV2, 'EXPLICIT_V2_INTERFACE_REQUIRED')
    check(type(rendered) is Rendered, 'RENDERED_EVIDENCE_REQUIRED')
    check(digest(prompt) == PROMPT_HASHES['P2'], 'APPROVED_P2_HASH_MISMATCH')
    check(model in MODELS, 'UNAPPROVED_MODEL')
    check(type(repetition) is int and repetition in SEEDS, 'UNAPPROVED_REPETITION')
    check(type(model_digest) is str and re.fullmatch(r'(sha256:)?[0-9a-f]{64}', model_digest),
          'FULL_MODEL_DIGEST_REQUIRED')
    value = {'model': model, 'stream': False,
             'messages': [{'role': 'system', 'content': prompt.decode('utf-8')},
                          {'role': 'user', 'content': rendered.content.decode('utf-8')}],
             'options': {**OPTIONS, 'seed': SEEDS[repetition]}}
    if model == MODELS[0]:
        value['think'] = False
    if interface.mode == 'format_json':
        value['format'] = 'json'
    elif interface.mode == 'json_schema':
        value['format'] = transport_schema()
    body = encode(value)
    binding = interface.binding()
    interface_hash = digest(encode(binding))
    body_hash = digest(body)
    identity = dict(request_version=REQUEST_VERSION, output_interface_sha256=interface_hash,
                    rendered_request_sha256=body_hash, model_digest=model_digest)
    return RequestV2(body, {**rendered.metadata, **identity,
        'output_interface_version': VERSION, 'output_interface_mode': interface.mode,
        'transport_schema_sha256': binding['transport_schema_sha256'],
        'request_identity_sha256': digest(encode(identity)), 'request_builder_sha256': artifact_hash(),
        'prompt_name': 'P2', 'prompt_sha256': digest(prompt), 'model': model,
        'repetition': repetition, 'seed': SEEDS[repetition], 'timeout_seconds': TIMEOUT})


def validate_request_v2(request):
    """Reconstruct bytes and v2 identity before HTTP; never accept a v1 DTO."""
    check(type(request) is RequestV2 and request.timeout == TIMEOUT, 'V2_REQUEST_OR_TIMEOUT_CHANGED')
    try:
        metadata = request.metadata
        check(metadata['request_version'] == REQUEST_VERSION, 'V2_REQUEST_VERSION_CHANGED')
        interface = OutputInterfaceV2(metadata['output_interface_mode'], metadata['output_interface_version'])
        payload = loads(request.body)
        system, user = payload['messages']
        content = user['content'].encode('utf-8')
        check(digest(content) == metadata['rendered_evidence_sha256'], 'EVIDENCE_HASH_CHANGED')
        rebuilt = build_request_v2(Rendered(content, metadata), interface=interface,
            prompt=system['content'].encode('utf-8'), model=metadata['model'],
            model_digest=metadata['model_digest'], repetition=metadata['repetition'])
        check(request.body == rebuilt.body and metadata == rebuilt.metadata, 'V2_REQUEST_BINDING_CHANGED')
    except (KeyError, TypeError, ValueError, UnicodeError, AttributeError) as exc:
        raise Blocked('V2_REQUEST_VALIDATION_FAILED') from exc
