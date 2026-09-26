"""Exact approved prompt binding and D07 request construction."""
from dataclasses import dataclass
import re

from ..persistence.importer import PROMPT_HASHES
from .encoding import Blocked, check, digest, encode, loads
from .renderer import Rendered

MODELS = ('qwen3.6:27b', 'gemma3:27b', 'mistral-small3.2:24b')
SEEDS = {1: 101, 2: 202, 3: 303}
OPTIONS = dict(temperature=0.2, top_p=0.9, top_k=40, min_p=0.0,
               repeat_penalty=1.0, repeat_last_n=64, draft_num_predict=0,
               num_ctx=32768, num_predict=512)
TIMEOUT = 300
VERSION = 'ollama-chat-request-v1'


@dataclass(frozen=True, slots=True)
class Request:
    body: bytes
    metadata: dict
    timeout: int = TIMEOUT


def build_request(rendered: Rendered, *, prompt_name, prompt: bytes, model, model_digest,
                  repetition) -> Request:
    check(type(rendered) is Rendered, 'RENDERED_EVIDENCE_REQUIRED')
    check(prompt_name in PROMPT_HASHES and digest(prompt) == PROMPT_HASHES[prompt_name],
          'APPROVED_PROMPT_HASH_MISMATCH')
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
    body = encode(value)
    return Request(body, {**rendered.metadata, 'request_version': VERSION,
        'prompt_name': prompt_name, 'prompt_sha256': digest(prompt), 'model': model,
        'model_digest': model_digest, 'repetition': repetition, 'seed': SEEDS[repetition],
        'timeout_seconds': TIMEOUT, 'rendered_request_sha256': digest(body)})


def validate_request(request):
    """Fail closed at the HTTP boundary even for an accidentally altered DTO."""
    check(type(request) is Request and request.timeout == TIMEOUT, 'REQUEST_OR_TIMEOUT_CHANGED')
    try:
        payload = loads(request.body)
        system, user = payload['messages']
        content = user['content'].encode('utf-8')
        check(digest(content) == request.metadata['rendered_evidence_sha256'], 'EVIDENCE_HASH_CHANGED')
        rebuilt = build_request(Rendered(content, request.metadata),
            prompt_name=request.metadata['prompt_name'], prompt=system['content'].encode('utf-8'),
            model=request.metadata['model'], model_digest=request.metadata['model_digest'],
            repetition=request.metadata['repetition'])
        check(request.body == rebuilt.body and digest(request.body) == request.metadata['rendered_request_sha256'],
              'REQUEST_BYTES_CHANGED')
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise Blocked('REQUEST_VALIDATION_FAILED') from exc


@dataclass(frozen=True, slots=True)
class ContextProof:
    """Externally measured native-template/tokenizer evidence, mandatory at dispatch.

    input_tokens includes the complete two messages AND native template/defaults.
    This stage supplies no guessed token counter or fabricated live preflight.
    """
    request_sha256: str
    model_digest: str
    template_sha256: str
    measurement_sha256: str
    input_tokens: int

    def verify(self, request):
        check(self.request_sha256 == digest(request.body)
              and self.model_digest == request.metadata['model_digest'], 'CONTEXT_PROOF_IDENTITY')
        for value in (self.template_sha256, self.measurement_sha256):
            check(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'CONTEXT_EVIDENCE_REQUIRED')
        check(type(self.input_tokens) is int and self.input_tokens > 0, 'CONTEXT_COUNT_REQUIRED')
        check(self.input_tokens + OPTIONS['num_predict'] <= OPTIONS['num_ctx'], 'CONTEXT_OVERFLOW')
