"""Materialize only the approved development_dataset_v1.md inventory.

Expectations are checked after construction's artifact-only Oracle calls. Output
is a candidate for manual review, never an automatically released reference set.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess

from . import construction as c

SPEC_PATH = Path(__file__).with_name('development_dataset_v1.json')
REPOSITORY = Path(__file__).resolve().parents[2]
ORIGINS = {
    c.Origin.NATURAL: 'NATURAL',
    c.Origin.CONTROL: 'SYNTHETIC_CONFORMANT',
    c.Origin.INCONSISTENCY: 'SYNTHETIC_INCONSISTENT',
}


class DatasetRejected(ValueError):
    """No manifest is published; rejection.json retains available evidence."""


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw):
    return (json.dumps(raw, indent=2, sort_keys=True, ensure_ascii=True) + '\n').encode()


def _git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def _read_sources(research, spec):
    # Explicit allowlist: never enumerate pilots or import sibling families.
    sources = {}
    for path, expected in spec['sources'].items():
        raw = (research / path).read_bytes()
        if _sha(raw) != expected:
            raise DatasetRejected(f'SOURCE_HASH_MISMATCH: {path}')
        sources[path] = raw
    return sources


def _versions():
    code_paths = sorted((REPOSITORY / 'src/rest_api_checker').glob('*.py'))
    evidence_paths = [
        SPEC_PATH, REPOSITORY / 'uv.lock', REPOSITORY / 'pyproject.toml',
        REPOSITORY / 'tests/test_oracle_qualification.py',
        REPOSITORY / 'tests/contracts/provenance.json',
        REPOSITORY / 'docs/validator_spike.md',
    ]
    oracle_paths = ['src/rest_api_checker/' + name + '.py' for name in
                    ('oracle', 'models', 'schema_validation', 'media_type')]
    return {
        'implementation_commit': _git(REPOSITORY, 'rev-parse', 'HEAD'),
        'working_tree_dirty': bool(_git(REPOSITORY, 'status', '--porcelain',
                                       '--untracked-files=normal')),
        'oracle_commit': _git(REPOSITORY, 'log', '-1', '--format=%H', '--', *oracle_paths),
        'python': platform.python_version(),
        'dependencies': {name: version(name) for name in (
            'rest-api-checker', 'openapi-schema-validator', 'jsonschema',
            'referencing', 'jsonschema-specifications', 'attrs', 'rpds-py', 'pytest')},
        'files': {str(p.relative_to(REPOSITORY)): _sha(p.read_bytes())
                  for p in sorted(set(code_paths + evidence_paths))},
        'qualification': 'Q01-Q26; see hashed test and research review evidence',
    }


def _archived_response(files):
    # This bounded archive format has one HTTP response and one Content-Type.
    lines = files['response_headers.txt'].decode('utf-8').splitlines()
    status_lines = [line for line in lines if line.startswith('HTTP/')]
    media = [line.split(':', 1)[1].strip() for line in lines
             if line.lower().startswith('content-type:')]
    if len(status_lines) != 1 or len(media) != 1:
        raise DatasetRejected('AMBIGUOUS_ARCHIVED_HEADERS')
    status = int(status_lines[0].split()[1])
    curl = dict(line.split('=', 1) for line in files['curl_result.txt'].decode().splitlines())
    body = files['response_body.bin']
    if (int(curl['http_code']) != status or curl['content_type'] != media[0]
            or int(curl['size_download']) != len(body)):
        raise DatasetRejected('ARCHIVED_RESPONSE_METADATA_MISMATCH')
    return c.Response(status, media[0], body)


def _construct(row, cases, contracts, sources, spec):
    case_id = row['case_id']
    contract = contracts[row['api']]
    parent = cases.get(row['parent'])
    if row['origin'] == 'NATURAL':
        root = spec['roots'][row['root_family']]
        directory = root['source_directory']
        files = {name: sources[f'{directory}/{name}'] for name in root['files']}
        return c.observe(case_id, contract, _archived_response(files), c.Observation(
            directory, files['request_metadata.txt'], files['response_headers.txt']))
    if case_id == 'DEV-02':
        return c.construct_parent(
            case_id, contract, c.Response(200, 'application/json', b'{"code":0}'),
            construction='development_dataset_v1.md §3 DEV-02: K01 minimal lowercase control',
            parent=parent,
        )
    if case_id == 'DEV-08':
        return c.construct_control(case_id, contract, 'K02', 'null', parent=parent)
    return c.mutate(case_id, parent, row['family'], variant=row['variant'])


def _result(result):
    if result is None:
        return None
    return {**asdict(result), 'vector': list(result.vector), 'overall': result.overall}


def _write(output, path, raw):
    target = output / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return {'path': path, 'sha256': _sha(raw), 'size_bytes': len(raw)}


def _record(output, case, row):
    prefix = f'cases/{case.case_id}'
    body = _write(output, f'{prefix}/response_body.bin', case.response.body)
    response = _write(output, f'{prefix}/response.json', _json({
        'status': case.response.status, 'content_type': case.response.content_type,
        'body': body,
    }))
    transformation = None
    if case.transformation:
        transformation = asdict(case.transformation)
        if case.transformation.body_edit:
            edit = case.transformation.body_edit
            transformation['body_edit']['replacement'] = _write(
                output, f'{prefix}/replacement.bin', edit.replacement)
    parent = case.parent
    return {
        'case_id': case.case_id, 'api': case.contract.api,
        'operation': {'method': 'post', 'path': case.contract.operation_path},
        'origin': ORIGINS[case.origin], 'root_family': row['root_family'],
        'immediate_parent': parent.case_id if parent else None,
        'fault_control_family': row['family'],
        'contract_sha256': case.contract.sha256,
        'status': case.response.status, 'content_type': case.response.content_type,
        'body': body, 'response': response, 'response_sha256': case.response.sha256,
        'parent_body_sha256': _sha(parent.response.body) if parent else None,
        'parent_response_sha256': case.parent_sha256,
        'parent_status': parent.response.status if parent else None,
        'parent_content_type': parent.response.content_type if parent else None,
        'transformation': transformation,
        'observation_source': case.observation.source if case.observation else None,
        'oracle': _result(case.result), 'oracle_before': _result(case.before),
        'verification_target': {key: row[key] for key in (
            'expected_vector', 'expected_overall', 'expected_body_sha256')},
        'manually_reviewed': False,
    }


def _verify_case(case, row, cases, spec):
    comparisons = {
        'id': (case.case_id, row['case_id']),
        'api': (case.contract.api, row['api']),
        'origin': (ORIGINS[case.origin], row['origin']),
        'parent': (case.parent.case_id if case.parent else None, row['parent']),
        'status': (case.response.status, row['status']),
        'content_type': (case.response.content_type, row['content_type']),
        'body_sha256': (_sha(case.response.body), row['expected_body_sha256']),
        'vector': (list(case.result.vector), row['expected_vector']),
        'overall': (case.result.overall, row['expected_overall']),
    }
    for field, (actual, expected) in comparisons.items():
        if actual != expected:
            raise DatasetRejected(f'{case.case_id}: {field}: {actual!r} != {expected!r}')
    if row['parent']:
        parent = cases[row['parent']]
        parent_row = next(r for r in spec['cases'] if r['case_id'] == row['parent'])
        if case.parent != parent or parent_row['root_family'] != row['root_family']:
            raise DatasetRejected(f'{case.case_id}: PARENT_LINEAGE_MISMATCH')
        if case.transformation is None:
            raise DatasetRejected(f'{case.case_id}: MISSING_TRANSFORMATION')
        edit = case.transformation.body_edit
        if edit and edit.apply(parent.response.body) != case.response.body:
            raise DatasetRejected(f'{case.case_id}: BODY_EDIT_MISMATCH')
    if row['origin'] == 'SYNTHETIC_INCONSISTENT':
        if case.before is None or case.before.vector != ('PASS',) * 3:
            raise DatasetRejected(f'{case.case_id}: NONCONFORMANT_FAULT_PARENT')
    if row['family'] and row['case_id'] != 'DEV-02':
        if (case.transformation.family, case.transformation.variant) != (row['family'], row['variant']):
            raise DatasetRejected(f'{case.case_id}: TRANSFORMATION_MISMATCH')
    if case.case_id == 'DEV-12' and not any(
            d.code == 'INVALID_JSON_REPRESENTATION' for d in case.result.diagnostics):
        raise DatasetRejected('DEV-12: MISSING_REPRESENTATION_DIAGNOSTIC')


def _verify_inventory(records):
    if [r['case_id'] for r in records] != [f'DEV-{i:02}' for i in range(1, 13)]:
        raise DatasetRejected('EXACT_INVENTORY_REQUIRED')
    expected_counts = {
        'api': {'edx': 6, 'htts': 6},
        'origin': {'NATURAL': 3, 'SYNTHETIC_CONFORMANT': 2, 'SYNTHETIC_INCONSISTENT': 7},
        'root_family': {'EDX-P02': 6, 'HTTS-H01': 4, 'HTTS-H05': 2},
    }
    for field, expected in expected_counts.items():
        if Counter(r[field] for r in records) != expected:
            raise DatasetRejected(f'INVENTORY_COUNT_MISMATCH: {field}')
    allowed = {('F01', 'status_500'), ('F02', 'undeclared_media'), ('F03', 'string'),
               ('F04', 'root'), ('F06', 'remove_msg'), ('F09', 'broken_json'),
               ('K01', 'explicit_parent'), ('K02', 'null')}
    for r in records:
        if r['transformation'] and (r['fault_control_family'], r['transformation']['variant']) not in allowed:
            raise DatasetRejected('HELD_OUT_VARIANT_PRESENT')
    labels = Counter(r['oracle']['overall'] for r in records)
    if labels != {'CONSISTENT': 4, 'INCONSISTENT': 8}:
        raise DatasetRejected('OVERALL_COUNT_MISMATCH')
    return {**expected_counts, 'overall': dict(sorted(labels.items()))}


def materialize(research: Path, output: Path) -> dict:
    """Create a fresh staging directory; retain partial evidence on any failure.

    Existing nonempty directories are never overwritten. Use a second fresh path
    for a byte-for-byte reproducibility check or a new reviewed candidate.
    """
    research, output = research.resolve(), output.resolve()
    if output.is_relative_to(research):
        raise ValueError('The research repository is read-only')
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Use a fresh or empty staging directory')
    output.mkdir(parents=True, exist_ok=True)
    spec = json.loads(SPEC_PATH.read_bytes())
    records, cases = [], {}
    row = None
    versions = None
    try:
        versions = _versions()
        sources = _read_sources(research, spec)
        source_records = {
            path: _write(output, f'sources/{path}', raw)
            for path, raw in sources.items()
        }
        contracts = {api: c.ContractSnapshot(api, sources[path])
                     for api, path in spec['contracts'].items()}
        for row in spec['cases']:
            try:
                case = _construct(row, cases, contracts, sources, spec)
            except c.ConstructionRejected as exc:
                if exc.candidate is not None:
                    records.append(_record(output, exc.candidate, row))
                raise
            records.append(_record(output, case, row))
            _verify_case(case, row, cases, spec)
            cases[case.case_id] = case
        counts = _verify_inventory(records)
        manifest = {
            'format': 'development-dataset-v1',
            'release_status': 'CANDIDATE_PENDING_MANUAL_REVIEW',
            'manual_review': {'required': 12, 'completed': 0},
            'authority': spec['authority'], 'research_commit': spec['research_commit'],
            'pilot_source_commit': spec['pilot_source_commit'],
            'sources': source_records, 'contracts': spec['contracts'],
            'roots': spec['roots'],
            'versions': versions, 'counts': counts, 'cases': records,
            'held_out_variants_absent': True,
        }
        # Publish only after every admission check; no timestamps or output paths.
        raw = _json(manifest)
        _write(output, 'manifest.json', raw)
        _write(output, 'manifest.sha256', f'{_sha(raw)}  manifest.json\n'.encode())
        return manifest
    except Exception as exc:
        failure = {
            'release_status': 'REJECTED_PENDING_RESOLUTION',
            'case_id': row['case_id'] if row else None,
            'error_type': type(exc).__name__, 'reason': str(exc),
            'cases': records, 'versions': versions,
        }
        if isinstance(exc, c.ConstructionRejected):
            failure['oracle_before'] = _result(exc.before)
        _write(output, 'rejection.json', _json(failure))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research-repository', required=True, type=Path)
    parser.add_argument('--output', type=Path,
                        default=REPOSITORY / 'artifacts/development_dataset_v1')
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(REPOSITORY):
        parser.error('Staging output must be inside the technical repository')
    manifest = materialize(args.research_repository, args.output)
    print(f"Materialized {len(manifest['cases'])} cases; CANDIDATE_PENDING_MANUAL_REVIEW")
    print((args.output / 'manifest.sha256').read_text(), end='')


if __name__ == '__main__':
    main()
