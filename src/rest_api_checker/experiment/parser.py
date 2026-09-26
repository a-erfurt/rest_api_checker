"""D03/D10 syntax-only final-content parser. Never enforces reference vectors."""
from dataclasses import dataclass
from pathlib import Path
import json

from .encoding import digest, invalid_constant, unique_object

VERSION = 'strict-output-v1'
VERDICTS = ('PASS', 'FAIL', 'NOT_APPLICABLE')


@dataclass(frozen=True, slots=True)
class ParseResult:
    status: str
    code: str
    path: str = ''
    prediction: dict | None = None


def artifact_hash():
    root = Path(__file__).parent
    return digest(b''.join(name.encode() + b'\0' + (root/name).read_bytes() + b'\0'
                          for name in ('parser.py', 'encoding.py', 'output_schema_v1.json')))


def parse(content: str) -> ParseResult:
    def failure(code, path=''):
        return ParseResult('PARSER_FAILURE', code, path)
    if type(content) is not str:
        return failure('FINAL_CONTENT_NOT_STRING')
    try:
        value = json.loads(content, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except json.JSONDecodeError:
        return failure('INVALID_JSON')
    except ValueError as exc:
        return failure(str(exc))
    except RecursionError:
        return failure('JSON_NESTING_LIMIT')
    if type(value) is not dict:
        return failure('TOP_LEVEL_NOT_OBJECT')
    if set(value) != {'c1', 'c2', 'c3'}:
        return failure('CATEGORY_FIELDS')
    prediction = {}
    for category in ('c1', 'c2', 'c3'):
        item = value[category]
        path = '/' + category
        if type(item) is not dict or set(item) != {'verdict', 'reason'}:
            return failure('CATEGORY_MEMBERS', path)
        if type(item['verdict']) is not str or item['verdict'] not in VERDICTS:
            return failure('ILLEGAL_VERDICT', path + '/verdict')
        if type(item['reason']) is not str or not item['reason'].strip():
            return failure('BLANK_OR_NONSTRING_REASON', path + '/reason')
        prediction[category] = item['verdict']
        prediction[category + '_reason'] = item['reason']
    return ParseResult('VALID_OUTPUT', 'ACCEPTED', prediction=prediction)
