"""Development-only construction under research fault_model_v1.md §§2–4.

Family intent is an admission check AFTER independent reference measurement.
This module neither releases cases nor assigns split membership.
"""
from dataclasses import dataclass, replace
from enum import StrEnum
import hashlib
import json

from . import oracle
from .models import OracleResult, State


_BINDINGS = {
    'edx': ('/edx/validation/body',
            '4fb9c2bf81b401463dcd66f463c214a3019b75b48f0a88db1cf541a770ea4fbc'),
    'htts': ('/resistance/validation/file',
             '084b2d72929226f0984cda1ce7758c8e7d9fb1aa7e1001e308160da440828e42'),
}
_CONFORMANT = (State.PASS,) * 3


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ContractSnapshot:
    api: str
    raw: bytes

    def __post_init__(self):
        if (self.api not in _BINDINGS or type(self.raw) is not bytes
                or self.sha256 != _BINDINGS[self.api][1]):
            raise ValueError('An unchanged qualified contract snapshot is required')

    @property
    def sha256(self) -> str:
        return _sha(self.raw)

    @property
    def operation_path(self) -> str:
        return _BINDINGS[self.api][0]


@dataclass(frozen=True)
class Response:
    status: int
    content_type: str | None
    body: bytes

    def __post_init__(self):
        if type(self.body) is not bytes:
            raise TypeError('Immutable raw body bytes are required')
        if type(self.status) is not int:
            raise TypeError('Integer HTTP status is required')
        if self.content_type is not None and type(self.content_type) is not str:
            raise TypeError('Content-Type must be a string or None')

    @property
    def sha256(self) -> str:
        # Versioned, unambiguous envelope binds all three observed layers.
        envelope = ['response-v1', self.status, self.content_type, self.body.hex()]
        return _sha(json.dumps(envelope, separators=(',', ':')).encode('utf-8'))


class Origin(StrEnum):
    NATURAL = 'natural_observation'
    CONTROL = 'synthetic_conformant_control'
    INCONSISTENCY = 'synthetic_inconsistency'


@dataclass(frozen=True)
class Observation:
    """Caller-supplied archive provenance; no acquisition or wire parsing."""
    source: str
    request: bytes
    response: bytes

    def __post_init__(self):
        if (type(self.source) is not str or not self.source.strip()
                or type(self.request) is not bytes or type(self.response) is not bytes):
            raise ValueError('Archive source and raw request/response bytes are required')


@dataclass(frozen=True)
class BodyEdit:
    """One UTF-8 byte splice; unrelated body bytes remain unchanged."""
    start: int
    end: int
    replacement: bytes

    def apply(self, raw: bytes) -> bytes:
        return raw[:self.start] + self.replacement + raw[self.end:]


@dataclass(frozen=True)
class Transformation:
    family: str | None
    variant: str
    parameters: tuple[tuple[str, str], ...] = ()
    body_edit: BodyEdit | None = None


@dataclass(frozen=True)
class DevelopmentCase:
    case_id: str
    contract: ContractSnapshot
    response: Response
    origin: Origin
    result: OracleResult
    transformation: Transformation | None = None
    parent: 'DevelopmentCase | None' = None
    before: OracleResult | None = None
    observation: Observation | None = None

    @property
    def parent_sha256(self) -> str | None:
        return self.parent.response.sha256 if self.parent else None


class ConstructionRejected(ValueError):
    """Admission failed; measured candidate/parent evidence is retained."""

    def __init__(self, code: str, *, candidate: DevelopmentCase | None = None,
                 parent: DevelopmentCase | None = None, before: OracleResult | None = None):
        self.code = code
        self.candidate = candidate
        self.parent = parent
        self.before = before
        super().__init__(code)


def _measure(contract: ContractSnapshot, response: Response) -> OracleResult:
    # Deliberately no case, origin, family, intent, expected vector or ID argument.
    return oracle.evaluate_response(
        contract=json.loads(contract.raw), operation_path=contract.operation_path,
        method='post', status=response.status, content_type=response.content_type,
        body=response.body,
    )


