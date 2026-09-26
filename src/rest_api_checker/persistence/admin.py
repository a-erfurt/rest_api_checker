"""Explicit local administration. Disposable drops require both a name and marker."""
from contextlib import closing
import re
import uuid

from .database import connect, database_name, require

TEST_PREFIX = 'rac_test_'


def create_database(settings, name, *, disposable=False):
    database_name(name)
    require((not disposable and name=='rest_api_checker') or
            (disposable and re.fullmatch(r'rac_test_[0-9a-f]{32}',name)), 'Database outside allowed create scope')
    with closing(connect(settings,'master',autocommit=True)) as cn:
        require(cn.execute('SELECT DB_ID(?)',name).fetchval() is None, 'Refusing existing database')
        cn.execute(f'CREATE DATABASE [{name}]')
    if disposable:
        with closing(connect(settings,name,autocommit=True)) as cn:
            cn.execute("EXEC sys.sp_addextendedproperty @name=N'rest_api_checker_disposable', @value=N'v1'")
    return name


def create_test_database(settings):
    return create_database(settings,TEST_PREFIX+uuid.uuid4().hex,disposable=True)


def destroy_test_database(settings, name):
    require(re.fullmatch(r'rac_test_[0-9a-f]{32}',name) is not None, 'Refusing non-disposable database name')
    with closing(connect(settings,name,autocommit=True)) as cn:
        require(cn.execute("SELECT CAST(value AS nvarchar(20)) FROM sys.extended_properties WHERE class=0 AND name=N'rest_api_checker_disposable'").fetchval()=='v1',
                'Disposable marker missing; refusing drop')
    with closing(connect(settings,'master',autocommit=True)) as cn:
        # Exact marked resource only. No forced connection termination or other reset.
        cn.execute(f'DROP DATABASE [{name}]')


def _server_backup_path(path):
    require(re.fullmatch(r'/var/opt/mssql/backup/rac_persistence_[0-9a-f]{32}\.bak',path) is not None,
            'Backup must use an isolated rac_persistence_<uuid>.bak path')
    return path


def _drain(cursor):
    while cursor.nextset():
        pass


def backup_database(settings, name, path):
    """COPY_ONLY/CHECKSUM, refusing existing backup files. Copy outside container next."""
    database_name(name)
    _server_backup_path(path)
    with closing(connect(settings,'master',autocommit=True)) as cn:
        require(cn.execute('SELECT DB_ID(?)',name).fetchval() is not None, 'Database absent')
        require(cn.execute('EXEC master.dbo.xp_fileexist ?',path).fetchone()[0]==0, 'Backup path already exists')
        _drain(cn.execute(f'BACKUP DATABASE [{name}] TO DISK=? WITH COPY_ONLY,CHECKSUM',path))
        _drain(cn.execute('RESTORE VERIFYONLY FROM DISK=? WITH CHECKSUM',path))


def restore_test_database(settings, path):
    """Restore an independent marked disposable target, never REPLACE a database."""
    _server_backup_path(path)
    name = TEST_PREFIX+uuid.uuid4().hex
    with closing(connect(settings,'master',autocommit=True)) as cn:
        require(cn.execute('SELECT DB_ID(?)',name).fetchval() is None, 'Restore target exists')
        _drain(cn.execute('RESTORE VERIFYONLY FROM DISK=? WITH CHECKSUM',path))
        files = cn.execute('RESTORE FILELISTONLY FROM DISK=?',path).fetchall()
        require(len(files)==2 and {r.Type for r in files}=={'D','L'}, 'Expected one data and one log file')
        data = next(r.LogicalName for r in files if r.Type=='D')
        log = next(r.LogicalName for r in files if r.Type=='L')
        _drain(cn.execute(f'''RESTORE DATABASE [{name}] FROM DISK=? WITH MOVE ? TO ?, MOVE ? TO ?, CHECKSUM,RECOVERY''',
            path,data,f'/var/opt/mssql/data/{name}.mdf',log,f'/var/opt/mssql/data/{name}_log.ldf'))
    with closing(connect(settings,name,autocommit=True)) as cn:
        marker = cn.execute("SELECT value FROM sys.extended_properties WHERE class=0 AND name=N'rest_api_checker_disposable'").fetchval()
        if marker is None:
            cn.execute("EXEC sys.sp_addextendedproperty @name=N'rest_api_checker_disposable', @value=N'v1'")
        else:
            require(marker=='v1', 'Unexpected restored marker')
    return name
