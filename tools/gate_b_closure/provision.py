"""Explicit local provisioning of migration-002 membership; never print secrets."""
from contextlib import closing
import json
import os
from pathlib import Path
import secrets
import stat
import sys

from rest_api_checker.persistence.database import connect, read_settings

LOGIN = 'rac_application_login'
USER = 'rac_application_user'
TARGET = 'rest_api_checker'
ADMIN = Path('/private/tmp/rac-sqlserver-environment-20260926/credentials.env')
APPLICATION = Path.home()/'.config/rest-api-checker/application-credentials.env'


def provision():
    admin = read_settings(ADMIN)
    APPLICATION.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if APPLICATION.exists():
        raise ValueError('Application credential file already exists; inspect, never overwrite')
    with closing(connect(admin,'master')) as cn:
        if cn.execute('SELECT SUSER_ID(?)',LOGIN).fetchval() is not None:
            raise ValueError('Application login already exists; inspect, never replace')
        cn.rollback()
    password = secrets.token_urlsafe(48)
    fd = os.open(APPLICATION, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(fd,'w') as stream:
        stream.write('RAC_SQL_USER='+LOGIN+'\nRAC_SQL_PORT='+admin['RAC_SQL_PORT']+'\nRAC_SQL_PASSWORD='+password+'\n')
        stream.flush(); os.fsync(stream.fileno())
    # Bind the secret as a parameter. SQL DDL is built inside SQL Server; neither
    # tool command text nor evidence receives the password or connection string.
    with closing(connect(admin,'master')) as cn:
        try:
            cn.execute("DECLARE @sql nvarchar(max)=N'CREATE LOGIN [rac_application_login] WITH PASSWORD = '+QUOTENAME(?,CHAR(39))+N', CHECK_POLICY=ON, CHECK_EXPIRATION=OFF, DEFAULT_DATABASE=[rest_api_checker]'; EXEC(@sql)",password)
            cn.execute('USE [rest_api_checker]')
            cn.execute('CREATE USER [rac_application_user] FOR LOGIN [rac_application_login]')
            cn.execute('ALTER ROLE [rac_application] ADD MEMBER [rac_application_user]')
            cn.commit()
        except BaseException:
            cn.rollback()
            # Retain the private file for explicit reconciliation; no ambiguous
            # success triggers password replacement or deletion of a principal.
            raise
    assert stat.S_IMODE(APPLICATION.stat().st_mode)==0o600
    with closing(connect(read_settings(APPLICATION),TARGET)) as cn:
        row=cn.execute("SELECT ORIGINAL_LOGIN(),USER_NAME(),IS_SRVROLEMEMBER('sysadmin'),IS_MEMBER('db_owner'),IS_MEMBER('rac_application')").fetchone()
        assert tuple(row)==(LOGIN,USER,0,0,1)
        cn.rollback()
    print(json.dumps(dict(login=LOGIN,user=USER,role='rac_application',database=TARGET,application_credentials=str(APPLICATION),administrative_credentials=str(ADMIN),credential_mode='0600',sysadmin=False,db_owner=False)))

if __name__=='__main__':
    try:
        provision()
    except BaseException:
        print('Provisioning did not complete; inspect the retained private credential and SQL principal state. No secret details emitted.',file=sys.stderr)
        raise SystemExit(1) from None
