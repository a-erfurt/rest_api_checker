"""Offline, human-input-only Evaluation-v2 release handoff. No SQL or inference."""
import csv
import io
import json
from pathlib import Path
import subprocess
import sys

from .experiment.encoding import digest, encode
from .persistence.database import require, timestamp

DATASET = 'FINAL_EVALUATION_DATASET_V2'
REVIEW_FILES = ('manual_review.csv', 'family_review.csv', 'review_decisions.json')


def safe_path(root, name):
    path = Path(name)
    require(not path.is_absolute() and '..' not in path.parts and bool(path.parts), 'Unsafe artifact path')
    result = Path(root)/path
    require(result.resolve().is_relative_to(Path(root).resolve()), 'Artifact escapes package')
    return result


def inventory(files):
    return [dict(path=n, sha256=digest(b), bytes=len(b)) for n, b in sorted(files.items())]


def checked_package(root, manifest_name):
    root = Path(root)
    raw = (root/manifest_name).read_bytes()
    require((root/Path(manifest_name).with_suffix('.sha256')).read_text().split()[0] == digest(raw),
            'Manifest integrity failed')
    manifest = json.loads(raw)
    files = {}
    for item in manifest['files']:
        name = item['path']
        require(name not in files, 'Duplicate artifact path')
        content = safe_path(root, name).read_bytes()
        require(digest(content) == item['sha256'] and len(content) == item['bytes'], 'Artifact integrity failed: '+name)
        files[name] = content
    return manifest, files, raw


def publish(root, files, *, research):
    root = Path(root).resolve()
    require(not root.is_relative_to(Path(research).resolve()), 'Research repository is read only')
    require(not root.exists(), 'New output directory required; never overwrite a release')
    root.mkdir(parents=True)
    for name, raw in sorted(files.items()):
        target = safe_path(root, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)


def seal(files, name, **metadata):
    raw = encode(dict(**metadata, files=inventory(files)))
    return {**files, name: raw, str(Path(name).with_suffix('.sha256')): (digest(raw)+'  '+name+'\n').encode()}


def csv_rows(raw):
    return list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))


def reviewed(candidate_files, reviews):
    """Validate human decisions; never synthesize, modify or filter a review row."""
    document = json.loads(candidate_files['candidate_cases.json'])
    cases = document['cases']
    ids = [c['candidate_id'] for c in cases]
    require(cases and len(ids) == len(set(ids)) and document['case_count'] == len(cases), 'Candidate identity/count mismatch')
    # archive_position belongs to each source capture. The candidate list itself
    # is the ordered membership authority; capture positions can repeat.
    for name, key in [('manual_review.csv', 'candidate_id'), ('family_review.csv', 'comparison_id')]:
        templates, decisions = csv_rows(candidate_files[name]), csv_rows(reviews[name])
        by_id = {r[key]: r for r in decisions}
        require(len(by_id) == len(decisions) == len(templates) and set(by_id) == {r[key] for r in templates}, 'Incomplete review coverage')
        if key == 'candidate_id':
            require([r[key] for r in templates] == ids, 'Review/candidate order mismatch')
        for template in templates:
            row = by_id[template[key]]
            require(set(row) == set(template), 'Review columns changed')
            require(all(row[k] == v for k, v in template.items() if not k.startswith('reviewer_') and k != 'reviewed_at'), 'Non-review fields changed')
            require(row['reviewer_status'] == 'APPROVED', 'Review PENDING/non-final; exclusions or replacements require a revised candidate')
            require(bool(row['reviewer_name'].strip()), 'Named human reviewer required')
            timestamp(row['reviewed_at'])
            if key == 'candidate_id':
                require(not row.get('reviewer_replacement_candidate_id'), 'Replacement requires revised candidate')
                case = next(c for c in cases if c['candidate_id'] == row[key])
                for category in ('C1', 'C2', 'C3'):
                    require(row['reviewer_decision_'+category] == row[category+'_proposal'] == case[category], 'Changed/incomplete reference requires revised candidate')
                require(row['reviewer_decision_overall'] == row['overall_consistency'] == case['overall_consistency'], 'Changed/incomplete overall reference')
    decision = json.loads(reviews['review_decisions.json'])
    template = json.loads(candidate_files['review_decisions.json'])
    require(decision.get('decisions_required') == template.get('decisions_required'), 'Required scientific decisions changed')
    require(decision['status'] == 'APPROVED' and bool(decision['reviewer'].strip()), 'Dataset review PENDING/non-final')
    timestamp(decision['reviewed_at'])
    for key in ('coverage_losses_accepted', 'known_context_scope_accepted', 'no_independent_sample_claim_accepted'):
        require(decision[key] is True, 'Unaccepted review gate: '+key)
    return cases


