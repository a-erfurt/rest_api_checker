"""Display immutable evaluation values without evaluating or selecting a prompt.

The only arithmetic here converts an already persisted ratio to a percentage.
Run inspection uses the shared CLI comparison of stored verdicts. No aggregate
metrics are calculated and no outputs are parsed or repaired by the web layer.
"""
from collections.abc import Mapping


CATEGORIES = ("c1", "c2", "c3")
VERDICTS = ("PASS", "FAIL", "NOT_APPLICABLE")
METRICS = ("Score", "Robust", "StableCorrect", "Reliability", "FullCase")
RANKING_CRITERIA = (*METRICS, "Length", "Order")
BLUE, GREEN, CHARCOAL = "#003764", "#84AF00", "#41484f"
MODEL_NAMES = {
    "qwen3.6:27b": "Qwen",
    "gemma3:27b": "Gemma",
    "mistral-small3.2:24b": "Mistral",
}
MODEL_COLORS = dict(zip(MODEL_NAMES, (BLUE, GREEN, CHARCOAL)))
PROMPT_COLORS = dict(zip(("P1", "P2", "P3"), (BLUE, GREEN, CHARCOAL)))
VIEW_METRICS = {
    "models": ("Correctness", "StableCorrect", "Reliability", "FullCase"),
    "prompts": ("Correctness", "Robust", "StableCorrect", "Reliability", "FullCase"),
    "categories": ("Correctness", "StableCorrect"),
}


def model_name(value):
    """Preserve unknown persisted model identities rather than guessing families."""
    return MODEL_NAMES.get(value, value)


def percentage(value):
    """Presentation rounding only; undefined and missing ratios remain distinct."""
    if value is None or value.get("value") is None or not value.get("denominator"):
        return None
    return 100 * value["numerator"] / value["denominator"]


def format_ratio(value):
    if not isinstance(value, Mapping):
        return "Not available"
    numerator, denominator = value.get("numerator"), value.get("denominator")
    if numerator is None or denominator is None:
        return "Not available"
    percent = percentage(value)
    prefix = "N/A" if percent is None else f"{percent:.1f}%"
    return f"{prefix} ({numerator} / {denominator})"


def _dataset(label, values, color):
    return {
        "label": label,
        "data": [percentage(value) for value in values],
        "counts": [format_ratio(value) for value in values],
        "backgroundColor": color,
        "borderColor": color,
        "borderWidth": 1,
        "maxBarThickness": 42,
    }


def _chart(report, prompt, models, prompts, view, metric):
    cells = report["metrics"][prompt]["cells"]
    diagnostics = report["diagnostics"][prompt]
    datasets = []
    if view == "models":
        if metric in ("Correctness", "StableCorrect"):
            labels = [category.upper() for category in CATEGORIES]
            for model in models:
                values = cells[model] if metric == "Correctness" else diagnostics[model]["stable_correct"]
                datasets.append(_dataset(model_name(model), [values[c] for c in CATEGORIES],
                                         MODEL_COLORS.get(model, CHARCOAL)))
        else:
            labels = [prompt]
            key = {"Reliability": "reliability", "FullCase": "full_case"}[metric]
            for model in models:
                datasets.append(_dataset(model_name(model), [diagnostics[model][key]],
                                         MODEL_COLORS.get(model, CHARCOAL)))
        caption = f"{prompt} · {metric} by model. Each value comes from the persisted report."
    elif view == "prompts":
        if metric == "Correctness":
            labels = [f"{model_name(model)} · {c.upper()}" for model in models for c in CATEGORIES]
            for candidate in prompts:
                candidate_cells = report["metrics"][candidate]["cells"]
                values = [candidate_cells.get(model, {}).get(c) for model in models for c in CATEGORIES]
                datasets.append(_dataset(candidate, values, PROMPT_COLORS.get(candidate, CHARCOAL)))
        else:
            labels = [metric]
            for candidate in prompts:
                datasets.append(_dataset(candidate, [report["metrics"][candidate][metric]],
                                         PROMPT_COLORS.get(candidate, CHARCOAL)))
        caption = f"All prompt candidates · {metric}. The selected tab does not restrict this comparison."
    else:
        labels = [model_name(model) for model in models]
        for category, color in zip(CATEGORIES, (BLUE, GREEN, CHARCOAL)):
            values = [cells[model][category] if metric == "Correctness"
                      else diagnostics[model]["stable_correct"][category] for model in models]
            datasets.append(_dataset(category.upper(), values, color))
        caption = f"{prompt} · {metric} by category. C1, C2 and C3 retain separate report values."
    return {
        "type": "bar",
        "data": {"labels": labels, "datasets": datasets},
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "animation": False,
            "interaction": {"mode": "index", "intersect": False},
            "plugins": {"legend": {"position": "bottom"}},
            "scales": {
                "y": {"beginAtZero": True, "max": 100,
                      "title": {"display": True, "text": f"{metric} (%)"}},
                "x": {"grid": {"display": False}},
            },
        },
    }, caption


