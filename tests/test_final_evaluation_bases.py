"""Mechanical serializer tests with fabricated fields; no study fixtures/Oracle."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/final_evaluation_bases/prepare.py'
spec = importlib.util.spec_from_file_location('base_serializer', SCRIPT)
serializer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serializer)


def field(path, kind, **kwargs):
    return {'instance_pointer': path, 'kind': kind, **kwargs}


def test_literal_bytes_order_null_omission_unicode_and_nested_arrays():
    fields = [field('', 'object'), field('/z', 'array'), field('/z/0', 'null'),
              field('/z/1', 'object'), field('/z/1/t', 'string', literal='Grüße'),
              field('/a', 'integer', literal=13), field('/empty', 'array')]
    expected = '{"z":[null,{"t":"Grüße"}],"a":13,"empty":[]}'.encode('utf-8')
    assert serializer.serialize_fields(fields) == expected
    assert serializer.serialize_fields(fields) == expected
    assert fields[1] == field('/z', 'array')


def test_pointer_escaping_and_no_application_imports():
    fields = [field('', 'object'), field('/a~1b', 'object'),
              field('/a~1b/~0', 'string', literal='v')]
    assert serializer.serialize_fields(fields) == b'{"a/b":{"~":"v"}}'
    assert serializer.pointer({'a/b': {'~': 'v'}}, '/a~1b/~0') == 'v'
    subprocess.run([sys.executable, '-S', '-c',
                    'import runpy,sys; runpy.run_path(sys.argv[1]); '
                    'assert not any(k.startswith("rest_api_checker") for k in sys.modules)',
                    str(SCRIPT)], check=True)


@pytest.mark.parametrize('fields', [
    [], [field('/missing', 'null')],
    [field('', 'array'), field('/1', 'null')],
    [field('', 'array'), field('/00', 'null')],
    [field('', 'object'), field('/x', 'null'), field('/x', 'string', literal='a')],
    [field('', 'null'), field('/x', 'null')],
    [field('', 'integer', literal=True)],
    [field('', 'string', literal=7)],
    [field('', 'object', literal={})],
    [field('', 'boolean', literal=True)],
    [field('', 'object'), field('/missing/x', 'null')],
])
def test_ambiguous_or_unsupported_recipe_rejected(fields):
    with pytest.raises((ValueError, KeyError)):
        serializer.serialize_fields(fields)


def test_binding_mismatch_and_size_rejected(tmp_path):
    source = tmp_path / 'source'
    source.write_bytes(b'fabricated source')
    digest = serializer.sha(source.read_bytes())
    assert serializer.bound_bytes(source, digest, 17) == b'fabricated source'
    with pytest.raises(ValueError):
        serializer.bound_bytes(source, digest, 18)
    with pytest.raises(ValueError):
        serializer.bound_bytes(source, '0' * 64)


def test_wrong_plan_cannot_write_and_existing_directory_not_overwritten(tmp_path):
    research = tmp_path / 'research'
    path = research / serializer.PLAN_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(b'{}')
    output = tmp_path / 'output'
    with pytest.raises(ValueError, match='Source binding mismatch'):
        serializer.prepare(research, output, technical_commit='test', materialized_at='test')
    assert not output.exists()
    output.mkdir()
    marker = output / 'keep'
    marker.write_bytes(b'keep')
    with pytest.raises(FileExistsError):
        serializer.prepare(research, output, technical_commit='test', materialized_at='test')
    assert marker.read_bytes() == b'keep'


def fabricated_plan(tmp_path, monkeypatch, duplicate=False):
    research = tmp_path / 'research'
    research.mkdir()
    snapshot = b'{"location":{}}'
    (research / 'source.json').write_bytes(snapshot)
    bases, families, cases = [], [], []
    for i in range(6):
        base_id, family_id = f'BT-FABRICATED-{i}', f'CF-FABRICATED-{i}'
        children = [f'FABRICATED-{i}-A', f'FABRICATED-{i}-B']
        bases.append({'base_template_id': base_id, 'basis_kind': 'CONTRACT_DERIVED',
                      'api': 'fabricated', 'source_ids': ['source'],
                      'schema_pointers': ['/location'], 'construction_family_id': family_id,
                      'base_group_id': f'BG-FABRICATED-{i}', 'structural_pattern_group_id': 'SG-FABRICATED',
                      'field_specification': [field('', 'integer', literal=17 if duplicate else i + 17)],
                      'closed_recipe': 'Fabricated serializer probe', 'base_status': 200,
                      'base_content_type': 'application/json', 'natural_request_reason': 'FABRICATED'})
        families.append({'family_id': family_id, 'primary_case_ids': children, 'scored_base_case_id': None})
        cases.extend({'case_id': c, 'base_template_id': base_id} for c in children)
    plan = {'sources': [{'id': 'source', 'path': 'source.json', 'sha256': serializer.sha(snapshot), 'bytes': len(snapshot)}],
            'base_templates': bases, 'families': families, 'primary_candidates': cases,
            'finite_priority_order': [c['case_id'] for c in cases],
            'contracts': {'fabricated': {'source_id': 'source', 'operation': {'method': 'post', 'path': '/fabricated'},
                                        'response_map_pointer': '/location', 'sha256': serializer.sha(snapshot)}},
            'serialization_for_later': {'encoding': 'UTF-8'}, 'natural_evidence': []}
    path = research / serializer.PLAN_PATH
    path.parent.mkdir()
    path.write_bytes(serializer.document(plan))
    path.with_suffix('.md').write_bytes(b'Fabricated plan')
    monkeypatch.setattr(serializer, 'PLAN_HASH', serializer.sha(path.read_bytes()))
    monkeypatch.setattr(serializer, 'MD_HASH', serializer.sha(path.with_suffix('.md').read_bytes()))
    return research


def test_base_only_tree_reproduces_every_byte(tmp_path, monkeypatch):
    research = fabricated_plan(tmp_path, monkeypatch)
    before = {str(p): p.read_bytes() for p in research.rglob('*') if p.is_file()}
    outputs = [tmp_path / 'first', tmp_path / 'second']
    for output in outputs:
        manifest = serializer.prepare(research, output, technical_commit='fabricated', materialized_at='fixed')
        assert manifest['base_count'] == 6 and manifest['final_candidate_count'] == 0
        for entry in manifest['bases']:
            metadata = json.loads((output / entry['metadata']['path']).read_bytes())
            assert metadata['state'] == serializer.STATE
            assert metadata['final_candidate_materialized'] is False
            for record in metadata['artifacts'].values():
                serializer.bound_bytes(output / record['path'], record['sha256'], record['bytes'])
    trees = [{str(p.relative_to(o)): p.read_bytes() for p in o.rglob('*') if p.is_file()} for o in outputs]
    assert trees[0] == trees[1] and len(trees[0]) == 31
    assert before == {str(p): p.read_bytes() for p in research.rglob('*') if p.is_file()}


def test_duplicate_bases_hold_without_writing(tmp_path, monkeypatch):
    research = fabricated_plan(tmp_path, monkeypatch, duplicate=True)
    output = tmp_path / 'output'
    with pytest.raises(ValueError, match='identical base bodies'):
        serializer.prepare(research, output, technical_commit='fabricated', materialized_at='fixed')
    assert not output.exists()
