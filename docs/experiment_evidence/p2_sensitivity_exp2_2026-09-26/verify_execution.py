"""Read-only post-execution audit; only new local audit artifacts are written."""
from collections import Counter
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path('/Users/aerfurt/University/Bachelor/rest_api_checker')
sys.path.insert(0, str(ROOT / 'src'))
from rest_api_checker import sensitivity_candidate as sc, sensitivity_execution as sx
from rest_api_checker import sensitivity_freeze as sf
from rest_api_checker.experiment import parser
from rest_api_checker.experiment.encoding import digest, encode
from rest_api_checker.persistence import spool
from rest_api_checker.persistence.database import connect, read_settings
from rest_api_checker.persistence.inspection import rows, status, portable
from rest_api_checker.persistence.repository import Repository

D = ROOT / sc.DIRECTORY
E = D / 'execution_20260926'
SPOOL = ROOT.parent / 'rest_api_checker_spool/p2_sensitivity_exp2_20260926'


def save(name, value):
    with (E / name).open('xb') as out:
        out.write(encode(portable(value)))


def main():
    raw, approval, candidate = sx.authorization(D / 'candidate.json', E / 'acceptance.json')
    assert digest(raw) == '41c257a36cd2499fa8aa12fe8140e8fe24818fd5ed8586acc59fa8bbc4bcc9fc'
    assert sc.verify(candidate, ROOT, ROOT.parent / 'bachelor_rest_api_checker', D)
    console_raw = (E / 'execution_console.log').read_bytes()
    console = json.loads(console_raw)
    assert json.loads((E / 'process_exit.json').read_bytes())['exit_code'] == 0
    assert console['exit_code'] == 0 and console['status'] == 'COMPLETED' and console['message'] is None
    with closing(connect(read_settings(Path.home() / '.config/rest-api-checker/application-credentials.env'), 'rest_api_checker')) as cn:
        repo = Repository(cn)
        assert sc.verify(candidate, ROOT, ROOT.parent / 'bachelor_rest_api_checker', D, repo)
        sx.require_persisted(repo, 2, raw, approval, candidate)
        state = status(repo, 2)
        assert state == console['state']
        assert state['planned'] == state['completed'] == 108 and state['pending'] == 0
        assert state['experiment']['finished_at'] is not None
        assert state['fabricated'] is False
        run_map = {r['id']: r for r in state['runs']}
        attempts = [a for a in rows(repo, 'run_attempts') if a['run_id'] in run_map]
        predictions = [p for p in rows(repo, 'predictions') if p['run_id'] in run_map]
        attempt_map = {a['id']: a for a in attempts}
        assert len(attempts) == len(attempt_map)
        assert len(predictions) == state['counts']['valid']
        assert not rows(repo, 'evaluation_reports', experiment_id=2)
        setup_sha = digest(repo.file(state['experiment']['setup_file_id']))
        checked = []
        for path in sorted(SPOOL.iterdir()):
            assert path.is_file() and path.suffix == '.json' and not path.name.startswith('.incomplete-')
            spool_raw, value, response = spool.read(path)
            a = attempt_map[value['attempt_id']]
            r = run_map[value['run_id']]
            assert a['run_id'] == r['id'] and a['request_file_id'] == r['request_file_id']
            req = repo.file(a['request_file_id'])
            inv = candidate['request_inventory'][r['run_order'] - 1]
            assert req == (D / inv['request_path']).read_bytes()
            assert digest(req) == inv['request_sha256'] == value['request_sha256']
            assert value['setup_sha256'] == setup_sha
            assert response == (repo.file(a['response_file_id']) if a['response_file_id'] is not None else None)
            archived = cn.execute('SELECT id FROM dbo.files WHERE sha256=?', digest(spool_raw)).fetchall()
            assert archived and any(repo.file(row[0]) == spool_raw for row in archived)
            diagnostic = repo._diagnostic_root(a['diagnostics_file_id'])
            assert diagnostic['spool_sha256'] == digest(spool_raw)
            assert diagnostic['request_sha256'] == digest(req)
            assert diagnostic['run_id'] == r['id'] and diagnostic['attempt_id'] == a['id']
            assert diagnostic['parser_sha256'] == parser.artifact_hash()
            checked.append(dict(path=str(path), spool_sha256=digest(spool_raw), run_id=r['id'],
                                attempt_id=a['id'], response_sha256=value['response_sha256'],
                                request_sha256=digest(req), result=a['result']))
        assert len(checked) == len(attempts)
        assert {r['attempt_id'] for r in checked} == set(attempt_map)
        models = {m['id']: m['name'] for m in rows(repo, 'models')}
        per_model = {}
        for r in state['runs']:
            aa = sorted((a for a in attempts if a['run_id'] == r['id']), key=lambda a: a['attempt'])
            pp = [p for p in predictions if p['run_id'] == r['id']]
            assert 1 <= len(aa) <= 2 and [a['attempt'] for a in aa] == list(range(1, len(aa) + 1))
            assert r['finished_at'] is not None and all(a['finished_at'] is not None and a['result'] is not None for a in aa)
            assert aa[-1]['result'] == r['result']
            assert len(pp) == (1 if r['result'] == 'valid' else 0)
            if len(aa) == 2:
                diag = repo._diagnostic_root(aa[0]['diagnostics_file_id'])
                assert aa[0]['result'] == 'technical_failure' and diag['retry_eligible'] is True
                assert diag['attribution'] == 'isolated'
            if r['result'] in ('valid', 'parser_failure'):
                parsed = parser.parse(json.loads(repo.file(aa[-1]['response_file_id']))['message']['content'])
                assert parsed.status == ('VALID_OUTPUT' if pp else 'PARSER_FAILURE')
                if pp:
                    assert pp[0]['attempt_id'] == aa[-1]['id']
                    assert all(pp[0][k] == v for k, v in parsed.prediction.items())
            else:
                assert len(aa) == 2
            name = models[r['model_id']]
            per_model.setdefault(name, Counter())[r['result']] += 1
        baseline = status(repo, 1)
        assert baseline['planned'] == baseline['completed'] == 324 and baseline['pending'] == 0
        assert len(rows(repo, 'evaluation_reports', experiment_id=1)) == 1
        snap = sf.snapshot(repo)
        before = json.loads((E / 'preparation_gate.json').read_bytes())['database_before']
        expected_delta = dict(experiments=1, experiment_runs=108, prompts=1,
                              run_attempts=len(attempts), predictions=len(predictions))
        for table in snap:
            if table != 'files':
                assert snap[table]['count'] - before[table]['count'] == expected_delta.get(table, 0), table
        cn.rollback()
        result = dict(recorded_at=datetime.now().astimezone().isoformat(), experiment_id=2,
                      candidate_sha256=digest(raw), acceptance_sha256=digest(approval),
                      console_sha256=digest(console_raw), completion='COMPLETED',
                      planned=108, completed=108, pending=0, attempts=len(attempts),
                      predictions=len(predictions), retries=sum(a['attempt'] == 2 for a in attempts),
                      counts=state['counts'], per_model={k: dict(v) for k, v in per_model.items()},
                      attempt_outcomes=dict(Counter(a['result'] for a in attempts)),
                      spool_count=len(checked), spool_and_persisted_bytes_identical=True,
                      parser_replay_matches=True, baseline_all_frozen_rows_unchanged=True,
                      baseline_report_sha256=candidate['baseline']['report_sha256'],
                      source_candidate_request_context_bindings_verified=True,
                      d11_run=False, main_evaluation_run=False,
                      started_at=state['experiment']['started_at'], finished_at=state['experiment']['finished_at'],
                      database_before=before, database_after_execution=snap)
        save('spool_verification.json', checked)
        save('status_after_execution.json', state)
        save('execution_verification.json', result)
        print(json.dumps({k: v for k, v in result.items() if not k.startswith('database_')}, indent=2))


if __name__ == '__main__':
    main()
