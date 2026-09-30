"""Thesis CLI: bounded SQL inspection, immutable evaluation and offline preflight."""
import argparse
from contextlib import closing, nullcontext
import json
from pathlib import Path
import shlex
import shutil
import sys
import tempfile

import pyodbc

from . import demo, evaluation, preflight, terminal
from .experiment.batch import run
from .experiment.orchestration import reconcile_attempt
from .persistence.admin import (create_test_database, destroy_test_database, create_database,
                                backup_database, restore_test_database)
from .persistence.database import connect, read_settings, require
from .persistence.inspection import portable, rows, run_detail, status
from .persistence.migrate import apply, inspect, verify
from .persistence.repository import Repository


def arguments():
    p = argparse.ArgumentParser(prog='rest-api-checker',description=__doc__)
    # Options on both root and leaf accept the customary trailing --json too.
    def options(target, suppress=False):
        default = argparse.SUPPRESS if suppress else None
        target.add_argument('--json',action='store_true',default=default,help='JSON only on stdout')
        target.add_argument('--plain',action='store_true',default=default,help='No color or animation')
        target.add_argument('--verbose',action='store_true',default=default)
        target.add_argument('--env-file',type=Path,default=default,help='Private SQL connection settings')
        target.add_argument('--database',default=argparse.SUPPRESS if suppress else 'rest_api_checker')
        target.add_argument('--root',type=Path,default=argparse.SUPPRESS if suppress else Path.cwd())
        target.add_argument('--research',type=Path,default=default)
    options(p)
    groups = p.add_subparsers(dest='group',required=True)
    def group(name):
        return groups.add_parser(name).add_subparsers(dest='command',required=True)
    def leaf(g,name,identifier=None):
        node = g.add_parser(name)
        options(node,True)
        if identifier:
            node.add_argument(identifier,type=int)
        return node
    db = group('db')
    leaf(db,'status')
    for name in ('version','init','create-test','destroy-test'):
        leaf(db,name)
    leaf(db,'migrate').add_argument('--expected-current',type=int,required=True)
    for name in ('backup','restore-test'):
        leaf(db,name).add_argument('--server-path',required=True)
    node = leaf(db,'import-dev')
    node.add_argument('--staging',type=Path,required=True)
    node.add_argument('--release',type=Path,required=True)
    leaf(db,'import-prompts')
    ds = group('dataset')
    leaf(ds,'list'); leaf(ds,'cases','dataset_id'); leaf(ds,'inventory')
    ex = group('experiment')
    leaf(ex,'list')
    for name in ('show','schedule','progress'):
        leaf(ex,name,'experiment_id')
    for name in ('run','resume'):
        node = leaf(ex,name,'experiment_id')
        node.add_argument('--fabricated',action='store_true',help='Only marked disposable demo experiments can execute in this stage')
        node.add_argument('--spool',type=Path,required=True)
    node = leaf(ex,'reconcile')
    node.add_argument('--spool-file',type=Path,required=True)
    node.add_argument('--fabricated',action='store_true')
    node = leaf(ex,'demo')
    node.add_argument('--keep',action='store_true',help='Retain marked demo database and spool for inspection/resume')
    node.add_argument('--delay',type=float,default=0.01,help='Fabricated provider delay per attempt, seconds')
    node.add_argument('--export',type=Path,help='New directory for fabricated input/report JSON; never overwrite')
    ev = group('evaluate')
    leaf(ev,'comparison','experiment_id'); leaf(ev,'list'); leaf(ev,'show','report_id')
    node = leaf(ev,'export','report_id')
    node.add_argument('--output',type=Path,required=True)
    ins = group('inspect')
    for name in ('run','attempts'):
        leaf(ins,name,'run_id')
    node = groups.add_parser('preflight')
    options(node,True)
    node.add_argument('--experiment-id',type=int)
    service = group('service')
    node = leaf(service,'capture')
    node.add_argument('--base-url',required=True,help='Explicit HTTP(S) service origin')
    node.add_argument('--execution-origin',choices=('remote','local_original','controlled_variant'),required=True)
    node.add_argument('--target-id',required=True,help='Exact deployment/source identity supplied by the operator')
    node.add_argument('--contract-id',type=int,required=True,help='Stored OpenAPI contract ID')
    node.add_argument('--path',choices=('/edx/validation/body','/resistance/csv/validation/body',
                                        '/resistance/txt/validation/body','/resistance/validation/file'),required=True)
    node.add_argument('--input',type=Path,required=True)
    node.add_argument('--case-id',required=True)
    node.add_argument('--filename',help='Optional EDX filename header or Resistance multipart filename')
    return p


