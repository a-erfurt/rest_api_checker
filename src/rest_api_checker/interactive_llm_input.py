"""Read-only views of prepared / archived LLM request bytes, never reconstruction."""
import re

import pyodbc
from rich.text import Text

from . import terminal
from .experiment.encoding import digest, encode, loads
from .interactive_menu import Back, choose
from .persistence.database import IntegrityViolation
from .persistence.importer import PROMPT_HASHES
from .web.queries import DataUnavailable, NotFound


# Display-only filtering, including secrets inside JSON-encoded message/body strings.
# Never write the filtered representation back into a request or archive.
_PRIVATE_KEY = re.compile(r'(?is)-----BEGIN (?:[A-Z ]*PRIVATE KEY)-----.*?-----END (?:[A-Z ]*PRIVATE KEY)-----')
_SECRET_NAME = r'(?:authorization|proxy[-_]?authorization|(?:set[-_]?)?cookie|password|passwd|pwd|(?:client[-_]?)?secret|credential[s]?|(?:x[-_]?)?api[-_]?key|(?:access[-_]?|refresh[-_]?|id[-_]?)?token|session[-_]?id|csrf[-_]?token|private[-_]?key|(?:aws[-_]?)?secret[-_]?access[-_]?key)'
_SECRET_KEY = re.compile(_SECRET_NAME, re.I)
_ASSIGNMENT = re.compile(r'(?im)(\b'+_SECRET_NAME+r'\b[\"\']?\s*[:=]\s*)(\"(?:[^\"\\]|\\.)*\"|\'(?:[^\'\\]|\\.)*\'|[^\s,;&<>]+(?: [^\r\n,;&<>]+)?)')
_BEARER = re.compile(r'(?i)\b(?:Bearer|Basic)\s+[A-Za-z0-9+/_.=~-]+')
_URL_AUTH = re.compile(r'(?i)(https?://)[^/\s@]+@')
_TOKEN = re.compile(r'\b(?:sk-[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b')
_REDACTED = '[REDACTED]'
_HEADER = re.compile(r'(?im)(\b(?:authorization|proxy-authorization|cookie|set-cookie)\s*:\s*)[^\r\n]*')
_XML_SECRET = re.compile(r'(?is)(<(?P<tag>'+_SECRET_NAME+r')\b[^>]*>).*?(</(?P=tag)\s*>)')


def _pretty(value):
    """Indent the canonical JSON without rounding Decimal contract assertions."""
    tokens = re.findall(r'"(?:[^"\\]|\\.)*"|[^\s{}\[\],:]+|[{}\[\],:]', encode(value).decode('ascii'))
    result, level = [], 0
    for index, token in enumerate(tokens):
        if token in ('{', '['):
            result.append(token)
            level += 1
            if tokens[index+1] not in ('}', ']'):
                result.append('\n'+'  '*level)
        elif token in ('}', ']'):
            level -= 1
            if tokens[index-1] not in ('{', '['):
                result.append('\n'+'  '*level)
            result.append(token)
        elif token == ',':
            result.append(',\n'+'  '*level)
        elif token == ':':
            result.append(': ')
        else:
            result.append(token)
    return ''.join(result)