def evaluation_view(report, prompt=None, view="models", metric="Correctness"):
    """Project a completed persisted report; the caller enforces completion.

    This function never ranks candidates. A missing recorded selection stays
    missing even if a ranking or apparent winner happens to be present.
    """
    if report.get("format") != "comparison-evaluation-v1":
        raise ValueError("This evaluation report format is not supported by the web view")
    metrics = report["metrics"]
    if not metrics:
        raise ValueError("The persisted evaluation report contains no prompt metrics")
    prompts = sorted(metrics, key=lambda candidate: (candidate not in PROMPT_COLORS,
                                                     list(PROMPT_COLORS).index(candidate)
                                                     if candidate in PROMPT_COLORS else candidate))
    selected = report.get("selected_prompt")
    if selected not in metrics:
        selected = None
    if prompt not in metrics:
        prompt = selected or ("P1" if "P1" in metrics else prompts[0])
    if view not in VIEW_METRICS:
        view = "models"
    if metric not in VIEW_METRICS[view]:
        metric = "Correctness"
    model_cells = metrics[prompt]["cells"]
    models = [model for model in MODEL_NAMES if model in model_cells]
    models.extend(model for model in model_cells if model not in MODEL_NAMES)
    diagnostics = report["diagnostics"][prompt]
    rows = [dict(model=model, name=model_name(model), cells=model_cells[model],
                 diagnostic=diagnostics[model]) for model in models]
    chart, caption = _chart(report, prompt, models, prompts, view, metric)
    return {
        "prompt": prompt,
        "prompts": prompts,
        "selected_prompt": selected,
        "metrics": metrics[prompt],
        "metric_names": METRICS,
        "rows": rows,
        "categories": CATEGORIES,
        "verdicts": VERDICTS,
        "view": view,
        "chart_metric": metric,
        "chart_metrics": VIEW_METRICS[view],
        "chart": chart,
        "chart_caption": caption,
        "ranking": report.get("ranking", []),
        "ranking_criteria": RANKING_CRITERIA,
        "trace": report.get("tie_break_trace", []),
        "fabricated": report.get("fabricated") is True,
    }


# Single-run inspection shares the terminal's stored-verdict presentation rules.
def is_interactive(value):
    import re
    if isinstance(value, Mapping):
        if value.get('is_interactive') is not None:
            return bool(value['is_interactive'])
        value = value.get('name') or value.get('context_name') or value.get('experiment_name') or ''
    return bool(re.match(r'(?i)^live[- /]?(?:adhoc|ad-hoc|demo)(?:\b|[- /])', str(value or '')))


def context_name(value):
    name = value.get('name', '') if isinstance(value, Mapping) else value
    if is_interactive(value):
        timestamp = value.get('started_at') if isinstance(value, Mapping) else None
        return 'Interactive checks' + (' · ' + str(timestamp)[:16].replace('T', ' ') if timestamp else '')
    return name


def semantic_result(detail):
    from ..live_result import correct, usable, vector
    if not usable(detail):
        return 'NO USABLE PREDICTION', 'unavailable'
    if not detail.get('reference') or '?' in vector(detail['reference']):
        return 'UNAVAILABLE', 'unavailable'
    return ('CORRECT', 'correct') if correct(detail) else ('INCORRECT', 'incorrect')


def run_summary(row):
    from ..live_presenter import service_name
    reference = {c: row.get('reference_' + c) for c in CATEGORIES}
    prediction = {c: row.get('prediction_' + c) for c in CATEGORIES}
    prediction = prediction if all(prediction.values()) else None
    outcome, style = semantic_result(dict(run=row, reference=reference, prediction=prediction))
    return dict(row, service=service_name(row), semantic_result=outcome, semantic_class=style,
                timestamp=row.get('finished_at') or row.get('started_at') or row.get('prepared_at') or 'Not started')