def _check_id(case_id: str, parent: DevelopmentCase | None = None):
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError('A nonempty development case ID is required')
    while parent is not None:
        if case_id == parent.case_id:
            raise ValueError('A derivative must have a distinct case ID from its ancestors')
        parent = parent.parent


def observe(case_id: str, contract: ContractSnapshot, response: Response,
            observation: Observation) -> DevelopmentCase:
    """Label an archived natural observation as-is, including inconsistent ones."""
    _check_id(case_id)
    if not isinstance(observation, Observation):
        raise TypeError('Natural observations require archive provenance')
    return DevelopmentCase(case_id, contract, response, Origin.NATURAL,
                           _measure(contract, response), observation=observation)


def construct_parent(case_id: str, contract: ContractSnapshot, response: Response,
                     *, construction: str) -> DevelopmentCase:
    """Check explicit synthetic parent bytes; never repair them into conformance."""
    _check_id(case_id)
    if not isinstance(construction, str) or not construction.strip():
        raise ValueError('A construction description is required')
    candidate = DevelopmentCase(
        case_id, contract, response, Origin.CONTROL, _measure(contract, response),
        Transformation(None, 'explicit_parent', (('construction', construction),)),
    )
    if candidate.result.vector != _CONFORMANT:
        raise ConstructionRejected('NONCONFORMANT_PARENT', candidate=candidate)
    return candidate


# Concrete boundary shapes in fault_model_v1.md §4 (Q/S examples); these are
# construction templates and test material, never scored evaluation cases.
_CONTROLS = {
    ('K01', 'omitted'): ('edx', 200, b'{}'),
    ('K01', 'integer_code'): ('edx', 200, b'{"code":500}'),
    ('K01', 'nullable'): ('edx', 200, b'{"message":null,"data":null}'),
    ('K01', 'nested_strings'): ('edx', 200, b'{"data":[{"key":"a","value":"b"}]}'),
    ('K01', 'nested_optional_nullable'): ('edx', 200,
        b'{"code":0,"message":"ok","warning":null,"mode":null,"data":[{}, {"key":null,"value":null}]}'),
    ('K01', 'charset'): ('edx', 200, b'{"code":0}'),
    ('K02', 'null'): ('htts', 200, b'null'),
    ('K02', 'array'): ('htts', 200, b'[1,"x"]'),
    ('K02', 'object'): ('htts', 200, b'{"detail":123}'),
    ('K03', 'omitted'): ('htts', 422, b'{}'),
    ('K03', 'empty_detail'): ('htts', 422, b'{"detail":[]}'),
    ('K03', 'string_locations'): ('htts', 422,
        b'{"detail":[{"loc":["body","file"],"msg":"Field required","type":"missing","input":null}]}'),
    ('K03', 'integer_location_extras'): ('htts', 422,
        b'{"detail":[{"loc":[0],"msg":"x","type":"x","extra":1}],"extra":true}'),
}


def construct_control(case_id: str, contract: ContractSnapshot, family: str,
                      variant: str) -> DevelopmentCase:
    """Construct one admitted control shape and measure its actual conformance."""
    _check_id(case_id)
    if (family, variant) not in _CONTROLS:
        raise ConstructionRejected('UNAPPROVED_CONTROL_VARIANT')
    api, status, body = _CONTROLS[family, variant]
    if api != contract.api:
        raise ConstructionRejected('INAPPLICABLE_FAMILY')
    media = 'application/json; charset=utf-8' if variant == 'charset' else 'application/json'
    response = Response(status, media, body)
    candidate = DevelopmentCase(
        case_id, contract, response, Origin.CONTROL, _measure(contract, response),
        Transformation(family, variant, (('construction', 'literal UTF-8 template'),)),
    )
    if candidate.result.vector != _CONFORMANT:
        raise ConstructionRejected('UNEXPECTED_CONTROL_PROFILE', candidate=candidate)
    return candidate


