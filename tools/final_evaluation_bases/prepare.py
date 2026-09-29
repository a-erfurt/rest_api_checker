"""Serialize only the six bases of the hash-bound final construction plan.

No application imports, reference determination, child transformations or
release decisions. Invoke directly, never through the application package.
"""
import argparse
import hashlib
import json
from pathlib import Path


PLAN_COMMIT = 'e549cad575b34ada71b282fb0c2876acbb146ce0'
PLAN_PATH = '03_research_design/final_case_construction_plan_v1.json'
PLAN_HASH = 'aefae56258323ad6da7edadf714c8ca01fadd5bb953efc4c479a5ec2bbb7227c'
MD_HASH = 'c6b145ecffdaaa50e9413fa6e18651c41aa424d9fcf9caba6342c8e1d5969e27'
STATE = 'BASE_MATERIALIZED_REFERENCE_NOT_REVIEWED'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def document(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def pointer(document_value, path):
    value = document_value
    if path == '':
        return value
    if not path.startswith('/'):
        raise ValueError('Invalid pointer')
    for token in path[1:].split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def serialize_fields(fields):
    """Instantiate a closed ordered recipe, without interpreting a schema."""
    nodes = {}
    for row in fields:
        path, kind = row['instance_pointer'], row['kind']
        if path in nodes or (not nodes and path != ''):
            raise ValueError('Duplicate pointer or missing root')
        if kind in ('object', 'array', 'null'):
            if set(row) != {'instance_pointer', 'kind'}:
                raise ValueError('Unexpected literal or recipe field')
            value = {} if kind == 'object' else [] if kind == 'array' else None
        elif kind in ('integer', 'string'):
            if set(row) != {'instance_pointer', 'kind', 'literal'}:
                raise ValueError('Missing literal or unexpected recipe field')
            value = row['literal']
            if type(value) is not (int if kind == 'integer' else str):
                raise ValueError('Literal kind mismatch')
        else:
            raise ValueError('Unsupported recipe kind')
        if path:
            if not path.startswith('/'):
                raise ValueError('Invalid pointer')
            parent_path, token = path.rsplit('/', 1)
            parent = nodes[parent_path]
            token = token.replace('~1', '/').replace('~0', '~')
            if isinstance(parent, dict):
                if token in parent:
                    raise ValueError('Duplicate member')
                parent[token] = value
            elif isinstance(parent, list) and token == str(len(parent)):
                parent.append(value)
            else:
                raise ValueError('Non-container parent or non-contiguous array')
        nodes[path] = value
    if '' not in nodes:
        raise ValueError('Missing root')
    return json.dumps(nodes[''], ensure_ascii=False, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def bound_bytes(path, digest, size=None):
    raw = path.read_bytes()
    if sha(raw) != digest or (size is not None and len(raw) != size):
        raise ValueError(f'Source binding mismatch: {path}')
    return raw


def prepare(research, output, *, technical_commit, materialized_at):
    """Write a new base-only directory after all recipe/source checks succeed.

    The caller separately verifies Git commit identity and the complete
    exclusion corpus. This output is never a final dataset release.
    """
    research, output = Path(research), Path(output)
    if output.exists():
        raise FileExistsError('Output must be a new directory; no overwrite')
    plan_raw = bound_bytes(research / PLAN_PATH, PLAN_HASH)
    bound_bytes(research / PLAN_PATH.replace('.json', '.md'), MD_HASH)
    plan = json.loads(plan_raw)
    sources = {s['id']: s for s in plan['sources']}
    files, entries, hashes = {}, [], set()
    source_ids = {s for b in plan['base_templates'] for s in b['source_ids']}
    source_bytes = {s: bound_bytes(research / sources[s]['path'],
                                  sources[s]['sha256'], sources[s]['bytes'])
                    for s in source_ids}
    # Base order is the first dependent child's position in the bound order.
    by_case = {c['case_id']: c for c in plan['primary_candidates']}
    order = list(dict.fromkeys(by_case[c]['base_template_id']
                              for c in plan['finite_priority_order']
                              if by_case[c]['base_template_id'] is not None))
    bases = {b['base_template_id']: b for b in plan['base_templates']}
    if len(bases) != 6 or set(order) != set(bases):
        raise ValueError('Unexpected base register')
    for base_id in order:
        b = bases[base_id]
        if b['basis_kind'] != 'CONTRACT_DERIVED':
            raise ValueError('Only the six contract-derived bases are supported')
        idx = plan['base_templates'].index(b)
        contract = plan['contracts'][b['api']]
        snapshot = json.loads(source_bytes[contract['source_id']])
        for path in b['schema_pointers'] + [contract['response_map_pointer']]:
            pointer(snapshot, path)  # Source-location resolution, no schema validation.
        family = next(f for f in plan['families']
                      if f['family_id'] == b['construction_family_id'])
        children = [c['case_id'] for c in plan['primary_candidates']
                    if c['base_template_id'] == base_id]
        if children != family['primary_case_ids'] or len(children) != 2:
            raise ValueError('Dependency mapping mismatch')
        body = serialize_fields(b['field_specification'])
        if sha(body) in hashes:
            raise ValueError('Unexpected identical base bodies; hold before publication')
        hashes.add(sha(body))
        recipe = {
            'recipe_id': f'{base_id}/field-specification-v1',
            'plan_path': PLAN_PATH, 'plan_sha256': PLAN_HASH,
            'plan_pointer': f'/base_templates/{idx}',
            'field_specification': b['field_specification'],
            'closed_recipe': b['closed_recipe'],
            'serialization': {k: v for k, v in plan['serialization_for_later'].items()
                              if k != 'restriction'},
        }
        prefix = f'bases/{base_id}/'
        payloads = {
            'response_body.bin': body,
            'status.txt': str(b['base_status']).encode('ascii'),
            'content_type.txt': b['base_content_type'].encode('utf-8'),
            'recipe.json': document(recipe),
        }
        metadata = {
            'base_id': base_id, 'state': STATE,
            'intended_role': 'PRE_FAULT_BASE_FOR_LATER_REFERENCE_REVIEW',
            'basis_kind': b['basis_kind'], 'api': b['api'],
            'operation': contract['operation'],
            'construction_family_ids': [b['construction_family_id']],
            'base_group_id': b['base_group_id'],
            'structural_pattern_group_id': b['structural_pattern_group_id'],
            'dependent_final_case_ids': children,
            'planned_retained_control_id': family['scored_base_case_id'],
            'final_candidate_materialized': False,
            'supplied_http_status': b['base_status'],
            'raw_content_type': b['base_content_type'],
            'envelope_origin': 'CONSTRUCTED_TEST_VALUES_NOT_SERVER_OBSERVATION',
            'text_sidecar_encoding': 'UTF-8, no trailing newline',
            'natural_observation_id': None, 'natural_request_artifact': None,
            'acquisition_timestamp': None, 'deployment': None,
            'natural_fields_null_reason': b['natural_request_reason'],
            'materialized_at': materialized_at,
            'source_bindings': [sources[s] for s in b['source_ids']],
            'contract_source_id': contract['source_id'],
            'contract_sha256': contract['sha256'],
            'schema_pointers': b['schema_pointers'],
            'response_map_pointer': contract['response_map_pointer'],
            'recipe_id': recipe['recipe_id'],
            'plan_base_pointer': recipe['plan_pointer'],
            'construction_trace': 'Plan field specification -> ordered containers and literal values -> compact UTF-8; no child transformation',
            'artifacts': {name: {'path': prefix + name, 'sha256': sha(raw), 'bytes': len(raw)}
                          for name, raw in payloads.items()},
        }
        payloads['metadata.json'] = document(metadata)
        files.update({prefix + name: raw for name, raw in payloads.items()})
        entries.append({'base_id': base_id, 'metadata': {
            'path': prefix + 'metadata.json', 'sha256': sha(payloads['metadata.json']),
            'bytes': len(payloads['metadata.json'])},
            'body': metadata['artifacts']['response_body.bin']})
    manifest = {
        'format': 'final-evaluation-bases-v1', 'state': STATE,
        'scope': 'SIX_CONSTRUCTION_BASES_ONLY', 'base_count': len(entries),
        'materialized_at': materialized_at,
        'authoring_provenance': 'Author-confirmed exact recipes, mechanically serialized with AI assistance',
        'plan_commit': PLAN_COMMIT,
        'plan_bindings': [{'path': PLAN_PATH, 'sha256': PLAN_HASH},
                         {'path': PLAN_PATH.replace('.json', '.md'), 'sha256': MD_HASH}],
        'implementation': {'technical_commit': technical_commit,
                           'path': 'tools/final_evaluation_bases/prepare.py',
                           'sha256': sha(Path(__file__).read_bytes())},
        'bases': entries,
        'natural_lineage': {'observation_id': 'HTTS-PO-0003',
                            'handling': 'EXISTING_ARCHIVE_BINDING_ONLY_NOT_COPIED',
                            'dependent_final_case_ids': ['FC-HTTS-009', 'FC-HTTS-010'],
                            'source_bindings': plan['natural_evidence']},
        'final_candidate_count': 0,
        'next_gate': 'Separate explicit authorization for Reference Oracle execution on these exact bases, followed by independent manual review before any fault derivation',
    }
    files['manifest.json'] = document(manifest)
    output.mkdir(parents=True)
    for path, raw in files.items():
        target = output / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--technical-commit', required=True)
    parser.add_argument('--materialized-at', required=True)
    args = parser.parse_args()
    result = prepare(args.research, args.output, technical_commit=args.technical_commit,
                     materialized_at=args.materialized_at)
    print(f"Materialized {result['base_count']} bases; {STATE}; no final candidates")


if __name__ == '__main__':
    main()
