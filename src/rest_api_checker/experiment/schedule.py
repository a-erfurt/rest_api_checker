"""Portable deterministic schedule, independent of Python random implementation."""
from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256

from .encoding import check, encode
from .request import MODELS, SEEDS

VERSION = 'comparison-schedule-v1'
SCHEDULE_SEED = 20260925
CASES = tuple(f'DEV-{i:02}' for i in range(1, 13))
PROMPTS = ('P1', 'P2', 'P3')


@dataclass(frozen=True, slots=True)
class Slot:
    case: str
    prompt: str
    model: str
    repetition: int
    seed: int
    run_order: int


def comparison_schedule():
    """Fisher-Yates, SHA-256 counter stream with unbiased 256-bit rejection.

    Initial lexicographic case/prompt/repetition order; independently domain-
    separated stream per model in the approved roster order. Seed is ASCII.
    """
    result = []
    for model in MODELS:
        block = [(case, prompt, r) for case in CASES for prompt in PROMPTS for r in SEEDS]
        counter = 0
        for i in range(len(block) - 1, 0, -1):
            bound = i + 1
            limit = 2**256 - 2**256 % bound
            while True:
                key = f'{VERSION}\n{SCHEDULE_SEED}\n{model}\n{counter}\n'.encode('ascii')
                counter += 1
                number = int.from_bytes(sha256(key).digest(), 'big')
                if number < limit:
                    break
            j = number % bound
            block[i], block[j] = block[j], block[i]
        for case, prompt, repetition in block:
            result.append(Slot(case, prompt, model, repetition, SEEDS[repetition], len(result) + 1))
    validate(result)
    return tuple(result)


def validate(slots):
    expected = {(c, p, m, r) for c in CASES for p in PROMPTS for m in MODELS for r in SEEDS}
    check(len(slots) == 324 and {(s.case, s.prompt, s.model, s.repetition) for s in slots} == expected,
          'SCHEDULE_IDENTITY_MISMATCH')
    check([s.run_order for s in slots] == list(range(1, 325)), 'SCHEDULE_ORDER_MISMATCH')
    check(all(s.seed == SEEDS[s.repetition] for s in slots), 'SCHEDULE_SEED_MISMATCH')
    check(Counter(s.prompt for s in slots) == dict.fromkeys(PROMPTS, 108), 'PROMPT_COUNTS')
    check(Counter(s.model for s in slots) == dict.fromkeys(MODELS, 108), 'MODEL_COUNTS')
    check(Counter((s.model, s.prompt) for s in slots) ==
          {(m, p): 36 for m in MODELS for p in PROMPTS}, 'MODEL_PROMPT_COUNTS')
    check([s.model for s in slots] == [m for m in MODELS for _ in range(108)], 'MODEL_BLOCK_ORDER')


def dry_run_bytes():
    return encode({'format': VERSION, 'schedule_seed': SCHEDULE_SEED,
                   'non_dispatched': True, 'slots': [asdict(s) for s in comparison_schedule()]})


def persist_comparison(repo, *, name, dataset_id, memberships, prompts, models, configs, setup):
    """Bind portable schedule identities to existing rows; no dispatch or model probing."""
    check(set(memberships) == set(CASES) and set(prompts) == set(PROMPTS)
          and set(models) == set(configs) == set(MODELS), 'INCOMPLETE_SCHEDULE_BINDINGS')
    repo.verify_comparison_bindings(dataset_id, memberships, prompts, models, configs)
    rows = [dict(dataset_case_id=memberships[s.case], prompt_id=prompts[s.prompt],
                 model_id=models[s.model], run_config_id=configs[s.model], repetition=s.repetition,
                 seed=s.seed, run_order=s.run_order) for s in comparison_schedule()]
    setup = {**setup, 'dataset_id': dataset_id, 'schedule_seed': SCHEDULE_SEED,
             'schedule_version': VERSION, 'schedule': rows, 'expected_runs': 324}
    return repo.plan_experiment(name=name, kind='comparison', dataset_id=dataset_id,
                               schedule_seed=SCHEDULE_SEED, setup=setup, schedule=rows)
