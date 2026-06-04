"""SM-2 spaced-repetition algorithm (pure, no DB).

Classic SM-2 grades each review on a 0..5 quality scale; this app grades answers
on a 0..100 score, so :func:`score_to_quality` maps one onto the other. The state
(``ease``, ``interval_days``, ``reps``) lives in ``ConceptMastery``; the DB-facing
update is in ``services/progress.py`` — this module is just the math, so it can be
unit-tested in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass

MIN_EASE = 1.3  # SM-2 floor — below this, intervals collapse
DEFAULT_EASE = 2.5
PASS_QUALITY = 3  # quality >= 3 counts as a successful recall


@dataclass(frozen=True)
class SM2State:
    ease: float
    interval_days: float
    reps: int


def score_to_quality(score: int) -> int:
    """Map a 0..100 answer score onto the SM-2 0..5 quality scale."""
    score = max(0, min(100, score))
    return round(score / 20)


def sm2_update(state: SM2State, quality: int) -> SM2State:
    """Return the next SM-2 state after a review of the given quality.

    On a lapse (quality < 3) the repetition count resets and the card is due
    again tomorrow, but the ease penalty still applies. On success the interval
    grows 1 → 6 → interval*ease. Ease is always nudged by the quality and floored
    at :data:`MIN_EASE`.
    """
    quality = max(0, min(5, quality))

    # Ease update (same formula for pass and lapse).
    ease = state.ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease = max(MIN_EASE, ease)

    if quality < PASS_QUALITY:
        return SM2State(ease=ease, interval_days=1.0, reps=0)

    reps = state.reps + 1
    if reps == 1:
        interval = 1.0
    elif reps == 2:
        interval = 6.0
    else:
        interval = max(1.0, round(state.interval_days * ease))

    return SM2State(ease=ease, interval_days=float(interval), reps=reps)
