"""Version-1 JSON transport: sorted keys, ASCII escapes, compact separators, LF."""
from decimal import Decimal
from hashlib import sha256
import json


class Blocked(ValueError):
    """Unresolved evidence/configuration; never a model outcome or retry grant."""


def check(condition, code):
    if not condition:
        raise Blocked(code)


def digest(raw):
    return sha256(raw).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('DUPLICATE_KEY')
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError('NON_JSON_NUMBER')


def loads(raw):
    # Decimal prevents rounding source contract assertions during extraction.
    return json.loads(raw, object_pairs_hook=unique_object, parse_float=Decimal,
                      parse_constant=invalid_constant)


def encode(value):
    def emit(node):
        if isinstance(node, Decimal):
            check(node.is_finite(), 'NON_JSON_NUMBER')
            return str(node)
        if isinstance(node, dict):
            check(all(type(k) is str for k in node), 'NON_STRING_KEY')
            return '{' + ','.join(json.dumps(k, ensure_ascii=True) + ':' + emit(node[k])
                                  for k in sorted(node)) + '}'
        if isinstance(node, (list, tuple)):
            return '[' + ','.join(emit(x) for x in node) + ']'
        return json.dumps(node, ensure_ascii=True, separators=(',', ':'), allow_nan=False)
    return (emit(value) + '\n').encode('ascii')
