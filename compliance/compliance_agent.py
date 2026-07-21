"""
compliance_agent.py — Checks an observed equipment/worker state against the
governing SOPs and regulatory clauses for that equipment, reasoning with a
LOCAL Ollama model (qwen3-vl:4b) instead of a cloud API.

DESIGN NOTE — the manual-input fallback:
check_compliance(equipment_id, observed_state) is the ONE function both
paths call. If the glasses' camera successfully reads a QR marker, the
caller passes the equipment_id it decoded. If the camera/glasses fail, the
same function is called with an equipment_id chosen from a manual dropdown
and an observed_state typed into a text box. There is no separate
"fallback code path" to maintain — the fallback IS this API shape.

DESIGN NOTE — no vector search needed here:
Given an equipment_id, the graph traversal below goes straight to that
equipment's governing SOPs and cited regulations — deterministic, no
embedding model required. Procedural detail (the actual PPE/LOTO wording)
comes from the `full_text` property attached by attach_full_text.py, not
from vector similarity search.
"""

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from ollama_client import generate_structured

load_dotenv()

neo4j_driver = GraphDatabase.driver(
    os.environ["NEO4J_URI"],
    auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
)

COMPLIANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["PASS", "FLAG", "UNKNOWN"]},
        "violated_requirement": {"type": ["string", "null"]},
        "citation": {"type": ["string", "null"]},
        "explanation": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["verdict", "explanation", "confidence"],
}

SYSTEM_PROMPT = """You are a plant safety compliance checker. You are given:
1. An OBSERVED STATE — what a technician or camera sees right now
2. GOVERNING PROCEDURES AND REGULATIONS — the actual SOP and regulatory text
   that applies to this equipment

Determine whether the observed state VIOLATES any requirement in the
governing procedures.

RULES:
1. Only flag a violation if it is clearly and specifically supported by the
   provided procedure text. Do not guess or infer requirements that are not
   actually stated in the text you were given.
2. If the observed state matches what the procedure requires, verdict is PASS.
3. If it clearly violates a stated requirement, verdict is FLAG. You MUST
   name the specific requirement violated (violated_requirement) and cite
   the source document ID (citation), e.g. "APM-SOP-014".
4. If the provided procedures do not contain enough information to make a
   confident determination — or no governing procedure was found at all —
   verdict is UNKNOWN. Do not guess to avoid an UNKNOWN verdict.
5. Set confidence between 0.0 and 1.0, reflecting how directly the procedure
   text supports your verdict. A PASS or FLAG based on explicit, unambiguous
   procedure text should be close to 1.0. Anything inferred should be lower.

Return ONLY JSON matching the given schema — no extra commentary."""


def fetch_requirements(equipment_id: str) -> dict:
    """Pulls the governing SOPs (with full text) and cited regulatory clauses
    for the given equipment via direct graph traversal.

    ROBUSTNESS NOTE: the Day 2 extraction (a small LLM run across 12 docs)
    doesn't reliably create every relationship type — LOCATED_IN and CITES
    in particular have been observed missing for some equipment. Relying
    solely on precise equipment/zone-based traversal means a real safety
    requirement (e.g. Zone B PPE rules) can silently go missing from the
    context, causing false PASS verdicts — worse than being slightly
    over-inclusive. So: try the precise traversal first, and ALWAYS also
    pull in every current SOP as a supplement, deduplicated. With only a
    handful of SOPs in this whole demo dataset, sending all of them is
    cheap and removes the dependency on extraction-fragile relationships.
    """
    with neo4j_driver.session() as session:
        precise_sops = session.run(
            """
            MATCH (e:Equipment {id: $eid})
            OPTIONAL MATCH (e)-[:LOCATED_IN]->(z:Zone)
            OPTIONAL MATCH (e)<-[:GOVERNS]-(s1:SOP)
            OPTIONAL MATCH (z)<-[:APPLIES_TO]-(s2:SOP)
            WITH collect(DISTINCT s1) + collect(DISTINCT s2) as candidate_sops
            UNWIND candidate_sops as s
            WITH DISTINCT s
            WHERE s IS NOT NULL
            RETURN s.id as sop_id, s.title as title, s.status as status,
                   s.full_text as full_text
            """,
            eid=equipment_id,
        ).data()

        # Supplement: every current SOP in the whole graph, regardless of
        # whether the (fragile) relationship extraction linked it to this
        # specific equipment/zone.
        all_current_sops = session.run(
            """
            MATCH (s:SOP)
            WHERE toLower(coalesce(s.status, '')) = 'current'
            RETURN s.id as sop_id, s.title as title, s.status as status,
                   s.full_text as full_text
            """
        ).data()

        regs = session.run(
            """
            MATCH (e:Equipment {id: $eid})<-[:GOVERNS]-(:SOP)-[:CITES]->(r:RegulatoryClause)
            RETURN DISTINCT r.id as reg_id, r.title as title, r.full_text as full_text
            """,
            eid=equipment_id,
        ).data()

    # Merge precise + supplement, deduplicated by sop_id, precise wins on conflict
    merged = {s["sop_id"]: s for s in all_current_sops}
    merged.update({s["sop_id"]: s for s in precise_sops if s.get("sop_id")})

    return {"equipment_id": equipment_id, "sops": list(merged.values()), "regulations": regs}


def format_requirements(requirements: dict) -> str:
    parts = [f"Equipment: {requirements['equipment_id']}"]

    if not requirements["sops"]:
        parts.append("(No governing SOPs found in the knowledge graph for this equipment.)")

    for sop in requirements["sops"]:
        parts.append(
            f"\n--- SOP: {sop.get('sop_id')} (status: {sop.get('status')}) "
            f"— \"{sop.get('title')}\" ---"
        )
        text = sop.get("full_text")
        if text:
            # Cap length — qwen3-vl:4b is a small local model; grammar-constrained
            # JSON decoding has been observed to fail (empty response) on longer
            # prompts, so keep this tight rather than generous.
            parts.append(text[:1800])
        else:
            parts.append(
                "(Full text not attached yet — run attach_full_text.py first. "
                "Only title/status known, cannot check specific requirements.)"
            )

    for reg in requirements["regulations"]:
        parts.append(f"\n--- Regulation: {reg.get('reg_id')} — \"{reg.get('title')}\" ---")
        text = reg.get("full_text")
        if text:
            parts.append(text[:1500])

    return "\n".join(parts)


def check_compliance(equipment_id: str, observed_state: str) -> dict:
    """Main entry point — the SAME function whether equipment_id came from a
    QR/marker scan (glasses) or a manual dropdown (fallback)."""
    requirements = fetch_requirements(equipment_id)
    requirements_text = format_requirements(requirements)

    user_prompt = (
        f"OBSERVED STATE: {observed_state}\n\n"
        f"GOVERNING PROCEDURES AND REGULATIONS:\n{requirements_text}"
    )

    result = generate_structured(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        json_schema=COMPLIANCE_SCHEMA,
    )
    result["equipment_id"] = equipment_id
    result["observed_state"] = observed_state
    return result


def close():
    neo4j_driver.close()