def review_binding(candidate_raw, reviews, cases):
    return dict(candidate_manifest_sha256=digest(candidate_raw), review_sha256={n: digest(b) for n, b in sorted(reviews.items())},
                ordered_case_ids=[c['candidate_id'] for c in cases])


def released_cases(cases, reviews):
    """Transcribe supplied final review into new membership records, not the archive."""
    decisions = {r['candidate_id']: r for r in csv_rows(reviews['manual_review.csv'])}
    result = []
    for position, candidate in enumerate(cases, 1):
        row = decisions[candidate['candidate_id']]
        result.append({**candidate, 'position': position, 'dataset_status': 'FROZEN',
            'manual_review_status': row['reviewer_status'], 'reference_status': 'HUMAN_CONFIRMED_REFERENCE',
            **{k: v for k, v in row.items() if k.startswith('reviewer_') or k == 'reviewed_at'},
            'accepted_review': row,
            'archived_candidate_status': {k: candidate[k] for k in
                ('dataset_status', 'manual_review_status', 'reference_status', 'reviewer_status')}})
    return result


def check_integrity(archive, review_dir):
    """Rerun the versioned archive's own offline checker, then bind exact inputs."""
    _, files, raw = checked_package(archive, 'archive_manifest.json')
    reviews = {n: (Path(review_dir)/n).read_bytes() for n in REVIEW_FILES}
    cases = reviewed(files, reviews)
    verifier = safe_path(archive, 'scripts/verify_candidate.py')
    require('scripts/verify_candidate.py' in files, 'Archived integrity verifier missing')
    command = [sys.executable, '-B', str(verifier), '--archive', str(Path(archive).resolve()),
               '--review-csv', str(Path(review_dir, REVIEW_FILES[0]).resolve()),
               '--family-review-csv', str(Path(review_dir, REVIEW_FILES[1]).resolve()),
               '--review-decisions', str(Path(review_dir, REVIEW_FILES[2]).resolve()), '--require-reviewed']
    result = subprocess.run(command, capture_output=True, check=False)
    require(result.returncode == 0, 'Candidate integrity verifier failed: '+result.stdout.decode(errors='replace')[-2000:])
    receipt = json.loads(result.stdout)
    require(receipt.get('status') == 'PASS' and receipt.get('archive_manifest_verified') is True
            and receipt.get('human_review_gate_checked') is True and receipt.get('ready_for_freeze') is True
            and not receipt.get('holds'), 'Failed candidate integrity receipt')
    # Refuse a concurrent edit while the external verifier was running.
    require(checked_package(archive, 'archive_manifest.json')[2] == raw
            and all((Path(review_dir)/n).read_bytes() == b for n, b in reviews.items()), 'Review changed during integrity check')
    return dict(format='main-v2-reviewed-integrity-v1', status='PASS', **review_binding(raw, reviews, cases),
                verifier_sha256=digest(files['scripts/verify_candidate.py']), verifier_result=receipt,
                verifier_stdout_sha256=digest(result.stdout), model_calls=0, prediction_writes=0)


def freeze_binding(raw, reviews, cases, integrity_raw, candidate_files):
    return dict(**review_binding(raw, reviews, cases), integrity_receipt_sha256=digest(integrity_raw),
                coverage_summary_sha256=digest(candidate_files['coverage_summary.json']),
                denominators=dict(observations=len(cases), exact_contexts=len({c['exact_model_context_sha256'] for c in cases}),
                                  response_pattern_groups=len({c['response_pattern_group'] for c in cases}),
                                  dependency_families=len({c['dependency_family'] for c in cases})))


def accepted(record, decision, expected):
    require(record.get('decision') == decision, 'Explicit human authorization required: '+decision)
    require(type(record.get('author')) is str and bool(record['author'].strip()), 'Named author required')
    timestamp(record.get('accepted_at'))
    require(all(record.get(k) == v for k, v in expected.items()), 'Human authorization binding mismatch')


