"""Read-only descriptions from stored references, provenance and OpenAPI metadata.

These strings are presentation only. They never enter model input or derive a
reference verdict from a mutation family, case name, or intended outcome.
"""
import json
import re

from .persistence.database import pointer
from .terminal import clean


_LABELS = {'PASS': 'P', 'FAIL': 'F', 'NOT_APPLICABLE': 'N'}
_ORIGINS = {
    'natural_observation': 'Recorded API response',
    'synthetic_conformant_control': 'Constructed control response',
    'synthetic_inconsistency': 'Controlled response variant',
}


def _text(value, limit=None):
    text = ' '.join(clean(value).split()) if value is not None else ''
    return text if limit is None or len(text) <= limit else text[:limit-1].rstrip()+'…'


def reference_vector(reference):
    """Display only an explicitly stored verdict; unknown/missing values stay unknown."""
    if isinstance(reference, dict):
        reference = [reference.get(category) for category in ('c1', 'c2', 'c3')]
    if not isinstance(reference, (list, tuple)) or len(reference) != 3:
        return '???'
    return ''.join(_LABELS.get(value, '?') if isinstance(value, str) else '?' for value in reference)


def contract_context(document, operation, reference_metadata):
    """Project descriptions and an explicitly referenced empty schema; no validation."""
    paths = document.get('paths', {})
    path = paths.get(operation['path_template'], {}) if isinstance(paths, dict) else {}
    node = path.get(operation['http_method'].lower(), {}) if isinstance(path, dict) else {}
    node = node if isinstance(node, dict) else {}
    info = document.get('info', {})
    info = info if isinstance(info, dict) else {}
    empty_schema = False
    location = reference_metadata.get('schema_pointer')
    if isinstance(location, str) and location.startswith('#/'):
        try:
            schema = pointer(document, location[1:])
            seen = set()
            while isinstance(schema, dict) and set(schema) == {'$ref'} and isinstance(schema['$ref'], str):
                ref = schema['$ref']
                if not ref.startswith('#/') or ref in seen:
                    break
                seen.add(ref)
                schema = pointer(document, ref[1:])
            empty_schema = schema == {}
        except (ValueError, KeyError, IndexError, TypeError):
            # Missing descriptive metadata does not replace or repair a reference.
            pass
    return dict(operation_summary=node.get('summary'), operation_description=node.get('description'),
                contract_title=info.get('title'), contract_description=info.get('description'),
                schema_empty=empty_schema)


def service_name(row):
    """A transparent display alias; the original DB name/identity stays unchanged."""
    name = _text(row.get('service') or row.get('name') or 'Unnamed service')
    if name.lower() == 'htts' and str(row.get('path', '')).startswith('/resistance/'):
        return 'Resistance'
    return 'EDX' if name.lower() == 'edx' else name


def service_label(row):
    name = service_name(row)
    description = {'EDX': 'Document/data-stream validation service',
                   'Resistance': 'File validation service'}.get(name)
    description = description or row.get('service_description') or row.get('contract_description')
    return name + '\n' + (_text(description, 90) if description else 'Stored API service')


def operation_label(row):
    method = _text(row.get('method') or row.get('http_method') or '?').upper()
    # OpenAPI paths are case-sensitive: normalize whitespace, never path casing.
    path = _text(row.get('path') or row.get('path_template') or 'Unknown endpoint')
    description = _text(row.get('operation_summary') or row.get('operation_description'))
    description = re.sub(r'\s*\(?(?:post|get|put|patch|delete|head|options) call to [^)]*\)?', '',
                         description, flags=re.IGNORECASE).strip(' —;')
    common = {'validation of incoming stream from post body': 'Validate incoming data stream',
              'validation of incoming file': 'Validate incoming file'}
    description = common.get(description.casefold(), description)
    return f'{method} {path}' + ('   '+_text(description, 65) if description else '')


