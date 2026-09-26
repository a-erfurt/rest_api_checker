"""Explicit administrative/import CLI. No startup migration or model execution."""
import argparse
from contextlib import closing
import json
from pathlib import Path

from .admin import (backup_database, create_database, create_test_database,
                    destroy_test_database, restore_test_database)
from .database import connect, read_settings
from .importer import import_development, import_prompts
from .migrate import apply, inspect, verify
from .repository import Repository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',type=Path,required=True)
    parser.add_argument('--database',default='rest_api_checker')
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init')
    sub.add_parser('create-test')
    sub.add_parser('destroy-test')
    migration = sub.add_parser('migrate')
    migration.add_argument('--expected-current',type=int,required=True)
    sub.add_parser('version')
    backup = sub.add_parser('backup')
    backup.add_argument('--server-path',required=True)
    restore = sub.add_parser('restore-test')
    restore.add_argument('--server-path',required=True)
    dev = sub.add_parser('import-dev')
    dev.add_argument('--staging',type=Path,required=True)
    dev.add_argument('--release',type=Path,required=True)
    dev.add_argument('--research',type=Path,required=True)
    prompts = sub.add_parser('import-prompts')
    prompts.add_argument('--research',type=Path,required=True)
    args = parser.parse_args()
    settings = read_settings(args.env_file)
    if args.command=='init':
        print(create_database(settings,args.database))
    elif args.command=='create-test':
        print(create_test_database(settings))
    elif args.command=='destroy-test':
        destroy_test_database(settings,args.database)
        print('Destroyed explicitly marked disposable database')
    elif args.command=='backup':
        backup_database(settings,args.database,args.server_path)
        print('Backup and VERIFYONLY complete; copy outside container')
    elif args.command=='restore-test':
        print(restore_test_database(settings,args.server_path))
    else:
        with closing(connect(settings,args.database)) as cn:
            if args.command=='migrate':
                print(json.dumps({'applied':apply(cn,expected_current=args.expected_current)}))
            elif args.command=='version':
                print(json.dumps({'version':verify(cn,complete=False),'ledger':inspect(cn)}))
            elif args.command=='import-dev':
                print(json.dumps(import_development(Repository(cn),args.staging,args.release,args.research)))
            elif args.command=='import-prompts':
                print(json.dumps(import_prompts(Repository(cn),args.research)))


if __name__=='__main__':
    main()