def _children(text: str, start: int):
    """Locate members using the standard JSON decoder, after oracle preflight.

    This locates edit spans only; it does not validate JSON or schemas.
    Yield (key/index, member start, value start, value end, preceding comma).
    """
    decoder = json.JSONDecoder()
    is_object = text[start] == '{'
    pos, index, comma = start + 1, 0, None
    while True:
        while text[pos] in ' \t\r\n':
            pos += 1
        if text[pos] in '}]':
            return
        member_start = pos
        if is_object:
            key, pos = decoder.raw_decode(text, pos)
            while text[pos] in ' \t\r\n:':
                pos += 1
        else:
            key = index
        value_start = pos
        _, pos = decoder.raw_decode(text, pos)
        yield key, member_start, value_start, pos, comma
        while text[pos] in ' \t\r\n':
            pos += 1
        if text[pos] != ',':
            return
        comma = pos
        pos += 1
        index += 1


def _locate(text: str, path: tuple[str | int, ...]) -> tuple[int, int]:
    start = len(text) - len(text.lstrip())
    _, end = json.JSONDecoder().raw_decode(text, start)
    for part in path:
        matches = [entry for entry in _children(text, start) if entry[0] == part]
        if not matches:
            raise ConstructionRejected('MISSING_MUTATION_TARGET')
        _, _, start, end, _ = matches[0]
    return start, end


def _body_edit(body: bytes, path: tuple[str | int, ...], action: str,
               value: bytes) -> BodyEdit:
    text = body.decode('utf-8')
    start, end = _locate(text, path)
    if action == 'add':
        start = end - 1
        end = start
        # Insert a member into an object, preserving even interior whitespace.
        value = (b',' if list(_children(text, _locate(text, path)[0])) else b'') + value
    elif action == 'remove':
        container_start, _ = _locate(text, path[:-1])
        members = list(_children(text, container_start))
        position = next(i for i, member in enumerate(members) if member[0] == path[-1])
        _, member_start, _, end, comma = members[position]
        start = comma if comma is not None else member_start
        if comma is None and len(members) > 1:
            end = members[1][1]
    return BodyEdit(len(text[:start].encode('utf-8')), len(text[:end].encode('utf-8')), value)


_VARIANTS = {
    'F01': ('status_500',), 'F02': ('undeclared_media',),
    'F03': ('string', 'boolean', 'null'), 'F04': ('root', 'nested'),
    'F05': ('integer_key',), 'F06': ('remove_msg',), 'F07': ('string_loc',),
    'F08': ('null', 'integer'), 'F09': ('broken_json',),
}


