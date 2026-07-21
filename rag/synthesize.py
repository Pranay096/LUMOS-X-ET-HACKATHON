"""
synthesize.py — Takes the hybrid retrieval result (vector chunks + graph
context) and asks Gemini to produce a natural-language answer that cites its
sources by source_doc, distinguishes current from superseded information, and
says so explicitly when it isn't confident — this last point feeds the Day 8
"Documentation Gap" dashboard later.
"""

import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL_NAME = "gemini-2.5-flash-lite"
MAX_RETRIES = 4  # 503 "high demand" spikes can outlast a couple of quick retries

SYNTHESIS_SYSTEM_PROMPT = """You are an industrial knowledge copilot for plant
technicians and engineers. You answer questions using ONLY the context provided
to you below — never invent facts, equipment IDs, document numbers, or details
not present in the context.

RULES:
1. Every factual claim must be followed by a citation in the form [source: FILENAME].
   If a claim draws on multiple sources, cite all of them: [source: FILE1, FILE2].
2. If the context lists multiple SOPs for the same equipment, use the SUPERSEDES
   relationship to determine which is current: if SOP A "SUPERSEDES" SOP B, then
   A is current and B is outdated — always recommend the one that is NOT
   superseded by anything else. Explicitly mention that an older version exists
   and was superseded, and why if that reason is in the context (look for
   "Revised because of incidents").
3. If the context shows an equipment has multiple similar/recurring incidents,
   point this pattern out explicitly — this is exactly the kind of multi-hop
   insight this system exists to surface.
4. If the provided context does not contain enough information to confidently
   answer the question, say so plainly: do not guess or fill gaps with
   plausible-sounding but unsupported claims. Set your own confidence
   accordingly (see output format).
5. Keep the answer concise and actionable — this may be read on a small
   glasses display or spoken aloud, not just a desktop screen.
6. Return your response as JSON in exactly this structure, no markdown fences,
   no preamble:

{
  "answer": "the natural language answer, written for a technician, with inline [source: ...] citations",
  "confidence": 0.0-1.0,
  "cited_sources": ["list", "of", "every", "source_doc", "filename", "actually", "cited"],
  "used_superseded_check": true/false,
  "flagged_recurring_pattern": true/false
}
"""


def format_context_for_prompt(retrieval_result: dict) -> str:
    """Turns the structured retrieval result into readable text for the LLM,
    clearly separating vector-retrieved chunks from graph-derived facts."""
    parts = []

    parts.append("=== RELEVANT DOCUMENT EXCERPTS (vector search) ===")
    for chunk in retrieval_result["vector_chunks"]:
        parts.append(
            f"\n[source_doc: {chunk['source_doc']}] "
            f"[doc_type: {chunk['doc_type']}] [status: {chunk['status']}]\n"
            f"{chunk['text']}"
        )

    if retrieval_result["graph_contexts"]:
        parts.append("\n\n=== STRUCTURED KNOWLEDGE GRAPH FACTS ===")
        for ctx in retrieval_result["graph_contexts"]:
            parts.append(f"\nEquipment: {ctx['equipment_id']}")

            if ctx["current_sop"]:
                for sop in ctx["current_sop"]:
                    status_note = f" [status: {sop.get('status')}]" if sop.get("status") else ""
                    parts.append(
                        f"  Governing SOP: {sop.get('sop_id')} "
                        f"(rev {sop.get('revision')}){status_note} — \"{sop.get('title')}\""
                    )
                    if sop.get("superseded_id"):
                        parts.append(f"    -> This SUPERSEDES an older SOP: {sop.get('superseded_id')}")
                    if sop.get("revised_due_to"):
                        parts.append(f"    -> Revised because of incidents: {sop.get('revised_due_to')}")

            if ctx["similar_incidents"]:
                parts.append(f"  Incident history on this equipment:")
                for inc in ctx["similar_incidents"]:
                    parts.append(
                        f"    - {inc.get('incident_id')} ({inc.get('date')}, "
                        f"severity: {inc.get('severity')})"
                    )
                    if inc.get("similar_to"):
                        parts.append(f"      -> SIMILAR_TO recurring incidents: {inc.get('similar_to')}")

            if ctx["regulatory"]:
                parts.append(f"  Regulatory citations for this equipment's SOPs:")
                for reg in ctx["regulatory"]:
                    parts.append(f"    - {reg.get('reg_id')}: {reg.get('title')}")

            if ctx["tacit_knowledge"]:
                parts.append(f"  Undocumented/tacit knowledge available:")
                for t in ctx["tacit_knowledge"]:
                    parts.append(f"    - {t.get('id')} (from {t.get('source_doc')})")

    return "\n".join(parts)


def synthesize_answer(retrieval_result: dict) -> dict:
    """Calls Gemini to produce the final cited answer. Returns a dict matching
    the JSON schema described in SYNTHESIS_SYSTEM_PROMPT, plus the raw context
    used (for debugging/test-harness inspection)."""
    context_text = format_context_for_prompt(retrieval_result)
    question = retrieval_result["question"]

    prompt = f"QUESTION: {question}\n\nCONTEXT:\n{context_text}"

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYNTHESIS_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                ),
            )
            raw = response.text.strip()
            parsed = json.loads(raw)
            parsed["_context_used"] = context_text  # kept for test harness inspection
            return parsed
        except json.JSONDecodeError as e:
            last_error = e
            print(f"  [WARN] JSON parse failed (attempt {attempt}): {e}")
            time.sleep(5)
        except Exception as e:
            msg = str(e)
            if "PerDay" in msg or "RequestsPerDay" in msg:
                raise SystemExit(f"\nStopped: daily quota exhausted. Original error: {msg[:300]}")
            last_error = e
            if "503" in msg or "UNAVAILABLE" in msg:
                wait = 20 * attempt  # high-demand spikes benefit from longer waits
                print(f"  [RETRY {attempt}/{MAX_RETRIES}] Model overloaded (503). Waiting {wait}s...")
            else:
                wait = 10 * attempt
                print(f"  [RETRY {attempt}/{MAX_RETRIES}] {msg[:150]}")
            time.sleep(wait)

    return {
        "answer": f"[FAILED to generate answer after {MAX_RETRIES} attempts: {last_error}]",
        "confidence": 0.0,
        "cited_sources": [],
        "used_superseded_check": False,
        "flagged_recurring_pattern": False,
        "_context_used": context_text,
    }
