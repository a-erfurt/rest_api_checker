"""Executable library probes; implementation evidence, not human annotations."""
import pytest
from jsonschema import Draft202012Validator
from openapi_schema_validator import OAS30Validator, OAS31Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4, DRAFT202012


@pytest.mark.parametrize('validator', [OAS30Validator, OAS31Validator, Draft202012Validator])
@pytest.mark.parametrize('schema,instance,expected', [
    ({'type': 'integer'}, False, False),
    ({'type': 'integer'}, '0', False),
    ({'type': 'integer'}, 0, True),
    ({'type': 'object', 'additionalProperties': False}, {'extra': 1}, False),
    ({'type': 'object', 'required': ['msg']}, {}, False),
    ({'type': 'array', 'items': {'type': 'string'}}, ['x'], True),
    ({'type': 'array', 'items': {'type': 'string'}}, [7], False),
    ({'anyOf': [{'type': 'string'}, {'type': 'integer'}]}, 0, True),
    ({'anyOf': [{'type': 'string'}, {'type': 'integer'}]}, 'file', True),
    ({'anyOf': [{'type': 'string'}, {'type': 'integer'}]}, False, False),
    ({}, None, True),
    ({}, [1, 'x'], True),
])
def test_structural_features(validator, schema, instance, expected):
    assert validator(schema).is_valid(instance) is expected


@pytest.mark.parametrize('validator,nullable_expected', [
    (OAS30Validator, True), (OAS31Validator, False), (Draft202012Validator, False),
])
def test_nullable_dialect_difference(validator, nullable_expected):
    assert validator({'type': 'string', 'nullable': True}).is_valid(None) is nullable_expected


@pytest.mark.parametrize('validator,dialect', [(OAS30Validator, DRAFT4), (OAS31Validator, DRAFT202012)])
def test_nested_local_refs(validator, dialect):
    document = {'components': {'schemas': {
        'Root': {'type': 'array', 'items': {'$ref': '#/components/schemas/Item'}},
        'Item': {'type': 'object', 'properties': {'key': {'type': 'string'}}, 'additionalProperties': False},
    }}}
    registry = Registry().with_resource('urn:spike:contract', Resource(document, dialect))
    v = validator({'$ref': 'urn:spike:contract#/components/schemas/Root'}, registry=registry)
    assert v.is_valid([{'key': 'a'}])
    assert not v.is_valid([{'key': 7}])
    assert not v.is_valid([{'extra': True}])