def safe_text(text):
    """Keep non-secret text exact; report any display-only redaction explicitly."""
    def scrub(value, depth=0, *, contract=False, properties=False, private_schema=False):
        if isinstance(value, dict):
            contract = contract or (isinstance(value.get('openapi'), str) and isinstance(value.get('paths'), dict))
            result = {}
            for key, item in value.items():
                secret = bool(_SECRET_KEY.fullmatch(key))
                schema = contract and properties and isinstance(item, dict)
                if (secret and not schema or private_schema and key in ('example', 'examples', 'default', 'enum', 'const')):
                    result[key] = _REDACTED
                else:
                    result[key] = scrub(item, depth+1, contract=contract,
                        properties=contract and key in ('properties', 'schemas'), private_schema=private_schema or secret and schema)
            return result
        if isinstance(value, list):
            return [scrub(item, depth+1, contract=contract, private_schema=private_schema) for item in value]
        if not isinstance(value, str):
            return value
        try:
            nested = loads(value.encode('utf-8'))
        except (ValueError, UnicodeError, RecursionError):
            nested = None
        if isinstance(nested, (dict, list)):
            filtered = scrub(nested, depth+1)
            return value if filtered == nested else _pretty(filtered)
        value = _PRIVATE_KEY.sub(_REDACTED, value)
        value = _HEADER.sub(lambda m: m[1]+_REDACTED, value)
        value = _XML_SECRET.sub(lambda m: m[1]+_REDACTED+m[3], value)
        value = _ASSIGNMENT.sub(lambda m: m[1]+_REDACTED, value)
        value = _BEARER.sub(_REDACTED, value)
        value = _URL_AUTH.sub(lambda m: m[1]+_REDACTED+'@', value)
        return _TOKEN.sub(_REDACTED, value)
    filtered = scrub(text)
    return filtered, filtered != text


def sections(raw):
    """Project only this payload. Message strings and wire JSON remain exact."""
    payload = loads(raw)
    if (not isinstance(payload, dict) or not {'model', 'stream', 'messages', 'options'} <= set(payload)
            or set(payload) - {'model', 'stream', 'messages', 'options', 'think', 'format'}
            or not isinstance(payload['messages'], list)):
        raise ValueError('Unsupported request')
    messages = payload['messages']
    if (len(messages) != 2 or [m.get('role') for m in messages if isinstance(m, dict)] != ['system', 'user']
            or any(set(m) != {'role', 'content'} or not isinstance(m['content'], str) for m in messages)):
        raise ValueError('Unsupported messages')
    if digest(messages[0]['content'].encode('utf-8')) not in PROMPT_HASHES.values():
        raise ValueError('Unrecognized prompt')
    user = loads(messages[1]['content'].encode('utf-8'))
    if (not isinstance(user, dict) or set(user) != {'operation', 'openapi', 'observed_response'}
            or not isinstance(user['operation'], dict) or set(user['operation']) != {'method', 'path'}
            or not all(isinstance(value, str) for value in user['operation'].values())
            or not isinstance(user['openapi'], dict)
            or not isinstance(user['observed_response'], dict)
            or set(user['observed_response']) != {'status', 'content_type', 'body'}):
        raise ValueError('Unsupported input context')
    response = user['observed_response']
    if (not isinstance(response['body'], str) or type(response['status']) is not int
            or response['content_type'] is not None and not isinstance(response['content_type'], str)):
        raise ValueError('Unsupported response body')
    return [
        ('System message — prompt / evaluation rules', messages[0]['content']),
        ('Operation / HTTP status / Content-Type — from user message', _pretty(dict(
            operation=user['operation'], status=response['status'], content_type=response['content_type']))),
        ('Response body — from user message', response['body']),
        ('OpenAPI excerpt — from user message', _pretty(user['openapi'])),
        ('Complete user message', messages[1]['content']),
        ('Request options — outside messages', _pretty({k: v for k, v in payload.items() if k != 'messages'})),
        ('Complete request JSON', raw.decode('utf-8')),
    ]


