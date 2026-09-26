"""Publish only the pre-specified D11 report after clean execution verification."""
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path('/Users/aerfurt/University/Bachelor/rest_api_checker')
sys.path.insert(0, str(ROOT / 'src'))
from rest_api_checker import sensitivity_candidate as sc, sensitivity_execution as sx
from rest_api_checker import sensitivity_freeze as sf, sensitivity_analysis as sa
from rest_api_checker import sensitivity_evaluation as se
from rest_api_checker.experiment.encoding import digest, encode
from rest_api_checker.persistence.database import connect, read_settings
from rest_api_checker.persistence.inspection import rows, portable
from rest_api_checker.persistence.repository import Repository

D = ROOT / sc.DIRECTORY
E = D / 'execution_20260926'


def save(name, content):
    with (E / name).open('xb') as out:
        out.write(content)


def main():
    verified = json.loads((E / 'execution_verification.json').read_bytes())
    assert verified['completion'] == 'COMPLETED' and verified['completed'] == 108 and verified['pending'] == 0
    assert verified['spool_and_persisted_bytes_identical'] and verified['baseline_all_frozen_rows_unchanged']
    raw, approval, candidate = sx.authorization(D / 'candidate.json', E / 'acceptance.json')
    assert digest(raw) == verified['candidate_sha256']
    assert digest(approval) == verified['acceptance_sha256']
    assert sc.verify(candidate, ROOT, ROOT.parent / 'bachelor_rest_api_checker', D)
    with closing(connect(read_settings(Path.home() / '.config/rest-api-checker/application-credentials.env'), 'rest_api_checker')) as cn:
        repo = Repository(cn)
        assert sc.verify(candidate, ROOT, ROOT.parent / 'bachelor_rest_api_checker', D, repo)
        assert not rows(repo, 'evaluation_reports', experiment_id=2)
        before = sf.snapshot(repo)
        assert before == verified['database_after_execution']
        old_rows = sc.baseline_rows(repo)
        cn.rollback()
        report_id, report = sa.create_report(repo, 2)
        report_row = repo._row('evaluation_reports', report_id)
        report_raw = repo.file(report_row['file_id'])
        input_raw = repo.file(report_row['input_file_id'])
        assert json.loads(report_raw) == report
        assert report['format'] == 'sensitivity-d11-evaluation-v1'
        assert report_row['baseline_report_id'] == candidate['baseline']['report']['id']
        replay = se.evaluate(json.loads(input_raw))
        replay.update(experiment_id=2, input_sha256=digest(input_raw), evaluator_sha256=se.artifact_hash(),
                      baseline_binding=json.loads(input_raw)['baseline_binding'])
        assert replay == report
        current = sc.baseline_rows(repo)
        assert all(all(current[t].get(i) == h for i, h in records.items()) for t, records in old_rows.items())
        assert sc.verify(candidate, ROOT, ROOT.parent / 'bachelor_rest_api_checker', D, repo)
        after = sf.snapshot(repo)
        for table in before:
            assert after[table]['count'] - before[table]['count'] == {'files': 2, 'evaluation_reports': 1}.get(table, 0), table
            if table not in ('files', 'evaluation_reports'):
                assert after[table] == before[table]
        cn.rollback()
        save('sensitivity-d11-analysis-input.json', input_raw)
        save('sensitivity-d11-evaluation-report.json', report_raw)
        evidence = dict(recorded_at=datetime.now().astimezone().isoformat(), report_id=report_id,
                        experiment_id=2, report_metadata=portable(report_row),
                        evaluator_version=se.VERSION, evaluator_sha256=se.artifact_hash(),
                        report_sha256=digest(report_raw), input_sha256=digest(input_raw),
                        evaluator_entrypoint='rest_api_checker.sensitivity_analysis.create_report(repo, 2)',
                        authority='prompt_development_protocol_v1.md sections 6, 9/D11 and 10/Gate C',
                        database_before_d11=before, database_after_d11=after,
                        existing_rows_unchanged=True, baseline_unchanged=True,
                        pure_d11_replay_matches=True, report_invocations=1,
                        main_evaluation_run=False, prompt_reselection=False, gate_c_approval=False)
        save('d11_verification.json', encode(evidence))
        print(json.dumps({k: v for k, v in evidence.items() if not k.startswith('database_')}, indent=2))


if __name__ == '__main__':
    main()
