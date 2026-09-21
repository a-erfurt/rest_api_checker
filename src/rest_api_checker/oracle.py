"""Deterministic reference labeling of one observed response artifact."""
import json
import math
import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .media_type import select_media
from .models import Diagnostic, OracleNotReady, OracleResult, State
from .schema_validation import pointer, prepare_validator, resolve_local, validate_instance

P, F, N = State.PASS, State.FAIL, State.NOT_APPLICABLE


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise OracleNotReady('DUPLICATE_JSON_NAME', key)
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f'Non-JSON numeric token: {value}')


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise OracleNotReady('UNQUALIFIED_NUMERIC_EXTREME')
    try:
        if Decimal(value) != Decimal(str(result)):
            raise OracleNotReady('UNQUALIFIED_NUMERIC_EXTREME')
    except InvalidOperation as exc:
        raise OracleNotReady('UNQUALIFIED_NUMERIC_EXTREME') from exc
    return result


def _integer(value):
    try:
        return int(value)
    except ValueError as exc:
        raise OracleNotReady('UNQUALIFIED_NUMERIC_EXTREME') from exc


def _decode(body: bytes):
    return json.loads(body.decode('utf-8'), object_pairs_hook=_unique_object,
                      parse_constant=_invalid_constant, parse_float=_finite_float, parse_int=_integer)


def _load(contract):
    if isinstance(contract, (str, Path)):
        try:
            document = _decode(Path(contract).read_bytes())
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise OracleNotReady('UNUSABLE_CONTRACT') from exc
    else:
        document = contract
    if not isinstance(document, Mapping):
        raise OracleNotReady('INVALID_CONTRACT_DOCUMENT')
    if document.get('openapi') not in {'3.0.4', '3.1.0'}:
        raise OracleNotReady('UNSUPPORTED_OPENAPI_VERSION')
    return document


def _select_response(responses, status):
    if not isinstance(responses, Mapping) or not responses:
        raise OracleNotReady('INVALID_RESPONSE_MAP')
    for key in responses:
        if not isinstance(key, str) or not (re.fullmatch(r'[1-5][0-9]{2}|[1-5]XX', key) or key == 'default' or key.startswith('x-')):
            raise OracleNotReady('INVALID_RESPONSE_KEY', str(key))
    return next((key for key in (str(status), f'{status // 100}XX', 'default') if key in responses), None)


def evaluate_response(contract: Mapping | str | Path, operation_path: str,
                      method: str, status: int, content_type: str | None,
                      body: bytes) -> OracleResult:
    """Return completed labels, or raise without labels for unsupported evidence.

    The input contains no fault metadata, expected labels, request semantics,
    model predictions or service source. Callers own contract byte-hash binding;
    the qualification suite verifies its copies before loading either contract.
    """
    if type(status) is not int or not 100 <= status <= 599:
        raise OracleNotReady('INVALID_OBSERVED_STATUS')
    if not isinstance(body, bytes):
        raise OracleNotReady('RAW_BODY_BYTES_REQUIRED')
    if not isinstance(method, str) or (method.lower(), operation_path) not in {
        ('post', '/edx/validation/body'), ('post', '/resistance/validation/file'),
    }:
        raise OracleNotReady('UNQUALIFIED_OPERATION')
    document = _load(contract)
    try:
        responses = document['paths'][operation_path][method.lower()]['responses']
    except (KeyError, TypeError, AttributeError) as exc:
        raise OracleNotReady('OPERATION_NOT_FOUND') from exc
    response_key = _select_response(responses, status)
    if response_key is None:
        return OracleResult(F, N, N, None, None, None, (Diagnostic('UNDOCUMENTED_STATUS'),))
    response = responses[response_key]
    response_pointer = '#' + pointer(('paths', operation_path, method.lower(), 'responses', response_key))
    visited = set()
    while isinstance(response, Mapping) and '$ref' in response:
        ref = response['$ref']
        if not isinstance(ref, str) or ref in visited or set(response) != {'$ref'}:
            raise OracleNotReady('UNUSABLE_RESPONSE_REFERENCE')
        visited.add(ref)
        response = resolve_local(document, ref)
        response_pointer = ref
    if not isinstance(response, Mapping):
        raise OracleNotReady('INVALID_RESPONSE_BRANCH')
    content = response.get('content')
    if not isinstance(content, Mapping) or not content:
        raise OracleNotReady('UNQUALIFIED_BODYLESS_RESPONSE')
    media_key = select_media(content, content_type)
    if media_key is None:
        return OracleResult(P, F, N, response_key, None, None, (Diagnostic('UNDECLARED_MEDIA_TYPE'),))
    if media_key.strip(' \t').lower() != 'application/json':
        raise OracleNotReady('UNQUALIFIED_REPRESENTATION', media_key)
    media = content[media_key]
    if not isinstance(media, Mapping) or 'schema' not in media:
        raise OracleNotReady('MISSING_SCHEMA')
    schema_pointer = response_pointer + pointer(('content', media_key, 'schema'))
    # Preflight before decoding: unusable contract evidence is never a body fault.
    validator = prepare_validator(document, schema_pointer)
    try:
        instance = _decode(body)
    except (UnicodeDecodeError, ValueError):
        return OracleResult(P, P, F, response_key, media_key, schema_pointer,
                            (Diagnostic('INVALID_JSON_REPRESENTATION'),))
    diagnostics = validate_instance(validator, instance)
    return OracleResult(P, P, F if diagnostics else P, response_key, media_key,
                        schema_pointer, diagnostics or (Diagnostic('SCHEMA_VALID'),))