def _execute(repo,args,display):
    require(args.fabricated,'BLOCKED: real execution is unavailable until measured Gate-B evidence and acceptance are implemented')
    client = demo.client_for(repo,args.experiment_id)
    def event(e):
        client.event(e)
        display.event(e)
    return run(repo,args.experiment_id,client=client,spool_directory=args.spool,
               verify_runtime=lambda r,p:True,review_failure=lambda r,p:'isolated',notify=event)


def _demo(args,settings,console):
    require(0 <= args.delay <= 5,'Demo delay must be between 0 and 5 seconds')
    if args.export:
        args.export.mkdir(parents=True,exist_ok=False)
    name = create_test_database(settings)
    spool = tempfile.mkdtemp(prefix='rac-fabricated-spool-')
    cleanup = False
    try:
        if not args.json:
            console.print('FABRICATED / TEST DATA — preparing disposable SQL Server resources',style='yellow')
        with closing(connect(settings,name)) as cn:
            apply(cn,expected_current=0)
            repo = Repository(cn)
            with console.status('Preparing FABRICATED disposable SQL demo',spinner_style=terminal.ACCENT) if console.is_terminal and not args.json else nullcontext():
                experiment_id, _ = demo.plan(repo,args.root,args.research)
            client = demo.client_for(repo,experiment_id,delay=args.delay)
            with terminal.RunDisplay(console,enabled=not args.json) as display:
                def event(e):
                    client.event(e)
                    display.event(e)
                result = run(repo,experiment_id,client=client,spool_directory=spool,verify_runtime=lambda r,p:True,
                             review_failure=lambda r,p:'isolated',notify=event)
            value = dict(fabricated=True,label='FABRICATED / TEST DATA',database=name,execution=result,
                         provider_calls=client.calls,study_execution=False,spool=spool)
            if result['exit_code']==0:
                report_id, report = evaluation.create_report(repo,experiment_id)
                value.update(report_id=report_id,report=report)
                if args.export:
                    row = repo._row('evaluation_reports',report_id)
                    for name_part,key in [('report.json','file_id'),('input.json','input_file_id')]:
                        with (args.export/name_part).open('xb') as f:
                            f.write(repo.file(row[key]))
                if not args.json:
                    terminal.report(console,report,args.verbose)
                value['preflight'] = preflight.check(args.root,args.research,repo,experiment_id)
            cleanup = result['exit_code']==0 and not args.keep
            value['retained'] = not cleanup
            value['resume_command'] = shlex.join(['rest-api-checker','--env-file',str(args.env_file),'--database',name,
                'experiment','resume',str(experiment_id),'--fabricated','--spool',spool])
            return value,result['exit_code']
    finally:
        if cleanup:
            try:
                destroy_test_database(settings,name)
            except Exception:
                print(f'Disposable cleanup failed: database={name}; spool={spool}; inspect before removal',file=sys.stderr)
                raise
            shutil.rmtree(spool)
        else:
            print(f'FABRICATED resources retained: database={name}; spool={spool}',file=sys.stderr)


