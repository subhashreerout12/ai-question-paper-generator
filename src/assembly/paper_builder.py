"""Pick questions from the bank to build a paper that matches the settings."""

import random

DIFFICULTY_MIX = {"easy": 0.3, "medium": 0.5, "hard": 0.2}


def _targets(n: int, mix: dict) -> dict:
    """Turn a total count into per-difficulty counts that add up to n."""
    counts = {d: int(n * share) for d, share in mix.items()}
    order = sorted(mix, key=lambda d: mix[d], reverse=True)
    i = 0
    while sum(counts.values()) < n:  # hand the leftovers to the biggest shares
        counts[order[i % len(order)]] += 1
        i += 1
    return counts


def pick(pool: list[dict], n: int, rng: random.Random, mix: dict = DIFFICULTY_MIX) -> list[dict]:
    """Choose n questions from pool, aiming for the difficulty mix."""
    by_diff = {d: [q for q in pool if q["difficulty"] == d] for d in mix}
    for items in by_diff.values():
        rng.shuffle(items)

    chosen = []
    for diff, target in _targets(n, mix).items():
        chosen += by_diff[diff][:target]

    if len(chosen) < n:  # not enough of some difficulty: fill from what is left
        taken = {q["id"] for q in chosen}
        leftover = [q for q in pool if q["id"] not in taken]
        rng.shuffle(leftover)
        chosen += leftover[: n - len(chosen)]

    rng.shuffle(chosen)
    return chosen[:n]


def build_paper(
    bank_questions: list[dict],
    n_mcq: int,
    n_short: int,
    seed: int | None = None,
    mix: dict = DIFFICULTY_MIX,
) -> dict:
    """Return a paper dict: {"mcq": [...], "short": [...], "total_marks": int, "warnings": [...]}.

    The same seed always gives the same paper; a different seed gives another set
    (use seeds 1 and 2 for Set A and Set B).
    """
    rng = random.Random(seed)
    mcq_pool = [q for q in bank_questions if q["type"] == "mcq"]
    short_pool = [q for q in bank_questions if q["type"] == "short"]

    warnings = []
    if len(mcq_pool) < n_mcq:
        warnings.append(f"Bank has only {len(mcq_pool)} MCQs; you asked for {n_mcq}.")
    if len(short_pool) < n_short:
        warnings.append(f"Bank has only {len(short_pool)} short-answer questions; you asked for {n_short}.")

    mcq = pick(mcq_pool, min(n_mcq, len(mcq_pool)), rng, mix)
    short = pick(short_pool, min(n_short, len(short_pool)), rng, mix)
    total = sum(q["marks"] for q in mcq + short)
    return {"mcq": mcq, "short": short, "total_marks": total, "warnings": warnings}
