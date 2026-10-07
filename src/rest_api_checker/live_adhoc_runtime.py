"""Current-runtime checks for explicitly separate, non-scientific live runs.

This module does not qualify an Ollama version for the thesis. Metadata reads do
not load a model. The byte budget is deliberately labelled an operational guard,
not a native token measurement; scientific ContextProof behavior is unchanged.
"""
from dataclasses import dataclass
from decimal import Decimal
import json
import re
import urllib.request

from .experiment import request_v2
from .experiment.encoding import digest, encode
from .experiment.provider import OllamaClient
from .experiment.request import OPTIONS
from .persistence.database import require

FORMAT = 'live-adhoc-setup-v1'
RUNTIME_FORMAT = 'live-adhoc-runtime-v1'
CONTEXT_METHOD = 'unqualified-conservative-byte-budget-v1'
THESIS_VERSION = '0.35.1'


def metadata(path, data=None):
    """Only local, read-only metadata endpoints; never generation or model loads."""
    require(path in ('/api/version', '/api/tags', '/api/ps', '/api/show'), 'Metadata endpoint required')
    body = None if data is None else encode(data)
    with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:11434'+path,
            data=body, headers={'Content-Type': 'application/json'}), timeout=3) as response:
        return json.load(response)


def probe_runtime(api=None):
    """Optional informational probe; offline discovery and cancellation still work."""
    api = api or metadata
    try:
        version = api('/api/version').get('version')
        require(isinstance(version, str) and version.strip(), 'Missing Ollama version')
        return dict(available=True, version=version, thesis_version=THESIS_VERSION,
            notice=f'⚠ Runtime differs from the qualified version: Ollama {version}. Interactive checks remain available.')
    except (OSError, ValueError, TypeError, AttributeError):
        return dict(available=False, version=None, thesis_version=THESIS_VERSION,
            notice='⚠ Local runtime unavailable; execution will check again after confirmation.')


def model_availability(api=None):
    """Read-only display hints; failure never removes configured menu entries."""
    api = api or metadata
    try:
        tags = api('/api/tags')['models']
        installed = {model['name']: 'installed' for model in tags}
        try:
            loaded = {model['name'] for model in api('/api/ps')['models']}
        except (OSError, ValueError, KeyError, TypeError):
            return installed
        return {name: 'installed · loaded' if name in loaded else 'installed · not loaded'
                for name in installed}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def capture(models, api=None):
    """Bind current version and exact installed model/template metadata after consent."""
    api = api or metadata
    version, tags = api('/api/version'), api('/api/tags')['models']
    require(isinstance(version.get('version'), str) and version['version'], 'Current Ollama version unavailable')
    identities, sources = [], {'version.json': encode(version)}
    for model in models:
        matches = [tag for tag in tags if tag.get('name') == model['name']]
        from .live_presenter import model_label
        require(matches, '✗ '+model_label({'name': model['name']})+' is not installed in Ollama.')
        show = api('/api/show', {'model': model['name']})
        # Ollama 0.40 can list several runner manifests for the same tag.
        # /api/show identifies the selected one; list order is not authority.
        selected = [item for item in show.get('manifests', []) if item.get('selected') is True]
        if selected:
            require(len(selected) == 1, 'Current model identity is ambiguous: '+model['name'])
            actual = selected[0].get('digest', '').removeprefix('sha256:')
            require(any(tag.get('digest', '').removeprefix('sha256:') == actual for tag in matches),
                    'Selected model manifest is absent from installed tags: '+model['name'])
        else:
            digests = {tag.get('digest', '').removeprefix('sha256:') for tag in matches}
            require(len(digests) == 1, 'Current model identity is ambiguous: '+model['name'])
            actual = digests.pop()
        require(re.fullmatch('[0-9a-f]{64}', actual) is not None, 'Current model digest unavailable')
        template = show.get('template')
        require(isinstance(template, str) and template.strip(), 'Current model template unavailable')
        raw = encode(show)
        name = f'model-{len(identities)+1}-show.json'
        sources[name] = raw
        identities.append(dict(name=model['name'], digest=actual,
            template_sha256=digest(template.encode()), metadata_sha256=digest(raw), show=name))
    host = dict(format=RUNTIME_FORMAT, runtime_identity='live_adhoc_ollama_'+version['version'],
        ollama=version, scientifically_qualified=False)
    binding = dict(runtime=host, models=identities)
    sources['runtime-binding.json'] = encode(binding)
    return binding, sources