def dispatch(args,console):
    args.research = args.research or args.root.parent/'bachelor_rest_api_checker'
    if args.group=='preflight' and not args.env_file:
        return preflight.check(args.root,args.research),3
    require(args.env_file is not None,'--env-file is required for SQL commands')
    settings = read_settings(args.env_file)
    if args.group=='experiment' and args.command=='demo':
        return _demo(args,settings,console)
    if args.group=='db':
        if args.command=='init':
            return dict(database=create_database(settings,args.database)),0
        if args.command=='create-test':
            return dict(database=create_test_database(settings)),0
        if args.command=='destroy-test':
            destroy_test_database(settings,args.database)
            return dict(status='Removed marked disposable database'),0
        if args.command=='backup':
            backup_database(settings,args.database,args.server_path)
            return dict(status='Backup and VERIFYONLY complete; copy outside container'),0
        if args.command=='restore-test':
            return dict(database=restore_test_database(settings,args.server_path)),0
    with closing(connect(settings,args.database)) as cn:
        if args.group=='db':
            if args.command in ('status','version'):
                return dict(database=args.database,version=verify(cn),ledger=inspect(cn)),0
            if args.command=='migrate':
                return dict(applied=apply(cn,expected_current=args.expected_current)),0
            from .persistence.importer import import_development, import_prompts
            if args.command=='import-dev':
                return import_development(Repository(cn),args.staging,args.release,args.research),0
            return import_prompts(Repository(cn),args.research),0
        repo = Repository(cn)
        if args.group=='service':
            from .service_capture import ServiceTarget, check_operation, execute, materialize, prepare
            check_operation(repo,args.contract_id,args.path,args.case_id)
            target = ServiceTarget(args.base_url,args.execution_origin,args.target_id)
            request = prepare(target,args.path,str(args.input.resolve()),args.input.read_bytes(),
                              filename=args.filename)
            return materialize(repo,execute(request),args.contract_id,args.case_id),0
        if args.group=='preflight':
            return preflight.check(args.root,args.research,repo,args.experiment_id),3
        if args.group=='dataset':
            if args.command=='list':
                return rows(repo,'datasets'),0
            if args.command=='inventory':
                return {t:portable(rows(repo,t)) for t in ('models','prompts','run_configs')},0
            return rows(repo,'dataset_cases',dataset_id=args.dataset_id),0
        if args.group=='inspect':
            return run_detail(repo,args.run_id,raw=args.verbose),0
        if args.group=='evaluate':
            if args.command=='list':
                return rows(repo,'evaluation_reports'),0
            if args.command=='comparison':
                with console.status('Reconciling schedule and archiving evaluation',spinner_style=terminal.ACCENT) if console.is_terminal and not args.json else nullcontext():
                    report_id, report = evaluation.create_report(repo,args.experiment_id)
                return dict(report_id=report_id,report=report),0
            row = repo._row('evaluation_reports',args.report_id)
            raw = repo.file(row['file_id'])
            if args.command=='export':
                with args.output.open('xb') as f:
                    f.write(raw)
                return dict(report_id=args.report_id,output=str(args.output)),0
            return dict(report_id=args.report_id,report=json.loads(raw)),0
        if args.command=='list':
            return [dict(id=e['id'],name=e['name'],**{k:v for k,v in status(repo,e['id']).items()
                         if k in ('planned','completed','pending','counts','fabricated')}) for e in rows(repo,'experiments')],0
        if args.command in ('run','resume'):
            with terminal.RunDisplay(console,enabled=not args.json) as display:
                result = _execute(repo,args,display)
            return result,result['exit_code']
        if args.command=='reconcile':
            require(args.fabricated,'BLOCKED: runtime failure attribution must be supplied by a verified future adapter')
            demo.require_isolation(repo)
            from .persistence.spool import read
            _,value,_ = read(args.spool_file)
            r = repo._row('experiment_runs',value['run_id'])
            demo.client_for(repo,r['experiment_id'])  # verifies fabricated namespace; never sends
            return dict(result=reconcile_attempt(repo,args.spool_file,review_failure=lambda r,p:'isolated')),0
        state = status(repo,args.experiment_id)
        if args.command=='schedule':
            for r in state['runs']:
                r.update(case=repo._row('dataset_cases',r['dataset_case_id'])['case_code'],
                         model=repo._row('models',r['model_id'])['name'],prompt=repo._row('prompts',r['prompt_id'])['name'])
        elif not args.verbose:
            state.pop('runs')
        return state,0


