"""Single-run parity and evidence safety over fabricated immutable projections."""
from copy import deepcopy
from html import unescape
from html.parser import HTMLParser
import json
import re

import pytest

from .browser_fixture import HASH, HOSTILE, experiment


class PreText(HTMLParser):
    """Recover displayed text, proving escaping did not change stored content."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_pre = False
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        if tag == 'pre':
            self.in_pre = True
            self.blocks.append('')

    def handle_endtag(self, tag):
        if tag == 'pre':
            self.in_pre = False

    def handle_data(self, data):
        if self.in_pre:
            self.blocks[-1] += data


def pre_blocks(html):
    parser = PreText()
    parser.feed(html)
    return parser.blocks


@pytest.fixture
def interactive(queries, monkeypatch):
    original_detail = queries.run_detail
    original_experiments = queries.experiments
    context = dict(experiment(20009), name='LIVE-ADHOC FABRICATED-PRIVATE-UUID',
                   planned=2, completed=1, pending=1, valid=1, is_interactive=True)
    row = queries.run_rows[0]
    row.update(experiment_id=context['id'], context_name=context['name'], is_interactive=True,
               case='V2-EDX-002', model='gemma3:27b', prompt='P2', repetition=1)
    for category in ('c1', 'c2', 'c3'):
        row['reference_'+category] = row['prediction_'+category] = 'PASS'
    detail = original_detail(1)
    detail['reference'] = dict(c1='PASS', c2='PASS', c3='PASS', version=1)
    detail['prediction'].update(c1='PASS', c2='PASS', c3='PASS')
    detail['case_details'].update(reference=detail['reference'], status_code=200,
                                  origin='natural_observation', path='/edx/validation/stream')
    detail['run'].update(path='/edx/validation/stream')

    def get_detail(identifier, tab='reasons'):
        if identifier != 1:
            return original_detail(identifier, tab)
        queries.calls.append(('run_detail', dict(id=identifier, tab=tab)))
        return deepcopy(detail)

    monkeypatch.setattr(queries, 'run_detail', get_detail)
    monkeypatch.setattr(queries, 'experiments', lambda: [deepcopy(context), *original_experiments()])
    monkeypatch.setattr(queries, 'latest_interactive_run', lambda: deepcopy(row))
    return detail, context, row


def main_detail(html):
    return html.split('<details class="technical">', 1)[0]


def test_latest_redirects_directly_to_stored_interactive_run(client, interactive):
    response = client.get('/runs/latest', follow_redirects=False)
    assert response.status_code == 307
    assert response.headers['location'] == '/runs/1'


def test_latest_without_interactive_data_falls_back_to_runs(client):
    response = client.get('/runs/latest', follow_redirects=False)
    assert response.status_code == 307
    assert response.headers['location'] == '/runs'


def test_interactive_detail_header_is_human_readable(client, interactive):
    response = client.get('/runs/1')
    assert response.status_code == 200
    hero = response.text.split('<header class="run-hero">')[1].split('</header>')[0]
    for value in ('V2-EDX-002', 'EDX', 'POST /edx/validation/stream', 'Gemma 3 27B',
                  'Prompt', 'P2', 'Repetition', 'Duration', '4.0 s', 'VALID', 'CORRECT'):
        assert value in hero
    assert 'Run ID' not in hero and '20009' not in hero and 'LIVE-ADHOC' not in hero


@pytest.mark.parametrize(('changed', 'outcome', 'prediction_vector', 'matches', 'mismatches'), [
    (False, 'CORRECT', 'PPP', 3, 0),
    (True, 'INCORRECT', 'PPF', 2, 1),
])
def test_reference_prediction_matrix_matches_cli_semantics(client, interactive, changed,
                                                          outcome, prediction_vector, matches, mismatches):
    detail, _, _ = interactive
    if changed:
        detail['prediction']['c3'] = 'FAIL'
    response = client.get('/runs/1')
    view = response.context['detail_view']
    assert view['semantic_result'] == outcome
    assert view['reference_vector'] == 'PPP' and view['prediction_vector'] == prediction_vector
    assert [r['label'] for r in view['comparison']] == ['C1 Status', 'C2 Media Type', 'C3 Body Schema']
    matrix = response.text.split('<table class="comparison-matrix category-comparison">')[1].split('</table>')[0]
    assert all(f'>{label}</th>' in matrix for label in ('Check', 'Reference', 'Prediction', 'Match'))
    assert matrix.count('class="match-positive"') == matches
    assert matrix.count('class="match-negative"') == mismatches


@pytest.mark.parametrize('result', ['parser_failure', 'technical_failure', None])
def test_invalid_and_pending_outputs_never_infer_verdicts_from_stale_prediction(client, interactive, result):
    detail, _, _ = interactive
    detail['run']['result'] = result
    # Deliberately retain a seemingly correct persisted prediction to test gating.
    detail['prediction']['c1_reason'] = 'STALE REASON MUST NOT BE PRESENTED'
    response = client.get('/runs/1')
    view = response.context['detail_view']
    assert view['semantic_result'] == 'NO USABLE PREDICTION'
    assert view['prediction_vector'] == '—'
    assert all(r['prediction'] is None and r['match'] is None for r in view['comparison'])
    assert not view['reasons']
    assert 'No category verdict was inferred.' in response.text
    assert 'STALE REASON MUST NOT BE PRESENTED' not in response.text


def test_applicability_verdict_has_na_badge_and_matches(client):
    response = client.get('/runs/1')
    assert 'title="NOT_APPLICABLE">N/A</span>' in response.text
    c3 = response.context['detail_view']['comparison'][2]
    assert c3['reference'] == c3['prediction'] == 'NOT_APPLICABLE' and c3['match']


def test_reasons_remain_separate_and_html_escaped(client, interactive):
    response = client.get('/runs/1')
    assert 'Model reasons' in response.text
    assert 'Fabricated model reason; not reference truth.' in response.text
    assert HOSTILE not in response.text and '&lt;script&gt;' in response.text
    matrix = response.text.split('<table class="comparison-matrix category-comparison">')[1].split('</table>')[0]
    assert 'Fabricated model reason' not in matrix


def test_case_details_match_stored_reference_and_service(client, interactive):
    response = client.get('/runs/1')
    view = response.context['detail_view']
    assert view['service'] == 'EDX' and view['status_code'] == 200
    assert view['operation'] == 'POST /edx/validation/stream'
    assert view['content_type'] == 'application/json'
    assert view['case_type'] == 'Conforming' and view['overall_reference'] == 'CONFORMING'
    assert view['case_description'] and view['case_description'] in unescape(response.text)


def test_resistance_service_alias_and_case_category_use_cli_presenter(client, interactive):
    detail, _, _ = interactive
    detail['case_details'].update(service='htts', path='/resistance/validation/file',
                                  reference=dict(c1='PASS', c2='PASS', c3='FAIL'))
    detail['reference']['c3'] = 'FAIL'
    response = client.get('/runs/1')
    view = response.context['detail_view']
    assert view['service'] == 'Resistance'
    assert view['case_type'] == 'C3 Body Schema' and view['overall_reference'] == 'INCONSISTENT'


def test_file_links_are_scoped_and_private_provenance_is_unavailable(client, interactive):
    response = client.get('/runs/1')
    files = response.context['detail_view']['files']
    assert [f['label'] for f in files] == ['Observed response body', 'OpenAPI contract',
                                         'Original input file', 'Reference / explanation']
    for index, item in enumerate(files):
        assert item['url'] == f'/runs/1/files/{index}' and item['url'] in response.text
        viewed = client.get(item['url'])
        assert viewed.status_code == 200
        assert item['label'] in viewed.text
        assert '/Users/fabricated/' not in viewed.text
    assert 'Case provenance' not in response.text
    for url in ('/runs/1/files/4', '/runs/1/files/9999', '/runs/1/files/-1', '/runs/99999/files/0'):
        assert client.get(url).status_code == 404


def test_observed_evidence_is_exact_escaped_text(client, interactive):
    detail, _, _ = interactive
    response = client.get('/runs/1/files/0')
    assert response.status_code == 200
    assert detail['files'][0]['content'] in pre_blocks(response.text)
    assert HOSTILE not in response.text and '<img src=x' not in response.text


def test_reference_metadata_omits_secrets_and_paths_without_changing_stored_object(client, interactive):
    detail, _, _ = interactive
    value = dict(c1='PASS', authorization='Bearer FABRICATED-SECRET',
                 nested=dict(api_key='FABRICATED-KEY', location='/Users/fabricated/private/input.json'))
    detail['files'][3]['content'] = json.dumps(value)
    original = deepcopy(detail)
    response = client.get('/runs/1/files/3')
    assert response.status_code == 200
    assert 'FABRICATED-SECRET' not in response.text and 'FABRICATED-KEY' not in response.text
    assert '/Users/fabricated/' not in response.text
    assert 'private metadata omitted' in response.text and 'local path omitted' in response.text
    assert 'PASS' in response.text and detail == original


def test_raw_model_response_is_exact_collapsed_and_parser_error_is_preserved(client, interactive):
    detail, _, _ = interactive
    detail['run']['result'] = 'parser_failure'
    diagnostic = dict(status='invalid', code='CATEGORY_FIELDS', path='$.c1')
    detail['runtime_evidence']['parser_diagnostics'] = diagnostic
    detail['parser_error'] = diagnostic
    original = deepcopy(detail)
    response = client.get('/runs/1')
    assert detail['raw_model_response'] in pre_blocks(response.text)
    assert json.dumps(diagnostic) in pre_blocks(response.text)
    raw = re.search(r'<details\b[^>]*id="raw-response"[^>]*>', response.text).group()
    assert not re.search(r'\bopen\b', raw)
    opened = client.get('/runs/1?tab=raw')
    raw = re.search(r'<details\b[^>]*id="raw-response"[^>]*>', opened.text).group()
    assert re.search(r'\bopen\b', raw) and detail == original


def test_legacy_attempt_evidence_omits_private_diagnostics_and_preserves_provider(client, interactive):
    detail, _, _ = interactive
    detail['runtime_evidence']['parser_diagnostics'] = dict(status='invalid', code='CATEGORY_FIELDS')
    detail['evidence'] = [
        dict(title='Attempt 1: Persisted diagnostics', content=json.dumps(dict(
            spool='/Users/fabricated/private/recovery', password='FABRICATED-PRIVATE-SECRET',
            parser=dict(status='invalid', code='CATEGORY_FIELDS')))),
        dict(title='Attempt 1: Exact provider response', content=detail['raw_model_response']),
    ]
    original = deepcopy(detail)
    response = client.get('/runs/1?tab=attempts')
    assert response.status_code == 200
    assert 'FABRICATED-PRIVATE-SECRET' not in response.text and '/Users/fabricated/' not in response.text
    assert 'CATEGORY_FIELDS' in response.text
    assert detail['raw_model_response'] in pre_blocks(response.text)
    assert detail == original


def test_legacy_openapi_view_only_exposes_contract_evidence(client, interactive):
    detail, _, _ = interactive
    detail['evidence'] = [
        dict(title='Exact persisted OpenAPI contract', content='FABRICATED contract'),
        dict(title='Exact persisted request and rendered context', content='FABRICATED-PRIVATE-MODEL-REQUEST'),
    ]
    response = client.get('/runs/1?tab=openapi')
    assert response.status_code == 200
    assert 'FABRICATED contract' in response.text
    assert 'FABRICATED-PRIVATE-MODEL-REQUEST' not in response.text


def test_technical_identifiers_and_runtime_are_secondary_and_collapsed(client, interactive):
    response = client.get('/runs/1')
    technical = response.text.split('<details class="technical">')[1].split('</details>')[0]
    for value in ('Run ID', 'Experiment / context ID', '20009', 'Context name', 'LIVE-ADHOC',
                  'Model digest actually used', HASH, 'Ollama version', 'FABRICATED', 'Attempt 1', 'Prepared at'):
        assert value in technical
    assert 'LIVE-ADHOC' not in main_detail(response.text)
    assert 'Recovery directory' not in response.text and '/Users/' not in response.text


def test_navigation_links_previous_next_runs_and_latest_without_id_entry(client):
    response = client.get('/runs/2')
    assert response.status_code == 200
    navigation = response.text.split('aria-label="Run navigation">')[1].split('</nav>')[0]
    for path, label in (('/runs/1', 'Previous run'), ('/runs/3', 'Next run'),
                        ('/runs?experiment=1', 'Back to runs'), ('/runs/latest', 'Open latest run')):
        assert f'href="{path}"' in navigation and label in navigation


def test_runs_default_includes_all_contexts_and_readable_columns(client, queries, interactive):
    response = client.get('/runs')
    assert response.status_code == 200
    assert next(args for name, args in queries.calls if name == 'runs')['experiment_id'] is None
    for label in ('Case', 'Service', 'Model', 'Repetition', 'Parser status', 'Semantic result', 'Recorded'):
        assert f'>{label}</th>' in response.text
    assert 'href="/runs/1"' in response.text and 'V2-EDX-002' in response.text
    assert 'CORRECT' in response.text and 'LIVE-ADHOC' not in response.text


def test_runs_all_contexts_filter_form_accepts_blank_experiment(client, queries, interactive):
    response = client.get('/runs?experiment=&model=&prompt=&status=valid&search=V2-EDX&repetition=&page_size=50')
    assert response.status_code == 200
    args = next(args for name, args in queries.calls if name == 'runs')
    assert args['experiment_id'] is None and args['status'] == 'valid' and args['search'] == 'V2-EDX'
    assert 'V2-EDX-002' in response.text


def test_binary_file_view_exposes_metadata_only(client, interactive):
    detail, _, _ = interactive
    detail['files'][2].update(content='Non-UTF-8 bytes; exact base64:\nAAH/', size_bytes=3)
    response = client.get('/runs/1/files/2')
    assert response.status_code == 200 and 'Binary artifact' in response.text
    assert 'AAH/' not in response.text and not pre_blocks(response.text)
    assert '3 bytes' in response.text and HASH in response.text


def test_overview_latest_card_does_not_default_to_incomplete_interactive_context(client, interactive):
    response = client.get('/')
    assert response.status_code == 200
    assert response.context['selected_experiment'] == 1
    assert response.context['latest_run']['id'] == 1
    assert 'LATEST INTERACTIVE RUN' in response.text and 'Inspect latest run' in response.text
    assert 'LIVE-ADHOC' not in response.text and 'FABRICATED-PRIVATE-UUID' not in response.text


def test_explicit_interactive_overview_avoids_half_finished_batch_progress(client, interactive):
    response = client.get('/?experiment=20009')
    assert response.status_code == 200 and response.context['interactive']
    assert 'LIVE-ADHOC' not in response.text
    assert '1 / 2' not in response.text and '50.0%' not in response.text


def test_interactive_evaluation_redirects_attention_to_individual_runs_without_prompt_tabs(client, queries, interactive):
    response = client.get('/evaluation?experiment=20009')
    assert response.status_code == 200
    assert 'Aggregate evaluation is intended for completed experiment batches.' in response.text
    assert 'href="/runs?experiment=20009"' in response.text and 'href="/runs/latest"' in response.text
    assert 'aria-label="Prompt candidate"' not in response.text and '<canvas' not in response.text
    assert not any(name == 'report' for name, _ in queries.calls)


def test_final_experiment_pages_keep_persisted_projection_read_only(client, queries, monkeypatch):
    # The real DB is never touched: this deliberately bound fixture tests route behavior.
    final = experiment(10003, completed=True)
    final.update(name='FABRICATED final experiment', kind='evaluation', dataset_id=3)
    queries.run_rows[0]['experiment_id'] = 10003
    queries.saved_report['experiment_id'] = 10003
    original_rows, original_report = deepcopy(queries.run_rows), deepcopy(queries.saved_report)
    monkeypatch.setattr(queries, 'experiments', lambda: [deepcopy(final)])
    monkeypatch.setattr(queries, 'report', lambda identifier: deepcopy(queries.saved_report))
    for url in ('/?experiment=10003', '/evaluation?experiment=10003', '/runs?experiment=10003', '/runs/1'):
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers['X-RestApiChecker-UI'] == 'read-only'
    for method in ('post', 'put', 'patch', 'delete'):
        assert getattr(client, method)('/runs/1').status_code == 405
        assert getattr(client, method)('/runs/1/files/0').status_code == 405
    assert queries.run_rows == original_rows and queries.saved_report == original_report