def mutate(case_id: str, parent: DevelopmentCase, family: str, *,
           variant: str | None = None, item_index: int | None = None) -> DevelopmentCase:
    """Apply one bounded fault, retaining parent and actual before/after results.

    An unsuccessful admission raises with its measured candidate where available.
    No fault IDs or expected vectors ever enter the reference measurement.
    """
    _check_id(case_id, parent)
    if family not in _VARIANTS:
        raise ConstructionRejected('UNAPPROVED_FAULT_FAMILY', parent=parent)
    variant = _VARIANTS[family][0] if variant is None else variant
    if variant not in _VARIANTS[family]:
        raise ConstructionRejected('UNAPPROVED_FAULT_VARIANT', parent=parent)
    before = _measure(parent.contract, parent.response)

    def reject(code):
        raise ConstructionRejected(code, parent=parent, before=before)

    if before.vector != _CONFORMANT:
        reject('NONCONFORMANT_PARENT')
    api, original = parent.contract.api, parent.response
    if original.content_type != 'application/json':
        reject('FAULT_PARENT_REQUIRES_EXACT_JSON_MEDIA')
    if (api == 'edx' and original.status != 200) or (api == 'htts' and original.status not in (200, 422)):
        reject('INAPPLICABLE_BRANCH')
    if family in ('F03', 'F04', 'F05') and api != 'edx':
        reject('INAPPLICABLE_FAMILY')
    if family in ('F06', 'F07', 'F08') and (api != 'htts' or original.status != 422):
        reject('INAPPLICABLE_FAMILY')
    indexed = family in ('F05', 'F06', 'F07') or (family == 'F04' and variant == 'nested')
    if item_index is not None and (not indexed or type(item_index) is not int or item_index < 0):
        reject('INVALID_ITEM_INDEX')
    index = 0 if item_index is None else item_index
    body = json.loads(original.body)
    path, action, value = (), 'replace', b''
    params = ()
    edit = None
    if indexed:
        field = 'data' if api == 'edx' else 'detail'
        items = body.get(field) if isinstance(body, dict) else None
        if not isinstance(items, list) or index >= len(items) or not isinstance(items[index], dict):
            reject('MISSING_MUTATION_TARGET')
        item = items[index]
        path = (field, index)
        params = (('item_index', str(index)),)
    if family == 'F01':
        response = replace(original, status=500)
        params = (('status', '500'),)
    elif family == 'F02':
        media = 'application/xml' if api == 'edx' else 'text/plain'
        response = replace(original, content_type=media)
        params = (('content_type', media),)
    else:
        if family == 'F03':
            if type(body.get('code')) is not int:
                reject('INTEGER_CODE_PARENT_REQUIRED')
            path = ('code',)
            value = {'string': b'"0"', 'boolean': b'false', 'null': b'null'}[variant]
        elif family == 'F04':
            if variant == 'nested' and item != {}:
                reject('EMPTY_DATA_ITEM_REQUIRED')
            if variant == 'root' and 'Code' in body:
                reject('ADDITIONAL_KEY_ALREADY_PRESENT')
            action = 'add'
            value = b'"Code":0' if variant == 'root' else b'"extra":true'
        elif family == 'F05':
            if not isinstance(item.get('key'), str):
                reject('STRING_KEY_PARENT_REQUIRED')
            path += ('key',)
            value = b'7'
        elif family == 'F06':
            path += ('msg',)
            action = 'remove'
        elif family == 'F07':
            path += ('loc',)
            value = b'"file"'
        elif family == 'F08':
            if not isinstance(body.get('detail'), list):
                reject('ARRAY_DETAIL_PARENT_REQUIRED')
            path = ('detail',)
            value = b'null' if variant == 'null' else b'123'
        elif family == 'F09':
            edit = BodyEdit(0, len(original.body), b'{broken')
        if edit is None:
            edit = _body_edit(original.body, path, action, value)
        response = replace(original, body=edit.apply(original.body))
        params += (('action', action), ('path', json.dumps(path)))
    after = _measure(parent.contract, response)
    candidate = DevelopmentCase(
        case_id, parent.contract, response,
        Origin.CONTROL if after.vector == _CONFORMANT else Origin.INCONSISTENCY,
        after, Transformation(family, variant, params, edit), parent, before,
    )
    if response == original:
        raise ConstructionRejected('NO_OP_MUTATION', candidate=candidate, parent=parent, before=before)
    if after.vector == _CONFORMANT:
        raise ConstructionRejected('INEFFECTIVE_MUTATION', candidate=candidate, parent=parent, before=before)
    expected = ((State.FAIL, State.NOT_APPLICABLE, State.NOT_APPLICABLE) if family == 'F01'
                else (State.PASS, State.FAIL, State.NOT_APPLICABLE) if family == 'F02'
                else (State.PASS, State.PASS, State.FAIL))
    if after.vector != expected:
        raise ConstructionRejected('UNEXPECTED_FAULT_PROFILE', candidate=candidate, parent=parent, before=before)
    representation_failure = any(d.code == 'INVALID_JSON_REPRESENTATION' for d in after.diagnostics)
    if representation_failure != (family == 'F09'):
        raise ConstructionRejected('UNEXPECTED_FAULT_DIAGNOSTIC', candidate=candidate, parent=parent, before=before)
    return candidate