def run_detail_view(detail, neighbors=None):
    from ..live_result import LABELS, usable, vector
    from ..live_presenter import case_type, describe_case, is_control, model_label, operation_label, service_name
    run = detail['run']
    case = dict(detail.get('case_details') or {})
    case.setdefault('reference', detail.get('reference'))
    for key in ('service', 'method', 'path'):
        case.setdefault(key, run.get(key))
    reference = detail.get('reference') or {}
    prediction = detail.get('prediction') if usable(detail) else None
    outcome, style = semantic_result(detail)
    rows = [dict(label=label, reference=reference.get(c), prediction=prediction.get(c) if prediction else None,
                 match=(prediction.get(c) == reference[c])
                 if prediction and reference.get(c) in VERDICTS else None)
            for c, label in zip(CATEGORIES, LABELS)]
    durations = [a['duration_ms'] for a in detail.get('attempts', []) if a.get('duration_ms') is not None]
    duration_ms = sum(durations) if durations else run.get('duration_ms')
    ref_vector = vector(reference)
    kind = dict(conforming='Conforming', c1='C1 Status', c2='C2 Media Type', c3='C3 Body Schema').get(
        case_type(case), 'Unavailable')
    if is_control(case):
        kind += ' · control'
    technical = {'Run ID': run.get('id'), 'Experiment / context ID': run.get('experiment_id'),
                 'Context name': run.get('context_name') or run.get('experiment_name'), 'Seed': run.get('seed'),
                 'Started at': run.get('started_at'), 'Finished at': run.get('finished_at')}
    # Persisted runtime facts only; never use the currently installed model as evidence.
    runtime = detail.get('runtime_evidence') or {}
    for key, label in (('model_digest', 'Model digest actually used'), ('ollama_version', 'Ollama version')):
        if runtime.get(key) is not None:
            technical[label] = runtime[key]
    if runtime.get('parser_diagnostics'):
        import json
        technical['Parser diagnostics'] = json.dumps(runtime['parser_diagnostics'], ensure_ascii=False)
    for attempt in detail.get('attempts', []):
        prefix = f"Attempt {attempt.get('attempt', '?')} · "
        for key, label in (('id', 'ID'), ('prepared_at', 'Prepared at'), ('started_at', 'Started at'),
                           ('finished_at', 'Finished at'), ('result', 'Result'), ('error_kind', 'Error kind'),
                           ('http_status', 'Provider HTTP status')):
            if attempt.get(key) is not None:
                technical[prefix + label] = attempt[key]
    files = [dict(label=f['label'], url=f"/runs/{run['id']}/files/{i}", available=True,
                  description=f"{f.get('size_bytes', '?')} bytes · stored evidence")
             for i, f in enumerate(detail.get('files', [])) if f.get('label') != 'Case provenance']
    neighbors = neighbors or {}
    return dict(service=service_name(case), operation=operation_label(case),
                model=model_label({'name': run.get('model')}), prompt=run.get('prompt'),
                repetition=run.get('repetition'), duration=f'{duration_ms / 1000:.1f} s' if duration_ms is not None else 'Not available',
                parser_status=run.get('result'), semantic_result=outcome, semantic_class=style,
                reference_vector=ref_vector, prediction_vector=vector(prediction), comparison=rows,
                reasons=[dict(label=label, text=prediction.get(c + '_reason') or 'No stored explanation.')
                         for c, label in zip(CATEGORIES, LABELS)] if prediction else [],
                overall_reference='CONFORMING' if ref_vector == 'PPP' else 'INCONSISTENT'
                    if ref_vector in ('FNN', 'PFN', 'PPF') else 'UNAVAILABLE',
                case_type=kind, case_description=describe_case(case)['description'],
                case_id=run.get('case_id'), status_code=case.get('status_code'), content_type=case.get('content_type'),
                files=files, raw_response=detail.get('raw_model_response'), parser_error=technical.get('Parser diagnostics') if run.get('result') == 'parser_failure' else None,
                technical={k: v for k, v in technical.items() if v is not None},
                previous_url=f"/runs/{neighbors['previous']['id']}" if neighbors.get('previous') else None,
                next_url=f"/runs/{neighbors['next']['id']}" if neighbors.get('next') else None)