def model_values(identity, sources):
    """Project actual show metadata for a new immutable model row, never defaults."""
    show = json.loads(sources[identity['show']])
    details, info = show.get('details', {}), show.get('model_info', {})
    architecture = info.get('general.architecture')
    family, quantization = details.get('family'), details.get('quantization_level')
    context = info.get(str(architecture)+'.context_length')
    require(all(isinstance(value, str) and value.strip() for value in (architecture, family, quantization))
            and type(context) is int and context > 0, 'Current model metadata is incomplete')
    count = info.get('general.parameter_count')
    parameters = ((Decimal(count)/Decimal(1_000_000_000)).quantize(Decimal('0.01'))
                  if type(count) is int and count > 0 else None)
    return dict(name=identity['name'], digest=identity['digest'], family=family,
        architecture=architecture, quantization=quantization, context_length=context,
        parameters_b=parameters if parameters else None)


def verify_live(binding, sources, api=None):
    api = api or metadata
    require(binding['runtime'].get('format') == RUNTIME_FORMAT
            and binding['runtime'].get('scientifically_qualified') is False, 'Ad-hoc runtime identity required')
    current, raw = capture(binding['models'], api=api)
    require(current == binding and raw == sources, 'Live runtime/model/template changed after confirmation')
    return True


@dataclass(frozen=True, slots=True)
class AdhocContextCheck:
    """Conservative small-input guard, explicitly not a native token proof."""
    request_sha256: str
    model_digest: str
    template_sha256: str
    metadata_sha256: str
    request_bytes: int
    template_bytes: int
    defaults_bytes: int
    method: str = CONTEXT_METHOD

    @property
    def budget_units(self):
        # Reserve twice the UTF-8 byte count plus 4096 units for chat framing.
        # This deliberately rejects large ad-hoc inputs; it is not qualification.
        return 2*(self.request_bytes+self.template_bytes+self.defaults_bytes)+4096

    def verify(self, request):
        request_v2.validate_request_v2(request)
        require(self.method == CONTEXT_METHOD, 'Ad-hoc context method drift')
        require(self.request_sha256 == digest(request.body)
                and self.model_digest == request.metadata['model_digest'], 'Ad-hoc request/model drift')
        require(all(isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v)
                    for v in (self.template_sha256, self.metadata_sha256)), 'Ad-hoc metadata evidence required')
        require(type(self.request_bytes) is int and self.request_bytes == len(request.body)
                and type(self.template_bytes) is int and self.template_bytes > 0
                and type(self.defaults_bytes) is int and self.defaults_bytes >= 0, 'Ad-hoc byte budget drift')
        require(self.budget_units + OPTIONS['num_predict'] <= OPTIONS['num_ctx'],
                'Selected input exceeds the conservative context budget; choose a smaller case')


def context_check(request, identity, sources):
    require(request.metadata['model_digest'].removeprefix('sha256:') == identity['digest'],
            'Ad-hoc request/current model drift')
    raw = sources[identity['show']]
    show = json.loads(raw)
    require(digest(raw) == identity['metadata_sha256']
            and digest(show['template'].encode()) == identity['template_sha256'], 'Ad-hoc template evidence drift')
    proof = AdhocContextCheck(digest(request.body), request.metadata['model_digest'],
        identity['template_sha256'], digest(raw), len(request.body), len(show['template'].encode()),
        len(encode({key: show.get(key) for key in ('system', 'parameters')})))
    proof.verify(request)
    return proof


def require_scope(setup, experiment_id, dataset_id):
    """There is no override that can select an existing or scientific write target."""
    require(type(experiment_id) is int and experiment_id != 10003 and dataset_id != 3,
            'Thesis experiment 10003 and Dataset 3 are protected')
    require(setup.get('format') == FORMAT and setup.get('live_adhoc') is True
            and setup.get('scientific_evaluation') is False and setup.get('gate_b_complete') is False
            and setup.get('dataset_id') == dataset_id and setup.get('fabricated') is False,
            'Explicit non-scientific interactive context required')


class AdhocClient:
    """Scoped composition of the existing transport, never a global guard override.

    Only hashes from this newly created context may reach the transport. The
    canonical attempt runner still owns raw receipts, parser and persistence.
    """
    def __init__(self, setup, experiment_id, dataset_id, *, client=None):
        require_scope(setup, experiment_id, dataset_id)
        self.setup, self.experiment_id, self.dataset_id = setup, experiment_id, dataset_id
        self.allowed = {item['sha256'] for item in setup['request_inventory']}
        require(self.allowed, 'Explicit live/ad-hoc request inventory required')
        self.client = client if client is not None else OllamaClient(request_validator=request_v2.validate_request_v2)

    def send(self, request, *, on_start):
        require_scope(self.setup, self.experiment_id, self.dataset_id)
        request_v2.validate_request_v2(request)
        require(digest(request.body) in self.allowed, 'Request is outside this interactive context')
        return self.client.send(request, on_start=on_start)
