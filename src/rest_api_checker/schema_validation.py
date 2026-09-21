"""Version-aware schema validation with a bounded, local-only evidence profile."""
from collections.abc import Mapping

from jsonschema.exceptions import SchemaError
from openapi_schema_validator import OAS30Validator, OAS31Validator, oas30_format_checker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4, DRAFT202012

from .models import Diagnostic, OracleExecutionError, OracleNotReady

_URI = 'urn:rest-api-checker:contract'
# This is an eligibility guard, not a replacement schema validator. Unknown
# assertions must not disappear silently through a validator's annotation rules.
_COMMON = {'$ref', 'type', 'properties', 'required', 'additionalProperties',
           'items', 'anyOf', 'title', 'description', 'format'}


def pointer(parts) -> str:
    return ''.join('/' + str(p).replace('~', '~0').replace('/', '~1') for p in parts)


def resolve_local(document: Mapping, ref: str):
    if not isinstance(ref, str) or not ref.startswith('#/'):
        raise OracleNotReady('UNSUPPORTED_REFERENCE', str(ref))
    current = document
    try:
        for token in ref[2:].split('/'):
            key = token.replace('~1', '/').replace('~0', '~')
            current = current[int(key)] if isinstance(current, list) else current[key]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise OracleNotReady('UNRESOLVED_REFERENCE', ref) from exc
    return current


def prepare_validator(document: Mapping, schema_pointer: str):
    version = document.get('openapi')
    if version == '3.0.4':
        cls, dialect = OAS30Validator, DRAFT4
    elif version == '3.1.0':
        cls, dialect = OAS31Validator, DRAFT202012
    else:
        raise OracleNotReady('UNSUPPORTED_OPENAPI_VERSION', str(version))
    if 'jsonSchemaDialect' in document:
        raise OracleNotReady('UNQUALIFIED_SCHEMA_DIALECT')
    allowed = _COMMON | ({'nullable'} if version == '3.0.4' else set())

    def check(schema, active_refs=frozenset()):
        if not isinstance(schema, dict):
            raise OracleNotReady('UNSUPPORTED_SCHEMA_FORM')
        unknown = set(schema) - allowed
        if unknown:
            raise OracleNotReady('UNQUALIFIED_SCHEMA_KEYWORD', ','.join(sorted(unknown)))
        try:
            cls.check_schema(schema)
        except SchemaError as exc:
            raise OracleNotReady('INVALID_SOURCE_SCHEMA') from exc
        if 'format' in schema and not (schema.get('type') == 'integer' and schema['format'] == 'int32'):
            raise OracleNotReady('UNQUALIFIED_SCHEMA_FORMAT')
        if '$ref' in schema:
            ref = schema['$ref']
            if set(schema) != {'$ref'}:
                raise OracleNotReady('UNQUALIFIED_REFERENCE_SIBLINGS')
            if ref in active_refs:
                raise OracleNotReady('UNQUALIFIED_RECURSIVE_SCHEMA', ref)
            check(resolve_local(document, ref), active_refs | {ref})
        for child in schema.get('properties', {}).values():
            check(child, active_refs)
        if 'items' in schema:
            check(schema['items'], active_refs)
        if isinstance(schema.get('additionalProperties'), dict):
            check(schema['additionalProperties'], active_refs)
        for child in schema.get('anyOf', []):
            check(child, active_refs)

    check(resolve_local(document, schema_pointer))
    # No retrieval callback: the registry cannot fetch remote references.
    registry = Registry().with_resource(_URI, Resource(dict(document), dialect))
    # Format errors are eligibility holds below, never qualified C3 failures.
    checker = oas30_format_checker if version == '3.0.4' else None
    return cls({'$ref': _URI + schema_pointer}, registry=registry, format_checker=checker)


def validate_instance(validator, instance) -> tuple[Diagnostic, ...]:
    try:
        errors = list(validator.iter_errors(instance))
    except Exception as exc:
        raise OracleExecutionError('SCHEMA_VALIDATOR_ERROR') from exc
    if any(error.validator == 'format' for error in errors):
        raise OracleNotReady('UNQUALIFIED_FORMAT_CASE')
    if any(error.validator == 'type' and error.validator_value == 'integer'
           and isinstance(error.instance, float) and error.instance.is_integer()
           for error in errors):
        raise OracleNotReady('UNQUALIFIED_INTEGER_REPRESENTATION')
    # Schema paths are validator paths relative to the selected schema (including
    # traversed ref targets), not falsely advertised as absolute document pointers.
    return tuple(sorted(Diagnostic(
        'SCHEMA_ASSERTION_FAILED', pointer(error.absolute_path),
        pointer(error.absolute_schema_path), str(error.validator),
    ) for error in errors))