def model_label(row):
    name = _text(row.get('name') or 'Unnamed model')
    display = {'gemma3:27b': 'Gemma 3 27B', 'qwen3.6:27b': 'Qwen 3.6 27B',
               'mistral-small3.2:24b': 'Mistral Small 3.2 24B'}.get(name, name)
    parts = [display]
    if row.get('parameters_b') is not None and ':' not in name and display == name:
        try:
            parts.append(f"{float(row['parameters_b']):g}B")
        except (TypeError, ValueError):
            pass
    if row.get('quantization'):
        parts.append(_text(row['quantization']))
    if row.get('availability'):
        parts.append(_text(row['availability']))
    return '   '.join(parts)


CASE_TYPES = [
    ('conforming', '✓ Conforming / baseline', 'Response matches the documented contract.'),
    ('c1', 'C1 Status fault', 'HTTP status is not covered by the documented response mapping.'),
    ('c2', 'C2 Media-type fault', 'Status is covered; Content-Type is not documented for that response.'),
    ('c3', 'C3 Schema fault', 'Status/media type conform; the JSON body violates the response schema.'),
    ('controls', 'Controls / formatting', 'Explicitly recorded controls and formatting variants.'),
    ('all', 'All cases', ''),
]


def case_type(row):
    """Classification uses only the bound stored reference, never fault intent."""
    return {'PPP': 'conforming', 'FNN': 'c1', 'PFN': 'c2', 'PPF': 'c3'}.get(
        reference_vector(row.get('reference')), 'unknown')


def is_control(row):
    metadata = row.get('metadata')
    metadata = metadata if isinstance(metadata, dict) else {}
    candidate = metadata.get('original_candidate')
    sources = [metadata, candidate] if isinstance(candidate, dict) else [metadata]
    return row.get('origin') == 'synthetic_conformant_control' or any(
        str(source.get('formatting_control', '')).casefold() not in ('', 'false', 'none', '0', 'no')
        or source.get('service_state') in ('formatting', 'formatting_control') for source in sources)


def filter_cases(cases, kind):
    if kind not in {value[0] for value in CASE_TYPES}:
        raise ValueError('Unknown case type')
    return [row for row in cases if kind == 'all' or
            (is_control(row) if kind == 'controls' else case_type(row) == kind)]


def _parameters(transformation):
    values = transformation.get('parameters') or {}
    if isinstance(values, dict):
        return values
    if isinstance(values, list):
        return {item[0]: item[1] for item in values
                if isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[0], str)}
    return {}


def _change(row, metadata):
    transformation = metadata.get('transformation')
    if not isinstance(transformation, dict):
        return ''
    parameters = _parameters(transformation)
    changes = []
    if 'status' in parameters:
        old = metadata.get('parent_status')
        if old is None or str(old) != str(parameters['status']):
            changes.append('HTTP status '+(str(old)+' → ' if old is not None else 'set to ')+_text(parameters['status']))
    if 'content_type' in parameters:
        old = metadata.get('parent_content_type')
        if old is None or str(old) != str(parameters['content_type']):
            changes.append('Content-Type '+(_text(old)+' → ' if old is not None else 'set to ')+_text(parameters['content_type']))
    action = parameters.get('action')
    if action == 'explicit_full_body_replacement':
        changes.append('response body replaced')
    elif action in ('add', 'remove', 'replace'):
        path = parameters.get('path')
        try:
            path_parts = json.loads(path) if isinstance(path, str) else path
            if isinstance(path_parts, list):
                location = '/'+ '/'.join(str(p) for p in path_parts) if path_parts else 'body root'
            else:
                location = _text(path) or 'response body'
        except (ValueError, TypeError):
            location = _text(path) or 'response body'
        action_name = {'add': 'addition at', 'remove': 'removal at', 'replace': 'replacement at'}[action]
        changes.append(action_name+' '+location)
    if not changes:
        variant = transformation.get('variant')
        if variant:
            changes.append('recorded variant '+_text(variant).replace('_', ' '))
    return 'Controlled change: '+', '.join(changes)+'.' if changes else ''


