"""Display immutable evaluation values without evaluating or selecting a prompt.

The only arithmetic here converts an already persisted ratio to a percentage.
No run-level outcomes, model reasons or references are scored by the web layer.
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
