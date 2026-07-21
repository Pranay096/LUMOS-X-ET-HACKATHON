"""
gap_tracker.py — Logs questions the Expert Copilot answered with low
confidence, so plant staff can see what's NOT well-documented yet. This is
the "Documentation Gap" feature: it turns the RAG system's own uncertainty
into a prioritized list of what to document next — directly demonstrating
the "knowledge cliff" framing from PS #8's problem statement.

Storage: a simple JSON file, not a database — appropriate for a hackathon
demo's data volume, and it means zero new infrastructure to set up or debug
under time pressure.
"""

import json
import os
from datetime import datetime, timezone

GAPS_FILE = "gaps.json"
CONFIDENCE_THRESHOLD = 0.5  # below this, a query gets logged as a gap


def _load() -> list:
    if not os.path.exists(GAPS_FILE):
        return []
    with open(GAPS_FILE, "r") as f:
        return json.load(f)


def _save(gaps: list):
    with open(GAPS_FILE, "w") as f:
        json.dump(gaps, f, indent=2)


def log_if_gap(question: str, answer_result: dict):
    """Call this after every /ask response. Logs the question if confidence
    is below threshold. Safe to call unconditionally — no-ops on high
    confidence answers."""
    confidence = answer_result.get("confidence")
    if confidence is None or confidence >= CONFIDENCE_THRESHOLD:
        return

    gaps = _load()
    gaps.append({
        "question": question,
        "confidence": confidence,
        "answer_given": answer_result.get("answer", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    _save(gaps)


def get_gaps() -> list:
    """Returns all logged gaps, most recent first."""
    gaps = _load()
    return list(reversed(gaps))


def clear_gaps():
    """Useful for resetting between demo rehearsals."""
    _save([])
