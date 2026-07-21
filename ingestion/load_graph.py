"""
load_graph.py — Reads extracted_graph.json (produced by extract.py) and writes
it into Neo4j AuraDB as real nodes and relationships. This is Step 2 of Day 2.
"""

import os
import json
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USERNAME = os.environ["NEO4J_USERNAME"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))


def clear_graph(tx):
    """Wipes the graph clean — useful when re-running ingestion during dev."""
    tx.run("MATCH (n) DETACH DELETE n")


def create_node(tx, node: dict):
    node_id = node["id"]
    node_type = node["type"]
    properties = node.get("properties", {})
    properties["id"] = node_id  # ensure id is always queryable as a property too

    # Using MERGE on id so re-running ingestion doesn't create duplicates.
    # Node label is dynamic, so we build the query string carefully (label names
    # are validated against schema.py's NODE_TYPES before this is ever called).
    query = f"""
    MERGE (n:{node_type} {{id: $id}})
    SET n += $properties
    """
    tx.run(query, id=node_id, properties=properties)


def create_relationship(tx, rel: dict):
    query = f"""
    MATCH (a {{id: $from_id}})
    MATCH (b {{id: $to_id}})
    MERGE (a)-[r:{rel['type']}]->(b)
    SET r += $properties
    """
    tx.run(
        query,
        from_id=rel["from_id"],
        to_id=rel["to_id"],
        properties=rel.get("properties", {}),
    )


def load_graph(json_path: str, wipe_first: bool = True):
    from schema import NODE_TYPES, RELATIONSHIP_TYPES

    with open(json_path) as f:
        data = json.load(f)

    driver = get_driver()

    with driver.session() as session:
        if wipe_first:
            print("Clearing existing graph...")
            session.execute_write(clear_graph)

        print(f"Loading {len(data['nodes'])} nodes...")
        skipped_nodes = 0
        for node in data["nodes"]:
            if node["type"] not in NODE_TYPES:
                print(f"  [SKIP] Unknown node type '{node['type']}' for id={node['id']}")
                skipped_nodes += 1
                continue
            session.execute_write(create_node, node)

        print(f"Loading {len(data['relationships'])} relationships...")
        skipped_rels = 0
        failed_rels = 0
        for rel in data["relationships"]:
            if rel["type"] not in RELATIONSHIP_TYPES:
                print(f"  [SKIP] Unknown relationship type '{rel['type']}'")
                skipped_rels += 1
                continue
            try:
                session.execute_write(create_relationship, rel)
            except Exception as e:
                print(f"  [FAIL] {rel['from_id']} -{rel['type']}-> {rel['to_id']}: {e}")
                failed_rels += 1

    driver.close()
    print(f"\nDone. Skipped {skipped_nodes} nodes, {skipped_rels} relationships "
          f"(unknown types), {failed_rels} relationships failed (likely missing endpoint node).")


if __name__ == "__main__":
    load_graph("extracted_graph.json", wipe_first=True)
