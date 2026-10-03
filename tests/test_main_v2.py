"""Offline release/plan gates. Human approval is fabricated only in temp fixtures."""
import json
from pathlib import Path
import socket
import os
import shlex
import subprocess
import sys
import tempfile

import pytest

from rest_api_checker import main_v2 as main, main_v2_context as context, main_v2_release as release
from rest_api_checker.experiment import request
from rest_api_checker.experiment.encoding import digest, encode
from rest_api_checker.persistence.importer import PROMPT_HASHES
from persistence.main_v2_helpers import RESEARCH, ARCHIVE, make_review, make_release, prepared_context, csv_bytes


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Real network/model calls forbidden')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)


@pytest.mark.parametrize('n', [1, 4])
def test_dynamic_schedule_and_exact_authorities(tmp_path, n):
    final, prepared, directory, native_calls = prepared_context(tmp_path, n)
    plan, files, raw = main.load_prepared(final, prepared)
    assert plan['planned'] == n*9
    assert plan['cases'] == n
    assert final['manifest']['denominators']['observations'] == n
    assert final['manifest']['denominators']['response_pattern_groups'] == len({
        c['response_pattern_group'] for c in final['manifest']['cases']})
    assert all(c['reviewer_status'] == c['accepted_review']['reviewer_status'] == 'APPROVED'
               and c['archived_candidate_status']['reviewer_status'] == 'PENDING' for c in final['manifest']['cases'])
    assert all(c['reviewer_status'] == 'PENDING' for c in json.loads(final['files']['candidate/candidate_cases.json'])['cases'])
    expected = [(c['candidate_id'], m, rep, seed) for c in final['manifest']['cases']
                for m in request.MODELS for rep, seed in request.SEEDS.items()]
    assert [(s['case'], s['model'], s['repetition'], s['seed']) for s in plan['slots']] == expected
    assert [s['run_order'] for s in plan['slots']] == list(range(1, n*9+1))
    assert {s['seed'] for s in plan['slots']} == {101, 202, 303}
    assert plan['prompt_sha256'] == PROMPT_HASHES['P2']
    assert plan['generation_options'] == request.OPTIONS and plan['generation_options']['num_predict'] == 512
    assert main.request_files(final)['plan.json'] == raw
    proofs, _, _ = context.verify_context(plan, files, raw, directory)
    assert len(proofs) == n*9
    for slot in plan['slots']:
        req = context.request_at(plan, files, slot)
        payload = json.loads(req.body)
        assert payload['format'] == 'json' and payload['options'] == {**request.OPTIONS, 'seed': slot['seed']}
        assert digest(payload['messages'][0]['content'].encode()) == PROMPT_HASHES['P2']
        request.ContextProof(**proofs[str(slot['run_order'])]).verify(req)
        assert all('reference' not in m['content'] or m['role'] == 'system' for m in payload['messages'])
    assert len(native_calls) == n*9*2  # All fabricated, all render/tokenize-only.


@pytest.mark.parametrize('change', ['pending', 'excluded', 'replacement', 'label', 'name', 'date', 'coverage', 'family', 'columns'])
def test_review_refusals(tmp_path, change):
    archive, review_dir = make_review(tmp_path)
    path = review_dir/'manual_review.csv'
    records = release.csv_rows(path.read_bytes())
    if change == 'pending': records[0]['reviewer_status'] = 'PENDING'
    if change == 'excluded': records[0]['reviewer_status'] = 'EXCLUDED'
    if change == 'replacement': records[0]['reviewer_replacement_candidate_id'] = 'NEW-ID'
    if change == 'label': records[0]['reviewer_decision_C1'] = 'FAIL'
    if change == 'name': records[0]['reviewer_name'] = ''
    if change == 'date': records[0]['reviewed_at'] = '2026-10-03'
    if change == 'columns': records[0]['api'] = 'changed'
    path.write_bytes(csv_bytes(records))
    if change == 'coverage':
        p = review_dir/'review_decisions.json'
        decision = json.loads(p.read_bytes()); decision['coverage_losses_accepted'] = False
        p.write_bytes(encode(decision))
    if change == 'family':
        p = review_dir/'family_review.csv'; r = release.csv_rows(p.read_bytes()); r[0]['reviewer_status'] = 'PENDING'
        p.write_bytes(csv_bytes(r))
    with pytest.raises(ValueError): release.check_integrity(archive, review_dir)


