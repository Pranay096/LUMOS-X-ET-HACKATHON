"""
load_vectors.py — Chunks each document, embeds chunks using Gemini's free
gemini-embedding-001 model, and writes them to Qdrant with metadata for filtering.
This is Step 3 of Day 2, and runs independently of the graph load.

Uses the current `google-genai` SDK (NOT the deprecated `google-generativeai` package).

NOTE: text-embedding-004 was fully shut down by Google on January 14, 2026.
gemini-embedding-001 is its replacement. Unlike text-embedding-004, when you
request a non-default output dimension (we use 768 here, not the 3072 default),
gemini-embedding-001 does NOT auto-normalize the result — you must normalize
manually (see embed_text below), or similarity search quality silently degrades.
"""

import os
import time
import uuid
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

load_dotenv()

client_genai = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

QDRANT_URL = os.environ["QDRANT_URL"]
QDRANT_API_KEY = os.environ["QDRANT_API_KEY"]
COLLECTION_NAME = "plant_documents"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768  # one of Google's three recommended sizes (768, 1536, 3072)
RATE_LIMIT_DELAY_SECONDS = 2

# Maps filename prefixes to metadata. Edit this if you add more documents later.
DOC_METADATA = {
    "01_equipment_master_list.md": {"doc_type": "equipment_list", "status": "current", "equipment_id": None},
    "02_sop_pump_maintenance_v1_superseded.md": {"doc_type": "sop", "status": "superseded", "equipment_id": "PMP-204"},
    "03_sop_pump_maintenance_v2_current.md": {"doc_type": "sop", "status": "current", "equipment_id": "PMP-204"},
    "04_sop_ppe_zone_b.md": {"doc_type": "sop", "status": "current", "equipment_id": None},
    "05_sop_loto.md": {"doc_type": "sop", "status": "current", "equipment_id": None},
    "06_regulatory_excerpt.md": {"doc_type": "regulation", "status": "current", "equipment_id": None},
    "07_incident_pmp204_july.md": {"doc_type": "incident", "status": "closed", "equipment_id": "PMP-204"},
    "08_incident_pmp204_august_recurrence.md": {"doc_type": "incident", "status": "closed", "equipment_id": "PMP-204"},
    "09_incident_cmp301_routine.md": {"doc_type": "incident", "status": "closed", "equipment_id": "CMP-301"},
    "10_incident_prs088_loto_nearmiss.md": {"doc_type": "incident", "status": "closed", "equipment_id": "PRS-088"},
    "11_incident_gen450_battery.md": {"doc_type": "incident", "status": "closed", "equipment_id": "GEN-450"},
    "12_tacit_knowledge_engineer_notes.md": {"doc_type": "tacit_knowledge", "status": "uncontrolled", "equipment_id": None},
}


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Simple sliding-window chunker by character count. Good enough at this
    document scale — no need for a fancier semantic chunker for 12 documents."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def embed_text(text: str, max_retries: int = 3) -> list[float]:
    """Embeds text via gemini-embedding-001 at EMBEDDING_DIM dimensions.

    IMPORTANT: gemini-embedding-001 only returns a normalized (unit-length)
    vector at its default 3072 dimensions. At any other dimension (768 here),
    Google's docs say you must normalize manually, or cosine-similarity search
    quality degrades. This function does that normalization before returning.
    """
    from google.genai import errors

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            result = client_genai.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
                config=types.EmbedContentConfig(
                    output_dimensionality=EMBEDDING_DIM,
                    task_type="RETRIEVAL_DOCUMENT",
                ),
            )
            raw_vector = np.array(result.embeddings[0].values)
            normalized = raw_vector / np.linalg.norm(raw_vector)
            return normalized.tolist()
        except errors.ClientError as e:
            msg = str(e)
            if "PerDay" in msg or "RequestsPerDay" in msg:
                raise SystemExit(
                    f"\nStopped: daily quota exhausted for {EMBEDDING_MODEL}. "
                    f"This resets at midnight Pacific Time. Re-run this script after "
                    f"the reset — note this script does NOT currently save partial "
                    f"progress, so a re-run starts the whole collection over.\n"
                    f"Original error: {msg[:300]}"
                )
            elif "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                last_error = e
                wait = 10 * attempt
                print(f"  [RETRY {attempt}/{max_retries}] Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Gave up embedding text after {max_retries} attempts: {last_error}")


def setup_collection(client: QdrantClient):
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in collections:
        client.delete_collection(COLLECTION_NAME)
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )


def load_vectors(doc_folder: str):
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    setup_collection(client)

    filenames = sorted(f for f in os.listdir(doc_folder) if f.endswith(".md"))
    points = []

    for filename in filenames:
        metadata = DOC_METADATA.get(filename, {"doc_type": "unknown", "status": "unknown", "equipment_id": None})
        filepath = os.path.join(doc_folder, filename)

        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = chunk_text(text)
        print(f"{filename}: {len(chunks)} chunks")

        for chunk_index, chunk in enumerate(chunks):
            embedding = embed_text(chunk)
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "text": chunk,
                    "source_doc": filename,
                    "chunk_index": chunk_index,
                    **metadata,
                },
            )
            points.append(point)
            time.sleep(RATE_LIMIT_DELAY_SECONDS)

    print(f"\nUpserting {len(points)} chunks into Qdrant collection '{COLLECTION_NAME}'...")
    client.upsert(collection_name=COLLECTION_NAME, points=points)
    print("Done.")


if __name__ == "__main__":
    load_vectors("../plant-docs")