def _show_section(console, label, content, read):
    # Text prevents Rich markup interpretation; clean makes terminal controls visible.
    content, redacted = safe_text(content)
    # Also neutralize C1 controls and bidi overrides that the shared clean()
    # intentionally leaves alone for other UI text. Request bytes stay untouched.
    content = ''.join(f'\\u{ord(c):04x}' if 0x80 <= ord(c) <= 0x9f or
                      ord(c) in (*range(0x202a, 0x202f), *range(0x2066, 0x206a)) else c for c in content)
    title = Text(label, style='bold cyan')
    notice = ('Secrets redacted for display; sent/stored bytes are unchanged.' if redacted else
              'From the request payload. Line wrapping / escaped control characters are display only.')
    # Plain/no-color output still needs pages when attached to a terminal.
    if not (console.is_terminal or getattr(console.file, 'isatty', lambda: False)()):
        console.print(title)
        console.print(notice, style='dim')
        console.print(Text(terminal.clean(content)))
        return
    lines = Text(terminal.clean(content)).wrap(console, max(20, console.width-2), overflow='fold')
    page_size = max(4, console.height-8)
    pages = max(1, (len(lines)+page_size-1)//page_size)
    page = 0
    while True:
        console.print(title)
        console.print(notice, style='dim')
        for line in lines[page*page_size:(page+1)*page_size]:
            console.print(line)
        console.print(f'Page {page+1}/{pages} · Enter/n next · p previous · q Back', style='dim')
        answer = read('Page: ').strip().lower()
        if answer in ('q', 'b', 'back') or not answer and page == pages-1:
            return
        if answer in ('', 'n'):
            page = min(pages-1, page+1)
        elif answer == 'p':
            page = max(0, page-1)
        else:
            console.print('Use Enter/n, p or q.')


def show_payload(console, raw, read, *, source):
    items = sections(raw)
    console.print('LLM input', style='bold cyan')
    console.print(source, style='dim')
    console.print('System = evaluation rules; user = operation, OpenAPI and observed response. '
                  'Case selection/reference metadata is not added to this view.', style='dim')
    console.print('Request SHA-256: '+digest(raw), style='dim')
    console.print(f'Request bytes: {len(raw)} · View only; no model call.', style='dim')
    while True:
        try:
            label, content = choose(console, 'Input sections', items, lambda item: item[0], read,
                explanation='Complete messages and request included. q returns to the previous screen.')
        except Back:
            return
        _show_section(console, label, content, read)


def show_plan_input(console, plan, read):
    try:
        requests = sorted(plan.requests.items())
        if not requests:
            raise ValueError('No prepared requests')
        while True:
            order, request = requests[0] if len(requests) == 1 else choose(
                console, 'Select prepared input', requests, lambda item: f'Planned run {item[0]}', read)
            show_payload(console, request.body, read,
                source=f'Prepared request {order}; not yet sent. Execution verifies these exact bytes. '
                       'Runtime template/tokenization is applied by Ollama and is not shown here.')
            if len(requests) == 1:
                return
    except Back:
        return
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        console.print('The prepared LLM input is unavailable or unsupported. No model was called by the preview.', style='yellow')


def load_run_payload(query, run_id):
    """SELECT-only read of the actual archived bytes; no prompt lookup or rebuild."""
    run = query._one('SELECT request_file_id FROM dbo.experiment_runs WHERE id=?', run_id)
    if run.get('request_file_id') is None:
        raise DataUnavailable('No stored request')
    raw = query._file(run['request_file_id'])  # SHA-256 and byte-length checked by WebQueries.
    if not isinstance(raw, bytes):
        raise DataUnavailable('Missing stored request')
    attempts = query._rows('SELECT request_file_id,started_at,result FROM dbo.run_attempts WHERE run_id=? ORDER BY attempt', run_id)
    for attempt in attempts:
        if attempt.get('request_file_id') is not None and query._file(attempt['request_file_id']) != raw:
            raise DataUnavailable('Conflicting stored requests')
    started = any(attempt.get('started_at') for attempt in attempts)
    status = ('A transport start was recorded; this alone does not prove server receipt.' if started else
              'No transport start is recorded; this payload may only have been reserved.')
    return raw, 'Stored request payload from the database archive. '+status


def show_run_input(query, run_id, console, read):
    try:
        raw, source = load_run_payload(query, run_id)
        show_payload(console, raw, read, source=source)
    except (DataUnavailable, NotFound, IntegrityViolation, pyodbc.Error, ValueError, TypeError,
            KeyError, AttributeError, UnicodeError, RecursionError, OSError):
        console.print('The stored LLM input is missing, unsupported or failed its integrity check. '
                      'No input was reconstructed.', style='yellow')