def present(console,args,value):
    if args.group=='preflight':
        for c in value['checks']:
            style = {'PASS':'green','FAIL':'red','BLOCKED':'yellow'}[c['status']]
            console.print(terminal.clean(f'[{c["status"]}] {c["check"]}: {c["detail"]}'),style=style)
        console.print('Gate B: '+value['status'],style='yellow')
    elif args.group=='evaluate' and isinstance(value,dict) and 'report' in value:
        console.print(f'Report {value["report_id"]}',style=terminal.ACCENT)
        terminal.report(console,value['report'],args.verbose)
    elif args.group=='inspect':
        terminal.inspection(console,value,args.verbose)
    elif args.group=='experiment' and args.command in ('demo','run','resume'):
        result = value.get('execution',value)
        s = result['state']
        console.print(terminal.table('Execution summary',('Status','Completed','Pending','Valid','Parser','Technical'),
            [[result['status'],f'{s["completed"]}/{s["planned"]}',s['pending'],*(s['counts'][k] for k in ('valid','parser_failure','technical_failure'))]]))
        if args.command=='demo':
            console.print('FABRICATED / TEST DATA. No study prompt winner.')
            if value['retained']:
                console.print('Resume: '+value['resume_command'])
                console.print(f'Inspect with --database {value["database"]}; remove explicitly with db destroy-test.')
            else:
                console.print('Disposable database and spool removed.')
        elif result['exit_code']:
            console.print('Resume: '+shlex.join(['rest-api-checker','--env-file',str(args.env_file),'--database',args.database,
                'experiment','resume',str(args.experiment_id),'--fabricated','--spool',str(args.spool)]))
    elif isinstance(value,list):
        if value:
            columns = [k for k in value[0] if k not in ('counts',)]
            console.print(terminal.table(args.group,columns,[[r.get(k) for k in columns] for r in value]))
        else:
            console.print('No records.')
    elif args.group=='experiment' and 'completed' in value:
        console.print(terminal.table(value['experiment']['name'],('Planned','Completed','Pending','Valid','Parser','Technical'),
            [[value['planned'],value['completed'],value['pending'],*(value['counts'][k] for k in ('valid','parser_failure','technical_failure'))]]))
        if 'runs' in value:
            console.print(terminal.table('Schedule',('Order','Run','Model','Prompt','Case','Repetition','Seed','Status'),
                [[r['run_order'],r['id'],r.get('model',r['model_id']),r.get('prompt',r['prompt_id']),
                  r.get('case',r['dataset_case_id']),r['repetition'],r['seed'],r['result'] or 'PENDING'] for r in value['runs']]))
    else:
        for key,item in value.items():
            if isinstance(item,list) and item and isinstance(item[0],dict):
                columns = list(item[0])
                console.print(terminal.table(key,columns,[[r[k] for k in columns] for r in item]))
            else:
                console.print(terminal.clean(f'{key}: {item}'))


def main(argv=None):
    args = arguments().parse_args(argv)
    console = terminal.console(plain=bool(args.plain or args.json))
    try:
        value,code = dispatch(args,console)
    except KeyboardInterrupt:
        value,code = dict(status='INCOMPLETE',error='Interrupted; inspect persisted state before resume'),130
    except (ValueError,OSError,KeyError,pyodbc.Error) as exc:
        # Driver errors can contain connection details. Never echo credentials.
        message = 'SQL operation failed; inspect connectivity/schema using db status' if isinstance(exc,pyodbc.Error) else str(exc)
        value,code = dict(status='BLOCKED',error=message),3
        print(terminal.clean(message),file=sys.stderr)
    if args.json:
        print(json.dumps(portable(value),ensure_ascii=True,sort_keys=True,allow_nan=False))
    elif code in (0,3,130) and 'error' not in value:
        present(console,args,value)
    return code


def entrypoint():
    raise SystemExit(main())


if __name__=='__main__':
    entrypoint()
