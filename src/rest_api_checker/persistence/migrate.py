"""Explicit numbered T-SQL migrations, transactional ledger and checksum guard."""
from hashlib import sha256
from pathlib import Path
import re

from .database import lock, require, transaction

MIGRATIONS = Path(__file__).with_name('migrations')
LEDGER = '''CREATE TABLE dbo.schema_migrations (
 version INT NOT NULL PRIMARY KEY CHECK (version>0),
 name NVARCHAR(128) COLLATE Latin1_General_100_BIN2 NOT NULL,
 sha256 CHAR(64) COLLATE Latin1_General_100_BIN2 NOT NULL,
 applied_at DATETIMEOFFSET(7) NOT NULL DEFAULT SYSDATETIMEOFFSET()
);'''


def migrations(directory=MIGRATIONS):
    found = []
    for path in sorted(Path(directory).glob('*.sql')):
        match = re.fullmatch(r'(\d{3})_[a-z0-9_]+\.sql', path.name)
        require(match is not None, f'Invalid migration filename: {path.name}')
        raw = path.read_bytes()
        found.append((int(match[1]), path.name, sha256(raw).hexdigest(), raw.decode('utf-8')))
    require(found and [m[0] for m in found] == list(range(1, len(found)+1)), 'Non-contiguous migrations')
    return found


def inspect(cn):
    if cn.execute("SELECT OBJECT_ID('dbo.schema_migrations','U')").fetchval() is None:
        return []
    return [tuple(r) for r in cn.execute('SELECT version,name,sha256 FROM dbo.schema_migrations ORDER BY version')]


def verify(cn, directory=MIGRATIONS, *, complete=True):
    expected = [m[:3] for m in migrations(directory)]
    actual = inspect(cn)
    require(actual == expected[:len(actual)] and len(actual) <= len(expected), 'Migration history/checksum mismatch')
    require(not complete or actual == expected, 'Schema version incompatible; explicit migration required')
    return len(actual)


def apply(cn, *, expected_current, directory=MIGRATIONS, lock_timeout_ms=10000):
    ordered = migrations(directory)  # Read once; apply exactly the bytes whose hashes are recorded.
    with transaction(cn):
        lock(cn, 'rest_api_checker:migrations', lock_timeout_ms)
        actual = inspect(cn)
        require(actual == [m[:3] for m in ordered[:len(actual)]] and len(actual) <= len(ordered),
                'Migration history/checksum mismatch')
        require(len(actual) == expected_current, 'Unexpected current schema version')
        if not actual and cn.execute("SELECT OBJECT_ID('dbo.schema_migrations','U')").fetchval() is None:
            require(cn.execute("SELECT COUNT(*) FROM sys.tables WHERE is_ms_shipped=0").fetchval() == 0,
                    'Unledgered nonempty database; refusing initialization')
            cn.execute(LEDGER)
        applied = []
        for version, name, digest, sql in ordered[len(actual):]:
            # GO on a line by itself is the only batch delimiter admitted here.
            for batch in re.split(r'^GO\s*$', sql, flags=re.MULTILINE):
                if batch.strip():
                    cur = cn.execute(batch)
                    while cur.nextset():
                        pass
            cn.execute('INSERT dbo.schema_migrations(version,name,sha256) VALUES (?,?,?)', version, name, digest)
            applied.append(version)
        return applied