def test_real_pending_candidate_never_freezes():
    with pytest.raises(ValueError, match='PENDING'):
        release.check_integrity(ARCHIVE, ARCHIVE)


@pytest.mark.parametrize('change', ['integrity', 'references', 'identity', 'status', 'approval'])
def test_final_release_refuses_invalid_input_even_with_new_package_hash(tmp_path, change):
    final = make_release(tmp_path)
    files = dict(final['files'])
    if change == 'integrity':
        obj = json.loads(files['integrity.json']); obj['status'] = 'FAIL'; files['integrity.json'] = encode(obj)
    elif change == 'approval':
        obj = json.loads(files['author-freeze.json']); obj['decision'] = 'PENDING'; files['author-freeze.json'] = encode(obj)
    else:
        obj = json.loads(files['dataset.json'])
        if change == 'references': del obj['cases'][0]['C1']
        if change == 'identity': obj['ordered_case_ids'] = ['OTHER']
        if change == 'status': obj['status'] = 'CANDIDATE'
        files['dataset.json'] = encode(obj)
    target = tmp_path/'invalid'
    release.publish(target, release.seal(files, 'freeze.json', format='main-v2-freeze-receipt-v1', status='FROZEN', dataset_sha256=digest(files['dataset.json'])), research=RESEARCH)
    with pytest.raises(ValueError): release.load_release(target)


def test_failed_checker_and_archive_integrity(tmp_path):
    archive, review_dir = make_review(tmp_path)
    (archive/'candidate_cases.json').write_bytes(b'{}')
    with pytest.raises(ValueError, match='integrity'): release.check_integrity(archive, review_dir)


def test_checker_failure_cannot_be_replaced_by_a_passing_receipt(tmp_path):
    archive, review_dir = make_review(tmp_path)
    _, files, _ = release.checked_package(archive, 'archive_manifest.json')
    files['scripts/verify_candidate.py'] = b'import json\nprint(json.dumps(dict(status="FAIL")))\nraise SystemExit(2)\n'
    broken = tmp_path/'failed-candidate'
    release.publish(broken, release.seal(files, 'archive_manifest.json', test_only=True), research=RESEARCH)
    with pytest.raises(ValueError, match='verifier failed'):
        release.check_integrity(broken, review_dir)


def test_materialization_api_cannot_bypass_release_gate(tmp_path):
    final = make_release(tmp_path)
    final['manifest']['status'] = 'PENDING'
    with pytest.raises(ValueError, match='identity changed'): main.request_files(final)
    # No repository method can run before the release check.
    with pytest.raises(ValueError, match='identity changed'): main.import_dataset(None, final)


def test_prepared_bytes_cannot_be_replaced_by_a_new_hash_manifest(tmp_path):
    final, prepared, directory, _ = prepared_context(tmp_path)
    plan, files, _ = release.checked_package(prepared, 'plan.json')
    req = json.loads(files['requests/000001.json']); req['options']['num_predict'] = 513
    files['requests/000001.json'] = encode(req)
    plan.pop('files')
    altered = tmp_path/'altered-plan'
    release.publish(altered, release.seal(files, 'plan.json', **plan), research=RESEARCH)
    with pytest.raises(ValueError, match='identity drift'): main.load_prepared(final, altered)


@pytest.mark.parametrize('change', ['missing', 'tokens', 'generation', 'request', 'runtime', 'overflow'])
def test_native_proofs_require_exact_complete_evidence(tmp_path, change):
    final, prepared, directory, _ = prepared_context(tmp_path)
    plan, files, raw = main.load_prepared(final, prepared)
    manifest, evidence, _ = release.checked_package(directory, 'manifest.json')
    if change == 'missing': manifest['rows'].pop()
    elif change == 'runtime': manifest['runtime_binding_sha256'] = '0'*64
    else:
        suffix = {'tokens': 'token-response', 'generation': 'render-response', 'request': 'render-request', 'overflow': 'token-response'}[change]
        name = 'native/000001-'+suffix+'.json'; obj = json.loads(evidence[name])
        if change == 'tokens': obj['tokens'] = []
        if change == 'overflow': obj['tokens'] = [1]*request.OPTIONS['num_ctx']
        if change == 'generation': obj['message'] = dict(content='forbidden answer')
        if change == 'request': obj['_debug_render_only'] = False
        evidence[name] = encode(obj)
    manifest.pop('files')
    target = tmp_path/'bad-context'
    release.publish(target, release.seal(evidence, 'manifest.json', **manifest), research=RESEARCH)
    with pytest.raises(ValueError): context.verify_context(plan, files, raw, target)


