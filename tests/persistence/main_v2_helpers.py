"""FABRICATED releases and native evidence, exclusively inside pytest temp dirs."""
from copy import deepcopy
import csv
import io
import json
from pathlib import Path

from rest_api_checker import main_v2 as main, main_v2_context as context, main_v2_release as release
from rest_api_checker.experiment.encoding import encode

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT.parent/'bachelor_rest_api_checker'
ARCHIVE = RESEARCH/'08_evaluation_v2/final_dataset_candidate_c_v1'


def csv_bytes(rows):
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def make_review(tmp_path, n=1):
    """Subset is a test fixture, never a proposed scientific membership change."""
    document = json.loads((ARCHIVE/'candidate_cases.json').read_bytes())
    cases = deepcopy(document['cases'][:n])
    ids = {c['candidate_id'] for c in cases}
    template = [r for r in release.csv_rows((ARCHIVE/'manual_review.csv').read_bytes()) if r['candidate_id'] in ids]
    families = release.csv_rows((ARCHIVE/'family_review.csv').read_bytes())[:1]
    for index, (case, row) in enumerate(zip(cases, template, strict=True), 1):
        case['candidate_id'] = row['candidate_id'] = f'TEST-ONLY-{index:03}'
        case['test_only'] = True
    families[0].update(comparison_id='TEST-COMPARISON', original_candidate_id=cases[0]['candidate_id'],
                       variant_candidate_id=cases[-1]['candidate_id'])
    decision = json.loads((ARCHIVE/'review_decisions.json').read_bytes())
    candidate_files = {
        'candidate_cases.json': encode(dict(case_count=n, cases=cases)),
        'manual_review.csv': csv_bytes(template), 'family_review.csv': csv_bytes(families),
        'review_decisions.json': encode(decision), 'coverage_summary.json': encode(dict(fabricated=True)),
        'runtime_plan.json': (ARCHIVE/'runtime_plan.json').read_bytes(),
        'source_bindings.json': (ARCHIVE/'source_bindings.json').read_bytes(),
        'scripts/verify_candidate.py': b'# FABRICATED test-only integrity result; never used outside pytest\nimport json\nprint(json.dumps(dict(status="PASS", archive_manifest_verified=True, human_review_gate_checked=True, ready_for_freeze=True, holds=[])))\n',
    }
    for c in cases:
        for key in ('response_evidence_file', 'contract_evidence_file', 'candidate_model_context_file',
                    'input_evidence_file', 'request_evidence_file', 'observation_provenance_file'):
            candidate_files[c[key]] = (ARCHIVE/c[key]).read_bytes()
    archive = tmp_path/'FABRICATED-candidate'
    release.publish(archive, release.seal(candidate_files, 'archive_manifest.json', test_only=True), research=RESEARCH)
    review_dir = tmp_path/'FABRICATED-review'
    review_dir.mkdir()
    for rows in (template, families):
        for row in rows:
            row.update(reviewer_status='APPROVED', reviewer_name='FABRICATED TEST REVIEWER', reviewed_at='2026-10-03T12:00:00+02:00')
            if 'candidate_id' in row:
                for cat in ('C1', 'C2', 'C3'):
                    row['reviewer_decision_'+cat] = row[cat+'_proposal']
                row['reviewer_decision_overall'] = row['overall_consistency']
    (review_dir/'manual_review.csv').write_bytes(csv_bytes(template))
    (review_dir/'family_review.csv').write_bytes(csv_bytes(families))
    decision.update(status='APPROVED', reviewer='FABRICATED TEST REVIEWER', reviewed_at='2026-10-03T12:00:00+02:00',
        coverage_losses_accepted=True, known_context_scope_accepted=True, no_independent_sample_claim_accepted=True)
    (review_dir/'review_decisions.json').write_bytes(encode(decision))
    return archive, review_dir


def make_release(tmp_path, n=1):
    archive, review_dir = make_review(tmp_path, n)
    integrity = tmp_path/'integrity.json'
    integrity.write_bytes(encode(release.check_integrity(archive, review_dir)))
    _, files, raw = release.checked_package(archive, 'archive_manifest.json')
    reviews = {n: (review_dir/n).read_bytes() for n in release.REVIEW_FILES}
    cases = release.reviewed(files, reviews)
    approval = tmp_path/'author.json'
    approval.write_bytes(encode(dict(decision='FREEZE_FINAL_EVALUATION_DATASET_V2', author='FABRICATED TEST AUTHOR',
        accepted_at='2026-10-03T12:00:00+02:00', version='FABRICATED-test-v2',
        **release.freeze_binding(raw, reviews, cases, integrity.read_bytes(), files))))
    return release.freeze_dataset(archive, review_dir, integrity, approval, tmp_path/'final',
                                   version='FABRICATED-test-v2', research=RESEARCH)


def prepared_context(tmp_path, n=1):
    final = make_release(tmp_path, n)
    prepared = tmp_path/'prepared'
    release.publish(prepared, main.request_files(final), research=RESEARCH)
    calls = []
    def transport(url, payload):
        calls.append((url, payload))
        if url.endswith('/api/chat'):
            assert payload['_debug_render_only'] is True and payload['truncate'] is False
            return encode({'_debug_info': {'rendered_template': '\n'.join(m['content'].strip() for m in payload['messages'])}})
        assert url == 'http://127.0.0.1:12345/tokenize'
        assert payload['add_special'] is payload['parse_special'] is True
        return encode(dict(tokens=[1, 2, 3]))
    directory = tmp_path/'context'
    context.measure(final, prepared, directory, root=tmp_path, research=RESEARCH, confirm=True,
        transport=transport, runner=lambda identity: ('FABRICATED tokenizer', 'http://127.0.0.1:12345/tokenize'),
        live_check=lambda *args: True)
    return final, prepared, directory, calls


def authorize(tmp_path, final, prepared, context_dir, dataset_id, database):
    raw = (prepared/'plan.json').read_bytes()
    context_raw = (context_dir/'manifest.json').read_bytes()
    path = tmp_path/'plan-authorization.json'
    path.write_bytes(encode(dict(decision='AUTHORIZE_MAIN_V2_PLAN', author='FABRICATED TEST AUTHOR',
        accepted_at='2026-10-03T12:00:00+02:00', **main.authorize_binding(final, raw, context_raw, dataset_id, database))))
    return path
