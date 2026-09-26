"""Render a factual handoff from the retained execution and D11 audit records."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path('/Users/aerfurt/University/Bachelor/rest_api_checker')
E = ROOT / 'artifacts/sensitivity_freeze_candidate_v2/execution_20260926'


def read(name):
    return json.loads((E / name).read_bytes())


def fraction(value):
    n, d = value['numerator'], value['denominator']
    return f'{n}/{d}' if d else 'N/A (0/0)'


def main():
    x, p, d, report, invocation = [read(n) for n in (
        'execution_verification.json', 'preexecution_gate.json', 'd11_verification.json',
        'sensitivity-d11-evaluation-report.json', 'invocation.json')]
    acceptance = read('acceptance.json')
    assert x['completed'] == 108 and x['pending'] == 0 and d['report_invocations'] == 1
    lines = [
        '# Experiment 2 — approved P2 sensitivity execution and diagnostic D11 handoff', '',
        'Evidence labels: FACT FROM OBSERVATION describes retained execution/SQL evidence; '
        'FACT FROM PROTOCOL describes the existing approved method. No new scientific decision, '
        'author interpretation, prompt selection, or Gate C approval is recorded here.', '',
        '## FACT FROM OBSERVATION — post-merge and authorization', '',
        f'- Execution branch: `main`; HEAD, local origin/main, and read-only remote origin/main all equalled `{invocation["head"]}`.',
        '- The technical working tree was clean before acceptance, preparation and dispatch. Frozen source inventories passed the actual adapter gates.',
        '- Research commit: `a54ec11b33d90722a482464dcda9823fdc50cf90`.',
        f'- Candidate SHA-256: `{x["candidate_sha256"]}`. Original bytes still state `NOT ACCEPTED`, `DO NOT EXECUTE`, `gate_b_complete=false`; they were not edited.',
        '- Prompt SHA-256: `e8d256399192e3f3ed66c23c78b80dc976bb8adc5e422a49ce3401ad407926cc`.',
        '- Schedule SHA-256: `0dbe99e7022f4dc46ece2a6127889b4f4c8a5822869557b332602f5221e0c700`.',
        f'- Separate acceptance: `acceptance.json`, SHA-256 `{x["acceptance_sha256"]}`; recorded at `{acceptance["accepted_at"]}` using the existing author/accepted_at schema.',
        '- The approval_statement is the exact user approval. Its recording timestamp is not a fabricated historical chat timestamp.',
        '- Local authorization/source checks preceded SQL/provider access; schema 2, application principal, baseline rows, model/runtime identities, schedule, requests and context proofs passed before preparation.',
        '- Experiment ID 2 was returned by the adapter/database and was not assumed for preparation.',
        '- Preparation persisted 108 planned logical runs; 0 attempts, predictions, reports or touched/partial runs. All 108 reconstructed request byte strings matched the frozen inventory.',
        '- A new empty spool directory and the live identities were checked immediately before dispatch. The existing adapter repeated its runtime/source/database/context checks before every physical attempt.', '',
        '## FACT FROM OBSERVATION — invocation and completion', '',
        'Working directory: `/Users/aerfurt/University/Bachelor/rest_api_checker`.', '',
        'Preparation:', '```sh', invocation['preparation_command'], '```', '',
        'Execution:', '```sh', invocation['command'], '```', '',
        'Both stdout and stderr were redirected, without overwrite, to '
        '`artifacts/sensitivity_freeze_candidate_v2/execution_20260926/execution_console.log`.', '',
        f'- Shell exit: 0; adapter status `COMPLETED`, exit_code 0, message null. Final console state equals the live DB state.',
        f'- Start: `{x["started_at"]}`; finish: `{x["finished_at"]}`.',
        f'- Finalized: {x["completed"]}/108; pending: {x["pending"]}; attempts: {x["attempts"]}; predictions: {x["predictions"]}; retries: {x["retries"]}.',
        f'- Valid: {x["counts"]["valid"]}; parser failures: {x["counts"]["parser_failure"]}; terminal technical failures: {x["counts"]["technical_failure"]}.',
        '- Pauses/holds/operator retry reviews: none. The adapter performed its normal durable spool import and finalization for each receipt; no separate recovery/reconciliation command was needed.',
        '- Sequential execution used caffeinate. No parser repair, fence stripping, majority vote, configuration change, prompt rewrite or baseline redispatch occurred.', '',
        '| Model | Planned/finalized | Valid | Parser failure | Technical failure |',
        '| --- | --- | --- | --- | --- |',
    ]
    for model, counts in x['per_model'].items():
        lines.append(f'| {model} | 36/36 | {counts.get("valid", 0)} | {counts.get("parser_failure", 0)} | {counts.get("technical_failure", 0)} |')
    lines += ['', '## FACT FROM OBSERVATION — integrity and database counts', '',
        f'All {x["spool_count"]} spool envelopes passed checksum, run/attempt identity, request and setup binding checks. '
        'Every response equals its persisted raw bytes. Every spool envelope is also archived byte-for-byte. '
        'The full strict parser replay matched stored outcomes and all prediction fields. No incomplete, duplicate or unmatched spool file remained.', '',
        'Spool: `/Users/aerfurt/University/Bachelor/rest_api_checker_spool/p2_sensitivity_exp2_20260926/`.', '',
        'Every row bound by the original candidate, including all original archived file bytes, remained unchanged. '
        'Experiment 1 still has 324 finalized runs, 324 attempts, 103 predictions and its sole original report. '
        f'Original report SHA-256: `{x["baseline_report_sha256"]}`.', '',
        '| Table | Before | After preparation | After execution | After D11 |',
        '| --- | --- | --- | --- | --- |']
    for table in x['database_before']:
        counts = [snapshot[table]['count'] for snapshot in (x['database_before'], p['database_after_preparation'],
                  x['database_after_execution'], d['database_after_d11'])]
        lines.append('| ' + table + ' | ' + ' | '.join(map(str, counts)) + ' |')
    lines += ['', '## FACT FROM PROTOCOL / OBSERVATION — D11 only', '',
        'Protocol §§6 and 9/D11 prescribe this diagnostic comparison after the approved wording runs; §10 requires '
        'its report before Gate C. D11 ran once only after clean completion and successful spool/evidence verification. '
        'The existing evaluator reused the original P2 outcomes, including their failures. It appended two archived '
        'files and one report row; it did not recalculate or replace Experiment 1 report 1.', '',
        f'- Entry point: `{d["evaluator_entrypoint"]}`.',
        f'- Report ID: {d["report_id"]}; version `{d["evaluator_version"]}`; evaluator SHA-256 `{d["evaluator_sha256"]}`.',
        f'- Report: `sensitivity-d11-evaluation-report.json`; SHA-256 `{d["report_sha256"]}`.',
        f'- Input: `sensitivity-d11-analysis-input.json`; SHA-256 `{d["input_sha256"]}`.',
        '- Pure D11 replay reproduces the persisted report. All pre-D11 rows remained unchanged.',
        '- No main evaluation, new ranking, winner, threshold, inferential metric or prompt reselection.', '',
        '| Prespecified measure | Original P2 | Wording variant |', '| --- | --- | --- |']
    for metric in ('Score', 'StableCorrect', 'Reliability', 'FullCase'):
        lines.append(f'| {metric} | {fraction(report["baseline"][metric])} | {fraction(report["variant"][metric])} |')
    lines += ['', f'Score delta: {fraction(report["Score_delta"])}.', '',
        '| Model | C1 delta | C2 delta | C3 delta | ModelCorrect delta | Paired valid coverage | Vector disagreement |',
        '| --- | --- | --- | --- | --- | --- | --- |']
    for model, values in report['models'].items():
        cells = [fraction(values['category_deltas'][c]) for c in ('c1', 'c2', 'c3')]
        cells += [fraction(values[k]) for k in ('ModelCorrect_delta', 'paired_valid_coverage', 'vector_disagreement')]
        lines.append('| ' + model + ' | ' + ' | '.join(cells) + ' |')
    lines += ['', 'The report retains all prespecified per-repetition category results, model/category stability, '
        'repeat disagreement and coverage, outcome rates, full-case correctness, valid-pair category/vector disagreement, '
        'excluded failure pairs and complete terminal transition tables. Empty conditional denominators remain N/A.', '',
        '## Exact next step', '',
        'Author review and interpretation of the completed comparison plus D11 sensitivity evidence. Then prepare the '
        'Gate C final selected-prompt freeze under protocol §10, preserving the original P2 selection and obtaining a '
        'separate actual author approval bound to exact artifact hashes. This execution acceptance is not Gate C approval. '
        'Do not begin main/final evaluation under this handoff.', '',
        '## Evidence and versioning', '',
        'The package includes acceptance, gate receipts, invocation/console/exit evidence, final counts, spool verification, '
        'the diagnostic input/report, and audit scripts. SHA256SUMS binds the package; full raw evidence remains in the SQL '
        'archive and original spool. The execution commit remains the exact approved commit above; an evidence-only commit, '
        'if made, is reported separately. No implementation or frozen scientific input was changed. No research, thesis or '
        'literature file was written. No push was performed.', '']
    with (E / 'HANDOFF.md').open('x') as out:
        out.write('\n'.join(lines))
    print(str(E / 'HANDOFF.md'))


if __name__ == '__main__':
    main()