def _schema_reason(reference_metadata):
    diagnostics = reference_metadata.get('diagnostics') or []
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        if diagnostic.get('code') == 'INVALID_JSON_REPRESENTATION':
            return 'the body is not valid JSON.'
        if diagnostic.get('code') != 'SCHEMA_ASSERTION_FAILED':
            continue
        location = _text(diagnostic.get('instance_pointer')) or 'body root'
        keyword = diagnostic.get('keyword')
        if keyword == 'additionalProperties':
            return f'additional properties are forbidden at {location}.'
        if keyword == 'required':
            return f'a required property is missing at {location}.'
        if keyword == 'type':
            return f'a value has the wrong JSON type at {location}.'
        if keyword:
            return f'the {_text(keyword)} schema constraint fails at {location}.'
    return 'the body fails the documented response-schema check.'


def describe_case(row):
    """Return concise, sanitized text for every case without inventing source facts."""
    reference = row.get('reference')
    vector = reference_vector(reference)
    metadata = row.get('metadata')
    metadata = metadata if isinstance(metadata, dict) else {}
    reference_metadata = row.get('reference_metadata')
    reference_metadata = reference_metadata if isinstance(reference_metadata, dict) else {}
    status = _text(row.get('status_code')) or 'unknown'
    media = _text(row.get('content_type')) or 'not recorded'
    schema_reason = _schema_reason(reference_metadata)
    title, verdict = {
        'FNN': ('C1 fault', f'HTTP {status} is not covered by the OpenAPI response mapping.'),
        'PFN': ('C2 fault', f'Content-Type {media} is not documented for HTTP {status}.'),
        'PPF': ('C3 fault', schema_reason[:1].upper()+schema_reason[1:]),
        'PPP': ('✓ conforming', 'Response matches the documented contract.'),
    }.get(vector, ('Stored response case',
        f'Stored response case · HTTP {status} · {media} · Reference {vector}'))
    if vector == 'PPP' and row.get('schema_empty') is True:
        verdict = 'Valid JSON under the documented empty schema.'
    description = row.get('description') or metadata.get('description') or metadata.get('label')
    change = _change(row, metadata)
    details = [f'HTTP status: {status}; Content-Type: {media}']
    if description:
        details.append(_text(description))
    if change:
        details.append(change)
    family = row.get('family') or metadata.get('root_family')
    if family:
        details.append('Case family: '+_text(family))
    parent = row.get('parent_case') or metadata.get('immediate_parent')
    if parent:
        details.append('Derived from: '+_text(parent))
    if metadata.get('fault_control_family'):
        details.append('Recorded construction family: '+_text(metadata['fault_control_family'])+' (provenance, not a verdict)')
    transformation = metadata.get('transformation')
    if isinstance(transformation, dict):
        if transformation.get('variant'):
            details.append('Recorded variant: '+_text(transformation['variant']))
        construction = _parameters(transformation).get('construction')
        if construction:
            details.append('Recorded construction: '+_text(construction))
    for key, label in (('formatting_control', 'Formatting control'), ('response_pattern_group', 'Response-pattern group')):
        if metadata.get(key) is not None:
            details.append(label+': '+_text(metadata[key]))
    values = [reference.get(c) for c in ('c1', 'c2', 'c3')] if isinstance(reference, dict) else reference
    reference_text = ', '.join(f'C{i+1} '+('N/A' if v == 'NOT_APPLICABLE' else _text(v))
                              for i, v in enumerate(values)) if isinstance(values, (list, tuple)) and len(values) == 3 else 'Reference unavailable'
    return dict(title=_text(title), description=_text(verdict, 150), details=[clean(d) for d in details],
                reference_vector=vector, reference_text=reference_text)