def freeze_dataset(archive, review_dir, integrity_path, approval_path, output, *, version, research):
    _, files, candidate_raw = checked_package(archive, 'archive_manifest.json')
    reviews = {n: (Path(review_dir)/n).read_bytes() for n in REVIEW_FILES}
    cases = reviewed(files, reviews)
    integrity_raw, approval_raw = Path(integrity_path).read_bytes(), Path(approval_path).read_bytes()
    integrity = json.loads(integrity_raw)
    require(integrity == check_integrity(archive, review_dir), 'Failed/stale candidate integrity receipt')
    expected = freeze_binding(candidate_raw, reviews, cases, integrity_raw, files)
    accepted(json.loads(approval_raw), 'FREEZE_FINAL_EVALUATION_DATASET_V2', {**expected, 'version': version})
    require(type(version) is str and version.strip() and len(version) <= 32, 'Explicit final release version required')
    payload = {'candidate/'+n: b for n, b in files.items()}
    payload['candidate/archive_manifest.json'] = candidate_raw
    payload['candidate/archive_manifest.sha256'] = (digest(candidate_raw)+'  archive_manifest.json\n').encode()
    payload.update({'review/'+n: b for n, b in reviews.items()})
    payload.update({'integrity.json': integrity_raw, 'author-freeze.json': approval_raw})
    dataset = dict(format='final-evaluation-dataset-v2', name=DATASET, version=version, purpose='evaluation',
                   status='FROZEN', review_status=json.loads(reviews['review_decisions.json'])['status'],
                   **expected, cases=released_cases(cases, reviews))
    payload['dataset.json'] = encode(dataset)
    publish(output, seal(payload, 'freeze.json', format='main-v2-freeze-receipt-v1', status='FROZEN',
                         dataset_sha256=digest(payload['dataset.json'])), research=research)
    return load_release(output)


def load_release(root):
    receipt, files, raw = checked_package(root, 'freeze.json')
    dataset = json.loads(files['dataset.json'])
    require(receipt.get('format') == 'main-v2-freeze-receipt-v1' and dataset.get('format') == 'final-evaluation-dataset-v2'
            and receipt['status'] == dataset['status'] == 'FROZEN' and dataset['review_status'] == 'APPROVED'
            and dataset['name'] == DATASET and dataset['purpose'] == 'evaluation'
            and receipt['dataset_sha256'] == digest(files['dataset.json']), 'FINAL/FROZEN dataset required')
    candidate = {n.removeprefix('candidate/'): b for n, b in files.items() if n.startswith('candidate/')}
    reviews = {n: files['review/'+n] for n in REVIEW_FILES}
    cases = reviewed(candidate, reviews)
    require(dataset['cases'] == released_cases(cases, reviews), 'Final dataset/candidate/review identity mismatch')
    candidate_raw = candidate['archive_manifest.json']
    require(json.loads(candidate_raw)['files'] == inventory({n: b for n, b in candidate.items()
            if n not in ('archive_manifest.json', 'archive_manifest.sha256')}), 'Candidate source closure mismatch')
    expected = freeze_binding(candidate_raw, reviews, cases, files['integrity.json'], candidate)
    require(all(dataset[k] == v for k, v in expected.items()), 'Dataset identity mismatch')
    integrity = json.loads(files['integrity.json'])
    require(integrity.get('format') == 'main-v2-reviewed-integrity-v1' and integrity.get('status') == 'PASS'
            and all(integrity.get(k) == v for k, v in review_binding(candidate_raw, reviews, cases).items())
            and integrity.get('verifier_sha256') == digest(candidate['scripts/verify_candidate.py']), 'Failed candidate integrity receipt')
    result = integrity['verifier_result']
    require(result.get('status') == 'PASS' and result.get('ready_for_freeze') is True
            and result.get('archive_manifest_verified') is True and result.get('human_review_gate_checked') is True
            and not result.get('holds'), 'Failed candidate integrity receipt')
    accepted(json.loads(files['author-freeze.json']), 'FREEZE_FINAL_EVALUATION_DATASET_V2', {**expected, 'version': dataset['version']})
    return dict(root=Path(root), manifest=dataset, files=files, freeze_raw=raw, sha256=digest(raw))
