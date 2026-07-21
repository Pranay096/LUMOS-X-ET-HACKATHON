"""
attach_full_text.py — One-time enrichment script. Reads the raw plant-docs
markdown files and attaches their full text as a `full_text` property on the
matching SOP and RegulatoryClause nodes in Neo4j (matched via the existing
source_doc property from Day 2 extraction).

WHY THIS EXISTS: the knowledge graph stores structured facts (title, revision,
status) but not full procedural detail — e.g. "face shield required within 2m
of WLD-077" only exists in the raw document text, not as a graph property.
The Compliance Agent needs that level of detail to judge a specific observed
state. Rather than adding a second embedding model just to fetch it, we
attach the text directly — deterministic, no LLM calls, no new dependency.

Run this ONCE after Day 2's load_graph.py has populated the graph, and again
any time plant-docs changes.
"""

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

driver = GraphDatabase.driver(
    os.environ["NEO4J_URI"],
    auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
)

DOC_FOLDER = "../plant-docs"


def attach_text(tx, source_doc: str, full_text: str) -> int:
    result = tx.run(
        """
        MATCH (n)
        WHERE n.source_doc = $source_doc AND (n:SOP OR n:RegulatoryClause)
        SET n.full_text = $full_text
        RETURN count(n) as updated
        """,
        source_doc=source_doc,
        full_text=full_text,
    )
    return result.single()["updated"]


def run():
    if not os.path.isdir(DOC_FOLDER):
        raise SystemExit(
            f"Can't find {DOC_FOLDER} — run this script from inside the "
            f"compliance/ folder, with plant-docs/ as a sibling of ingestion/, "
            f"rag/, and compliance/."
        )

    filenames = sorted(f for f in os.listdir(DOC_FOLDER) if f.endswith(".md"))
    total_updated = 0

    with driver.session() as session:
        for filename in filenames:
            filepath = os.path.join(DOC_FOLDER, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()

            updated = session.execute_write(attach_text, filename, text)
            if updated:
                print(f"  {filename}: attached full_text to {updated} node(s)")
            total_updated += updated

    print(f"\nDone. Attached full_text to {total_updated} node(s) total across "
          f"{len(filenames)} documents.")

    if total_updated == 0:
        print(
            "\nWARNING: 0 nodes updated. This usually means the source_doc "
            "property on your SOP/RegulatoryClause nodes doesn't match these "
            "filenames exactly. Check in Neo4j Browser:\n"
            "  MATCH (n:SOP) RETURN n.id, n.source_doc LIMIT 5"
        )

    driver.close()


if __name__ == "__main__":
    run()
