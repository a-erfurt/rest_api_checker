"""D01 allowlist renderer. No reference results, domain objects or body parsing."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import unquote

from ..persistence.database import pointer
from ..schema_validation import prepare_validator
from ..models import OracleNotReady
from .encoding import Blocked, check, digest, encode, loads

VERSION = 'operation-evidence-v1'


def artifact_hash():
    root = Path(__file__).parent
    paths = ('renderer.py', 'encoding.py', '../schema_validation.py', '../persistence/database.py')
    return digest(b''.join(name.encode() + b'\0' + (root/name).read_bytes() + b'\0' for name in paths))


@dataclass(frozen=True, slots=True)
class Evidence:
    contract: bytes
    method: str
    path: str
    status: int
    content_type: str | None
    body: bytes


@dataclass(frozen=True, slots=True)
class Rendered:
    content: bytes
    metadata: dict  # Sidecar only; never part of content or a model message.


def escape(key):
    return key.replace('~', '~0').replace('/', '~1')


def render(evidence: Evidence, *, contract_identity: str, body_identity: str) -> Rendered:
    check(type(evidence) is Evidence, 'ALLOWLIST_DTO_REQUIRED')
    check(type(evidence.contract) is bytes and type(evidence.body) is bytes, 'EXACT_BYTES_REQUIRED')
    check(evidence.method in ('get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace'),
          'INVALID_OPERATION_METHOD')
    check(type(evidence.path) is str and evidence.path.startswith('/'), 'INVALID_OPERATION_PATH')
    check(type(evidence.status) is int and 100 <= evidence.status <= 599, 'INVALID_OBSERVED_STATUS')
    check(evidence.content_type is None or type(evidence.content_type) is str, 'INVALID_CONTENT_TYPE')
    try:
        document = loads(evidence.contract.decode('utf-8'))
        body = evidence.body.decode('utf-8', errors='strict')
    except (ValueError, UnicodeError) as exc:
        raise Blocked('SOURCE_ENCODING_OR_JSON') from exc
    check(type(document) is dict and document.get('openapi') in ('3.0.4', '3.1.0'),
          'UNQUALIFIED_OPENAPI_VERSION')
    check('jsonSchemaDialect' not in document, 'UNQUALIFIED_SCHEMA_DIALECT')
    root = '/paths/' + escape(evidence.path) + '/' + evidence.method + '/responses'
    try:
        responses = pointer(document, root)
    except ValueError as exc:
        raise Blocked('MISSING_OPERATION_RESPONSES') from exc
    check(type(responses) is dict and bool(responses), 'UNUSABLE_RESPONSES')
    extracted = {'openapi': document['openapi'], 'paths': {evidence.path: {evidence.method: {
        'responses': deepcopy(responses)}}}}
    closure = set()

    def retain(path):
        tokens = path.split('/')[1:]
        source, target = document, extracted
        for index, token in enumerate(tokens):
            key = token.replace('~1', '/').replace('~0', '~')
            # Sparse arrays would invent nulls or include unrelated evidence. Hold
            # unless the whole array already belongs to a retained subtree.
            if isinstance(source, list):
                check(target == source, 'ARRAY_REFERENCE_CONTEXT_HOLD')
                return
            source = source[key]
            if index == len(tokens) - 1:
                target[key] = deepcopy(source)
            else:
                if key not in target:
                    check(type(source) is dict, 'REFERENCE_CONTEXT_HOLD')
                    target[key] = {}
                target = target[key]

    def walk(node, active=()):
        if isinstance(node, dict):
            check(not ({'$id', '$schema', '$anchor', '$dynamicRef', '$dynamicAnchor'} & node.keys()),
                  'UNQUALIFIED_REFERENCE_OR_DIALECT_CONTEXT')
            if '$ref' in node:
                check(set(node) == {'$ref'}, 'UNQUALIFIED_REFERENCE_SIBLINGS')
                ref = node['$ref']
                check(type(ref) is str and ref.startswith('#/'), 'EXTERNAL_OR_ANCHOR_REFERENCE')
                check(re.search(r'%(?![0-9a-fA-F]{2})', ref) is None, 'INVALID_REFERENCE_ESCAPE')
                path = unquote(ref[1:], errors='strict')
                check(path not in active, 'UNQUALIFIED_RECURSION')
                try:
                    value = pointer(document, path)
                except ValueError as exc:
                    raise Blocked('UNRESOLVED_REFERENCE') from exc
                if path not in closure:
                    walk(value, active + (path,))
                    retain(path)
                    closure.add(path)
            else:
                for value in node.values():
                    walk(value, active)
        elif isinstance(node, list):
            for value in node:
                walk(value, active)

    walk(responses, (root,))
    # Reuse the qualified schema admission guard, never measure the observed body.
    # Inspect every response/media alternative; status and Content-Type select none.
    def response_check(response, location):
        while isinstance(response, dict) and '$ref' in response:
            location = unquote(response['$ref'][1:], errors='strict')
            response = pointer(document, location)
        check(isinstance(response, dict) and isinstance(response.get('content'), dict)
              and bool(response['content']), 'UNQUALIFIED_RESPONSE_CONTENT')
        for media, representation in response['content'].items():
            check(isinstance(representation, dict) and 'schema' in representation, 'ABSENT_SCHEMA')
            try:
                prepare_validator(document, '#' + location + '/content/' + escape(media) + '/schema')
            except OracleNotReady as exc:
                raise Blocked('SCHEMA_ADMISSION_HOLD:' + str(exc)) from exc
    for key, response in responses.items():
        if not key.startswith('x-'):
            response_check(response, root + '/' + escape(key))
    check(pointer(extracted, root) == responses, 'RESPONSES_VALUE_MISMATCH')
    for path in closure:
        check(pointer(extracted, path) == pointer(document, path), 'REFERENCE_VALUE_MISMATCH')
    # The only serialization entry point is this explicit allowlist, never asdict(evidence).
    content = encode({'operation': {'method': evidence.method, 'path': evidence.path},
                      'openapi': extracted,
                      'observed_response': {'status': evidence.status,
                                            'content_type': evidence.content_type, 'body': body}})
    check(loads(content)['observed_response']['body'].encode('utf-8') == evidence.body,
          'BODY_ROUND_TRIP_FAILED')
    return Rendered(content, {'renderer_version': VERSION, 'renderer_sha256': artifact_hash(),
        'contract_identity': contract_identity, 'contract_sha256': digest(evidence.contract),
        'body_identity': body_identity, 'body_sha256': digest(evidence.body),
        'responses_pointer': root, 'reference_closure_paths': sorted(closure),
        'rendered_evidence_sha256': digest(content)})
