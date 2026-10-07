"""Read-only, integrity-checked case evidence for the interactive terminal."""
from base64 import b64encode
from contextlib import nullcontext
from hashlib import sha256
import json

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from .interactive_menu import Back, choose
from .live_presenter import describe_case, reference_vector, service_name
from .persistence.database import pointer
from .terminal import clean
from .web.queries import DataUnavailable, NotFound, WebQueries


CATEGORIES = (('c1', 'C1 Status'), ('c2', 'C2 Media Type'), ('c3', 'C3 Body Schema'))


def _query(repo):
    return repo if hasattr(repo, '_file') else WebQueries(repo.cn)


def _text(raw):
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return 'Non-UTF-8 bytes; exact base64:\n'+b64encode(raw).decode('ascii')


def _source(query, file_id, source_pointer):
    if file_id is None:
        return None
    try:
        return pointer(json.loads(query._file(file_id)), source_pointer or '')
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise DataUnavailable('The persisted source record is unavailable or invalid.') from exc


def _artifact(query, file_id, label, *, source_pointer=None, expected_hash=None):
    if file_id is None:
        return None
    try:
        record = query._one('SELECT id,name,sha256,size_bytes FROM dbo.files WHERE id=?', file_id)
    except NotFound:
        return None
    raw = query._file(file_id)  # Existing archive integrity check is mandatory.
    if expected_hash is not None and sha256(raw).hexdigest() != expected_hash:
        raise DataUnavailable('The associated artifact failed its integrity check.')
    content = _text(raw)
    if source_pointer is not None:
        content = json.dumps(_source(query, file_id, source_pointer), ensure_ascii=False, indent=2)
    return dict(label=label, content=content, archive_name=record['name'],
                sha256=record['sha256'], size_bytes=record['size_bytes'], source_pointer=source_pointer)


def _by_hash(query, expected_hash, label):
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        return None
    records = query._rows('SELECT id FROM dbo.files WHERE sha256=?', expected_hash)
    return _artifact(query, records[0]['id'], label, expected_hash=expected_hash) if len(records) == 1 else None


def _associated_files(query, metadata):
    """Recognize actual capture/final-package bindings, never guessed local paths."""
    if not isinstance(metadata, dict):
        return []
    result = []
    candidate = metadata.get('original_candidate')
    if isinstance(candidate, dict):
        for path_key, hash_key, label in (
            ('input_evidence_file', 'input_sha256', 'Original input file'),
            ('request_evidence_file', 'request_sha256', 'Original API request body'),
        ):
            # Require both the explicit provenance association and exact content identity.
            if candidate.get(path_key):
                result.append(_by_hash(query, candidate.get(hash_key), label))
    if metadata.get('format') == 'service-capture-v1':
        for name, id_key, hash_key, label in (
            ('source_input', 'file_id', 'sha256', 'Original input file'),
            ('request', 'body_file_id', 'body_sha256', 'Original API request body'),
        ):
            association = metadata.get(name)
            if isinstance(association, dict) and association.get(hash_key):
                result.append(_artifact(query, association.get(id_key), label,
                                        expected_hash=association[hash_key]))
    return [item for item in result if item is not None]


def load_case(repo, row):
    """Resolve an exact dataset membership or an explicit case/reference pair."""
    query = _query(repo)
    if row.get('case_id') is not None and row.get('reference_id') is not None:
        case_id, reference_id = row['case_id'], row['reference_id']
        case_code = row.get('case_code') or row.get('case')
    else:
        member_id = row.get('dataset_case_id', row.get('id'))
        member = query._one('SELECT case_id,reference_id,case_code FROM dbo.dataset_cases WHERE id=?', member_id)
        case_id, reference_id, case_code = member['case_id'], member['reference_id'], member['case_code']
    stored = query._one('''SELECT tc.id,tc.native_case_id,tc.source_file_id,tc.source_pointer,
        tc.origin,tc.description,api.name AS service,op.http_method AS method,op.path_template AS path,
        ac.file_id AS contract_file_id,res.status_code,res.content_type,res.body_file_id
        FROM dbo.test_cases tc JOIN dbo.api_operations op ON op.id=tc.operation_id
        JOIN dbo.api_contracts ac ON ac.id=op.contract_id JOIN dbo.apis api ON api.id=ac.api_id
        JOIN dbo.responses res ON res.id=tc.response_id WHERE tc.id=?''', case_id)
    reference = query._one('SELECT * FROM dbo.reference_results WHERE id=? AND case_id=?', reference_id, case_id)
    metadata = _source(query, stored['source_file_id'], stored['source_pointer'])
    reference_metadata = _source(query, reference.get('source_file_id'), reference.get('source_pointer'))
    view = dict(stored, case_code=case_code or stored['native_case_id'], reference=reference,
                metadata=metadata, reference_metadata=reference_metadata)
    artifacts = [
        _artifact(query, stored.get('body_file_id'), 'Observed response body'),
        _artifact(query, stored.get('contract_file_id'), 'OpenAPI contract'),
        *_associated_files(query, metadata),
        _artifact(query, reference.get('source_file_id'), 'Reference / explanation',
                  source_pointer=reference.get('source_pointer') or ''),
        _artifact(query, stored.get('source_file_id'), 'Case provenance',
                  source_pointer=stored.get('source_pointer') or ''),
    ]
    return view, [item for item in artifacts if item is not None]


