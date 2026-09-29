"""Explicit author-acceptance gate over the unchanged qualified attempt runner.

Preparation never calls this module's run_accepted function. The frozen SQL
setup keeps gate_b_complete=false; only an accepted in-memory dispatch view
enables the provider. No scientific evaluator is invoked here.
"""
import json
from pathlib import Path
import subprocess

from . import freeze, main_freeze as main
from .experiment import batch, orchestration
from .experiment.encoding import digest
from .experiment.provider import OllamaClient
from .persistence.database import require, timestamp
from .persistence.inspection import bindings, rows


def require_acceptance(raw, record):
    manifest = json.loads(raw)
    require(manifest['format'] == 'main-evaluation-freeze-v1'
            and manifest['status'] == 'FROZEN_READY_FOR_EXECUTION'
            and manifest['name'] == main.NAME and manifest['version'] == main.VERSION,
            'Final Main freeze required')
    require(record.get('decision') == 'AUTHOR_AUTHORIZED_126_MAIN_RUNS'
            and record.get('freeze_root') == digest(raw)
            and record.get('experiment_id') == manifest['experiment_id'], 'Explicit exact-root execution authorization required')
    require(type(record.get('author')) is str and bool(record['author'].strip()), 'Named author required')
    timestamp(record.get('authorized_at'))
    require(record.get('authorized_at') is not None, 'Authorization time required')
    return manifest


def verify_package(directory, manifest, technical):
    directory, technical = Path(directory), Path(technical)
    for item in manifest['files']:
        path = Path(item['path'])
        require(not path.is_absolute() and '..' not in path.parts, 'Unsafe freeze path')
        raw = (directory/path).read_bytes()
        require(digest(raw) == item['sha256'] and len(raw) == item['bytes'], 'Main freeze file drift: '+str(path))
    head = subprocess.check_output(['git','-C',str(technical),'rev-parse','HEAD']).decode().strip()
    require(head == manifest['technical_commit'], 'Main runner commit drift')
    require(not subprocess.check_output(['git','-C',str(technical),'status','--porcelain']), 'Main runner working tree dirty')
    source = json.loads((directory/'technical_sources.json').read_bytes())
    for item in source['files']:
        raw = (technical/item['path']).read_bytes()
        require(digest(raw) == item['sha256'], 'Main runner source drift')


def run_accepted(repo, directory, approval, technical, spool_directory, **kwargs):
    directory = Path(directory)
    raw = (directory/'freeze_manifest.json').read_bytes()
    manifest = require_acceptance(raw, approval)
    verify_package(directory, manifest, technical)
    exp = repo._row('experiments', manifest['experiment_id'])
    setup_raw = repo.file(exp['setup_file_id'])
    require(setup_raw == (directory/'experiment_setup.json').read_bytes()
            and exp['name'] == main.NAME and exp['kind'] == 'evaluation', 'Persisted Main setup drift')
    setup = json.loads(setup_raw)
    require(setup['bindings'] == bindings(repo, exp['dataset_id'], setup['schedule']), 'Main relational drift')
    actual = rows(repo,'experiment_runs',experiment_id=exp['id'])
    require([{k:r[k] for k in setup['schedule'][0]} for r in actual] == setup['schedule'], 'Main schedule drift')
    repo.verify_closure(setup['files'])
    repo.cn.commit()
    def prepare(repo, run_id):
        inputs, req = orchestration.prepare(repo, run_id)
        require(inputs['run']['experiment_id'] == exp['id'], 'Wrong Main run')
        expected = setup['request_inventory'][inputs['run']['run_order']-1]
        require(digest(req.body) == expected['sha256'] and req.body == (directory/expected['path']).read_bytes(), 'Main request drift')
        inputs['setup'] = {**inputs['setup'], 'gate_b_complete':True}
        return inputs, req
    def verify_runtime(req, proof):
        verify_package(directory, manifest, technical)
        proof.verify(req)
        return freeze.verify_live(dict(runtime=setup['runtime'],models=setup['models']), Path(technical))
    return batch.run(repo, exp['id'], client=OllamaClient(), spool_directory=spool_directory,
        prepare_request=prepare, verify_runtime=verify_runtime,
        review_failure=lambda receipt, provider:'ambiguous', **kwargs)