def test_no_native_call_without_confirmation(tmp_path):
    with pytest.raises(ValueError, match='confirmation'):
        context.measure(None, None, tmp_path/'native', root=tmp_path, research=RESEARCH)
    assert not (tmp_path/'native').exists()


def test_no_research_output_or_overwrite(tmp_path):
    with pytest.raises(ValueError, match='read only'):
        release.publish(RESEARCH/'forbidden', {}, research=RESEARCH)
    with pytest.raises(ValueError, match='never overwrite'):
        release.publish(tmp_path, {}, research=RESEARCH)


@pytest.mark.parametrize(('problematic', 'resume'), [(0, False), (0, True), (1, False)])
def test_launch_wrapper_uses_one_guarded_command(tmp_path, problematic, resume):
    """Run the actual shell flow with fabricated CLI and sleep-guard executables."""
    root = Path(main.ROOT)
    fake = tmp_path/'launcher'
    (fake/'tools/main_v2').mkdir(parents=True)
    (fake/'.venv/bin').mkdir(parents=True)
    marker = tmp_path/'dispatch-arguments'
    guard = tmp_path/'caffeinate-arguments'
    sleeper = tmp_path/'fabricated-caffeinate'
    sleeper.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > '+shlex.quote(str(guard))+'\nshift 2\nexec "$@"\n')
    sleeper.chmod(0o700)
    script = fake/'tools/main_v2/launch.sh'
    script.write_text((root/'tools/main_v2/launch.sh').read_text().replace('/usr/bin/caffeinate', shlex.quote(str(sleeper))))
    plan = dict(dataset=dict(id=7, name='FABRICATED', version='TEST'), experiment_id=9,
        cases=1, models=[dict(name=n) for n in request.MODELS], repetitions=len(request.SEEDS), seeds=list(request.SEEDS.values()),
        planned=9, prompt='P2', prompt_sha256=PROMPT_HASHES['P2'], output_mode='format_json',
        token_limit=request.OPTIONS['num_predict'], runtime={'ollama': {'version': 'FABRICATED'}}, setup_sha256='0'*64,
        problematic=problematic)
    receipt = tmp_path/'fabricated-dry-run.json'
    receipt.write_bytes(encode(dict(plan=plan)))
    cli = fake/'.venv/bin/rest-api-checker'
    cli.write_text('#!/bin/bash\ncase " $* " in\n*" --dry-run "*) cat '+shlex.quote(str(receipt))+' ;;\n'
        '*" run-batch "*) printf "%s\\n" "$@" > '+shlex.quote(str(marker))+'; echo "{}" ;;\n*) echo "{}" ;;\nesac\n')
    cli.chmod(0o700)
    executable = fake/'.venv/bin/python'
    executable.write_text('#!/bin/bash\nexec '+shlex.quote(sys.executable)+' "$@"\n')
    executable.chmod(0o700)
    env = tmp_path/'fabricated.env'; env.write_text('# FABRICATED: no database credentials\n')
    # Exercise durable-path validation on the workspace filesystem. Clean up all
    # smoke artifacts immediately; no scientific files or real spool are used.
    with tempfile.TemporaryDirectory(prefix='test-main-v2-wrapper-', dir=root/'artifacts') as run_dir:
        result = subprocess.run(['/bin/bash', str(script), str(env), 'FABRICATED', '7', '9', run_dir]
            + (['--resume'] if resume else []), capture_output=True, text=True,
            env={**os.environ, 'MAIN_V2_MIN_FREE_KIB': '1'})
        assert (result.returncode == 0) == (problematic == 0), result.stderr
        assert marker.exists() == guard.exists() == (problematic == 0)
        if not problematic:
            args = marker.read_text().splitlines()
            assert args.count('run-batch') == 1 and args.count('--yes') == 1
            assert ('--resume' in args) == resume
            assert guard.read_text().splitlines()[:2] == ['-i', '-s']
            assert len(list(Path(run_dir).glob('launch-*/main-receipt.json'))) == 1
