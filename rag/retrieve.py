"""
retrieve.py — Hybrid retrieval: vector search (Qdrant) finds the relevant
equipment/topic, then graph traversal (Neo4j) pulls the structured facts
(current vs superseded SOPs, similar incidents, regulatory citations) that a
flat vector search alone cannot connect. This is the core of Day 3.
"""

import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from qdrant_client import QdrantClient
from neo4j import GraphDatabase
import numpy as np

load_dotenv()

client_genai = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
qdrant = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.environ["QDRANT_API_KEY"])
neo4j_driver = GraphDatabase.driver(
    os.environ["NEO4J_URI"],
    auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768
COLLECTION_NAME = "plant_documents"
VECTOR_TOP_K = 4  # how many chunks to retrieve from Qdrant per question


def embed_query(text: str) -> list[float]:
    """Same embedding model/dimension/normalization as load_vectors.py —
    MUST match exactly or vector similarity scores will be meaningless."""
    result = client_genai.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=EMBEDDING_DIM,
            task_type="RETRIEVAL_QUERY",  # NOTE: QUERY not DOCUMENT — asymmetric, matches how docs were embedded
        ),
    )
    raw_vector = np.array(result.embeddings[0].values)
    normalized = raw_vector / np.linalg.norm(raw_vector)
    return normalized.tolist()


def vector_search(question: str, top_k: int = VECTOR_TOP_K) -> list[dict]:
    """Returns the top-k most relevant document chunks with their metadata."""
    query_vector = embed_query(question)
    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
        with_payload=True,
    )
    return [
        {
            "text": point.payload.get("text", ""),
            "source_doc": point.payload.get("source_doc", "unknown"),
            "doc_type": point.payload.get("doc_type", "unknown"),
            "status": point.payload.get("status", "unknown"),
            "equipment_id": point.payload.get("equipment_id"),
            "score": point.score,
        }
        for point in results.points
    ]


def extract_equipment_ids(chunks: list[dict]) -> set[str]:
    """Pulls distinct equipment IDs referenced in the retrieved chunks, to use
    as anchors for graph traversal."""
    ids = {c["equipment_id"] for c in chunks if c.get("equipment_id")}
    return ids


def graph_context_for_equipment(equipment_id: str) -> dict:
    """Runs the structured traversal queries that mirror the Day 1 schema doc's
    worked example: current SOP + supersession chain, similar incidents,
    regulatory citations, and tacit knowledge — the facts a flat vector search
    cannot connect on its own."""
    with neo4j_driver.session() as session:

        current_sop = session.run(
            """
            MATCH (e:Equipment {id: $eid})<-[:GOVERNS]-(s:SOP)
            WHERE toLower(s.status) = 'current'
            OPTIONAL MATCH (s)-[:SUPERSEDES]->(old:SOP)
            OPTIONAL MATCH (s)-[:REVISED_DUE_TO]->(inc:IncidentReport)
            RETURN s.id as sop_id, s.title as title, s.revision as revision,
                   old.id as superseded_id, collect(DISTINCT inc.id) as revised_due_to
            """,
            eid=equipment_id,
        ).data()

        # Fallback: if no SOP matched status='current' (e.g. extraction used a
        # different status string than expected), fetch ALL governing SOPs
        # instead of silently returning nothing — better to show possibly-stale
        # info clearly labeled than to show no SOP context at all.
        if not current_sop:
            current_sop = session.run(
                """
                MATCH (e:Equipment {id: $eid})<-[:GOVERNS]-(s:SOP)
                OPTIONAL MATCH (s)-[:SUPERSEDES]->(old:SOP)
                OPTIONAL MATCH (s)-[:REVISED_DUE_TO]->(inc:IncidentReport)
                RETURN s.id as sop_id, s.title as title, s.revision as revision,
                       s.status as status, old.id as superseded_id,
                       collect(DISTINCT inc.id) as revised_due_to
                """,
                eid=equipment_id,
            ).data()

        similar_incidents = session.run(
            """
            MATCH (i:IncidentReport)-[:OCCURRED_ON]->(e:Equipment {id: $eid})
            OPTIONAL MATCH (i)-[:SIMILAR_TO]->(other:IncidentReport)
            RETURN i.id as incident_id,
                   coalesce(i.date, 'unknown date') as date,
                   coalesce(i.severity, 'unknown severity') as severity,
                   collect(DISTINCT other.id) as similar_to
            """,
            eid=equipment_id,
        ).data()

        regulatory = session.run(
            """
            MATCH (e:Equipment {id: $eid})<-[:GOVERNS]-(:SOP)
            OPTIONAL MATCH (e)<-[:GOVERNS]-(:SOP)-[:CITES]->(reg:RegulatoryClause)
            WITH reg WHERE reg IS NOT NULL
            RETURN DISTINCT reg.id as reg_id, reg.title as title
            """,
            eid=equipment_id,
        ).data()

        tacit = session.run(
            """
            MATCH (t:TacitKnowledge)-[:RELATES_TO]->(e:Equipment {id: $eid})
            RETURN t.id as id,
                   coalesce(t.topic, t.title, 'general note') as topic,
                   t.source_doc as source_doc
            """,
            eid=equipment_id,
        ).data()

    return {
        "equipment_id": equipment_id,
        "current_sop": current_sop,
        "similar_incidents": similar_incidents,
        "regulatory": regulatory,
        "tacit_knowledge": tacit,
    }


def retrieve(question: str) -> dict:
    """Full hybrid retrieval pipeline for one question. Returns everything
    needed to construct a grounded, cited answer."""
    chunks = vector_search(question)
    equipment_ids = extract_equipment_ids(chunks)

    graph_contexts = [graph_context_for_equipment(eid) for eid in equipment_ids]

    return {
        "question": question,
        "vector_chunks": chunks,
        "graph_contexts": graph_contexts,
    }


def close():
    neo4j_driver.close()
