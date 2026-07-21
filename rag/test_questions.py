"""
test_questions.py — Runs a fixed set of test questions through the full RAG
pipeline (retrieve.py + synthesize.py) and prints the results so you can
eyeball whether the two critical demo moments actually work:
  1. The stale-SOP catch (PMP-204 maintenance question)
  2. The RCA pattern-match (PMP-204 "why does it keep failing")
Also includes general questions to sanity-check breadth, and one question
designed to NOT have a confident answer, to test the "say so honestly" rule.
"""

import os
import json
import time
from retrieve import retrieve, close as close_retrieve
from synthesize import synthesize_answer

TEST_QUESTIONS = [
    # 1. THE STALE-SOP CATCH — must surface Rev.2, mention Rev.1 is superseded, and why
    "How should I maintain the hydraulic coolant pump PMP-204?",

    # 2. THE RCA PATTERN-MATCH — must connect INC-031 and INC-044 as a recurring pattern
    "Why does PMP-204 keep failing?",

    # 3. Compliance/safety angle — LOTO near-miss + regulatory citation
    "What happened with the lockout-tagout near-miss on the hydraulic press?",

    # 4. Regulatory grounding — does it correctly cite REG-001 clauses?
    "What PPE is required to work in Zone B?",

    # 5. Cross-equipment — tests whether it stays equipment-specific, doesn't hallucinate
    "Is there a known issue with the air compressor CMP-301?",

    # 6. Tacit knowledge surfacing — the "knowledge cliff" feature
    "Are there any early warning signs for problems with PMP-204 that aren't in the official procedure?",

    # 7. Critical equipment / different failure mode
    "What caused the standby generator GEN-450 to fail its monthly test?",

    # 8. Specific document version check — direct test of supersession awareness
    "Is SOP-009 Revision 1 still valid to use?",

    # 9. Deliberately out-of-scope — equipment that doesn't exist in our docs.
    # This should trigger the "not confident, don't guess" rule, not a hallucination.
    "What is the maintenance schedule for the rooftop HVAC unit?",

    # 10. Broad/vague question — tests whether retrieval picks a sensible equipment anchor
    "What should a new technician know before working in the machining bay?",
]


def run_single_test(question: str, index: int, total: int) -> dict:
    print(f"\n{'=' * 70}")
    print(f"[{index}/{total}] QUESTION: {question}")
    print("=" * 70)

    retrieval_result = retrieve(question)
    print(f"  Vector chunks retrieved: {len(retrieval_result['vector_chunks'])}")
    print(f"  Equipment anchors found: {[c['equipment_id'] for c in retrieval_result['graph_contexts'] if c.get('equipment_id')] or 'none'}")

    result = synthesize_answer(retrieval_result)

    print(f"\n  ANSWER:\n  {result['answer']}")
    print(f"\n  Confidence: {result.get('confidence')}")
    print(f"  Cited sources: {result.get('cited_sources')}")
    print(f"  Used superseded-doc check: {result.get('used_superseded_check')}")
    print(f"  Flagged recurring pattern: {result.get('flagged_recurring_pattern')}")

    return {
        "question": question,
        "answer": result["answer"],
        "confidence": result.get("confidence"),
        "cited_sources": result.get("cited_sources"),
        "used_superseded_check": result.get("used_superseded_check"),
        "flagged_recurring_pattern": result.get("flagged_recurring_pattern"),
    }


RESULTS_PATH = "test_results.json"


def load_existing_results() -> dict:
    """Returns {question_text: result_dict} for any question that already
    produced a real (non-FAILED) answer on a prior run."""
    if not os.path.exists(RESULTS_PATH):
        return {}
    with open(RESULTS_PATH) as f:
        existing = json.load(f)
    return {
        r["question"]: r for r in existing
        if not str(r.get("answer", "")).startswith("[FAILED")
    }


def run_all_tests(delay_seconds: int = 8):
    """delay_seconds spaces out calls to stay well within daily/per-minute
    quota — each question makes 1 embedding call + 1 generation call.

    Resumable: any question that already has a real (non-FAILED) answer saved
    in test_results.json is skipped, so a 503 streak that kills a few
    questions doesn't cost you the ones that already succeeded."""
    existing = load_existing_results()
    if existing:
        print(f"Found {len(existing)} question(s) with existing successful answers — "
              f"will skip those and only run the rest.\n")

    results = []
    for i, question in enumerate(TEST_QUESTIONS, 1):
        if question in existing:
            print(f"[{i}/{len(TEST_QUESTIONS)}] SKIPPING (already succeeded): {question}")
            results.append(existing[question])
            continue

        result = run_single_test(question, i, len(TEST_QUESTIONS))
        results.append(result)

        # Save after every question, not just at the end — so a later failure
        # doesn't erase progress already made.
        with open(RESULTS_PATH, "w") as f:
            json.dump(results, f, indent=2)

        if i < len(TEST_QUESTIONS):
            time.sleep(delay_seconds)

    print(f"\n\n{'=' * 70}")
    print("SUMMARY — quick pass/fail self-check against the two critical moments")
    print("=" * 70)

    stale_sop_result = results[0]
    print(f"\n[1] Stale-SOP catch (Q1: '{stale_sop_result['question']}')")
    print(f"    used_superseded_check = {stale_sop_result['used_superseded_check']} "
          f"{'✅ PASS' if stale_sop_result['used_superseded_check'] else '❌ CHECK MANUALLY — expected True'}")

    rca_result = results[1]
    print(f"\n[2] RCA pattern-match (Q2: '{rca_result['question']}')")
    print(f"    flagged_recurring_pattern = {rca_result['flagged_recurring_pattern']} "
          f"{'✅ PASS' if rca_result['flagged_recurring_pattern'] else '❌ CHECK MANUALLY — expected True'}")

    out_of_scope_result = results[8]  # question 9
    print(f"\n[3] Out-of-scope honesty (Q9: '{out_of_scope_result['question']}')")
    print(f"    confidence = {out_of_scope_result['confidence']} "
          f"{'✅ PASS (low confidence as expected)' if (out_of_scope_result['confidence'] or 1) < 0.4 else '⚠️  CHECK MANUALLY — expected low confidence, got higher'}")

    failed_count = sum(1 for r in results if str(r.get("answer", "")).startswith("[FAILED"))
    if failed_count:
        print(f"\n⚠️  {failed_count} question(s) still failed after retries. "
              f"Just re-run this script — it will skip the questions that already "
              f"succeeded and only retry the failed ones.")

    print(f"\nFull results saved to {RESULTS_PATH}")

    close_retrieve()


if __name__ == "__main__":
    run_all_tests()