def render_case_details(console, row):
    reference = row.get('reference')
    vector = reference_vector(reference)
    values = reference if isinstance(reference, dict) else dict(zip(('c1', 'c2', 'c3'), reference or []))
    overall = ('✓ CONFORMING', 'green') if vector == 'PPP' else (
        ('✗ INCONSISTENT', 'red') if vector in ('FNN', 'PFN', 'PPF') else ('⚠ UNAVAILABLE', 'yellow'))
    summary = Table.grid(padding=(0, 2))
    for label, value in (
        ('Case', row.get('case_code') or row.get('native_case_id') or 'Unavailable'),
        ('Service / operation', service_name(row)+' / '+str(row.get('method', '?')).upper()+' '+str(row.get('path', '?'))),
        ('HTTP status', row.get('status_code', 'Unavailable')),
        ('Content-Type', row.get('content_type') or 'Not recorded'),
        ('Reference vector', vector),
    ):
        summary.add_row(Text(label, style='bold'), Text(clean(value)))
    summary.add_row(Text('Overall reference', style='bold'), Text(*overall))
    checks = Table(box=box.SIMPLE, header_style='bold cyan', padding=(0, 1))
    checks.add_column('Check')
    checks.add_column('Reference')
    for key, label in CATEGORIES:
        value = values.get(key)
        display = {'PASS': 'PASS', 'FAIL': 'FAIL', 'NOT_APPLICABLE': 'N/A'}.get(value, 'Unavailable')
        style = {'PASS': 'green', 'FAIL': 'red', 'NOT_APPLICABLE': 'dim'}.get(value, 'yellow')
        checks.add_row(label, Text(display, style=style))
    console.print(Panel(Group(summary, checks), title=Text('Case details', style='bold cyan'),
                        border_style='cyan', width=min(console.width, 100)))
    console.print(Text(describe_case(row)['description'], style='dim'))


def view_artifact(console, artifact):
    content = clean(artifact['content'])
    try:
        json.loads(artifact['content'])
        lexer = 'json'
    except (ValueError, TypeError):
        lexer = 'text'
    with console.pager(styles=True) if console.is_terminal else nullcontext():
        console.print(Text(artifact['label'], style='bold cyan'))
        console.print(Syntax(content, lexer, theme='ansi_dark', word_wrap=True,
                             background_color='default'))


def artifact_details(console, artifact):
    """No filesystem location is invented for database archive bytes."""
    summary = Table(box=box.ROUNDED, show_header=False, width=min(console.width, 100))
    summary.add_column('Field', no_wrap=True)
    summary.add_column('Value', overflow='fold')
    for label, value in (
        ('Storage', 'Read-only database archive'), ('Archive name', artifact['archive_name']),
        ('SHA-256', artifact['sha256']), ('Bytes', artifact['size_bytes']),
    ):
        summary.add_row(Text(label, style='bold'), Text(clean(value)))
    if artifact.get('source_pointer') is not None:
        summary.add_row('Source pointer', Text(clean(artifact['source_pointer'] or '(document root)')))
    console.print(summary)


def show_files(console, artifacts, read):
    if not artifacts:
        console.print('No associated files are available.', style='yellow')
        return
    while True:
        try:
            artifact = choose(console, 'Files / evidence', artifacts, lambda item: item['label'], read,
                              explanation='Select a file to view. Read-only.',
                              details=lambda item: artifact_details(console, item))
        except Back:
            return
        view_artifact(console, artifact)


def show_case_details(repo, row, console, read):
    view, artifacts = load_case(repo, row)
    render_case_details(console, view)
    show_files(console, artifacts, read)


def show_run_case_files(repo, detail, console, read):
    query = _query(repo)
    view, artifacts = load_case(query, dict(detail['run'], case_code=detail.get('case') or detail['run'].get('case')))
    for attempt in detail.get('attempts', []):
        label = 'Raw model response'+(f" · attempt {attempt['attempt']}" if len(detail['attempts']) > 1 else '')
        artifact = _artifact(query, attempt.get('response_file_id'), label)
        if artifact is not None:
            artifacts.append(artifact)
    render_case_details(console, view)
    show_files(console, artifacts, read)
