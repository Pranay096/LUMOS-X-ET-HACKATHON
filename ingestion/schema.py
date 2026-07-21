"""
schema.py — Knowledge graph schema definition, mirrors Day 1 schema doc exactly.
This is passed into the Gemini extraction prompt so every document is extracted
against the SAME schema, not whatever the model improvises per-document.
"""

NODE_TYPES = [
    "Plant", "Unit", "Zone", "Equipment", "SOP", "RegulatoryClause",
    "IncidentReport", "WorkOrder", "Engineer", "TacitKnowledge", "Vendor"
]

# FailureMode is intentionally excluded — per Day 1 schema doc, these are
# derived by the RCA agent later (Day 5), not extracted directly from documents.

RELATIONSHIP_TYPES = [
    "PART_OF", "LOCATED_IN", "MANUFACTURED_BY", "SUPPLIES_TO",
    "GOVERNS", "APPLIES_TO", "SUPERSEDES", "REFERENCES", "AUTHORED_BY",
    "CITES", "REVISED_DUE_TO", "MANDATES",
    "OCCURRED_ON", "REPORTED_BY", "RESULTED_IN", "SIMILAR_TO",
    "VIOLATES", "REPORTABLE_UNDER",
    "PERFORMED_ON", "PERFORMED_BY", "FOLLOWED_PROCEDURE",
    "EXPERT_IN", "AUTHORED", "RELATES_TO"
]

EXTRACTION_SYSTEM_PROMPT = f"""You are an information extraction system for an industrial knowledge graph.

Given a plant document, extract entities (nodes) and relationships matching EXACTLY this schema.
Do not invent node or relationship types outside this list.

VALID NODE TYPES: {", ".join(NODE_TYPES)}

VALID RELATIONSHIP TYPES: {", ".join(RELATIONSHIP_TYPES)}

Return ONLY valid JSON, no markdown fences, no preamble, in this exact structure:
{{
  "nodes": [
    {{"id": "unique_string_id", "type": "NodeType", "properties": {{"key": "value", ...}}}}
  ],
  "relationships": [
    {{"from_id": "node_id", "to_id": "node_id", "type": "RELATIONSHIP_TYPE", "properties": {{}}}}
  ]
}}

RULES:
1. Every node "id" must be a stable, human-readable string (e.g. "PMP-204", "APM-SOP-009-rev2", "R-Iyer").
   Reuse the SAME id for the same real-world entity if it appears in multiple documents
   (e.g. "PMP-204" should always be the id for that pump, in every document).
2. Every node must include a "source_doc" property set to the filename you were given.
3. Every node must include an "extraction_confidence" property: a float 0.0-1.0 reflecting
   how confident you are this entity/value was correctly extracted (use 1.0 only for
   explicit, unambiguous statements in the text).
4. Extract relationships explicitly stated OR strongly implied by the document text
   (e.g. a maintenance procedure for equipment X implies SOP-[GOVERNS]->Equipment).
5. For SOP documents that mention "Revision X (supersedes Revision Y)" or similar,
   ALWAYS create the SUPERSEDES relationship between the two SOP nodes.
6. For incident reports that explicitly reference another incident report as a recurrence
   or similar pattern, ALWAYS create a SIMILAR_TO relationship between them.
7. If a document references a clause that doesn't appear in this document, still create
   a node for it (e.g. a referenced RegulatoryClause) with lower confidence (~0.6) since
   you're inferring it exists rather than seeing its full text here.
8. Do not fabricate information not present in or strongly implied by the text.
"""
