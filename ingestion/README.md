# Day 2 — Ingestion Pipeline Setup & Run Instructions

## What this does
Reads the 12 plant documents → extracts entities/relationships via Gemini (free tier)
→ writes them into Neo4j as a knowledge graph → separately chunks + embeds documents
into Qdrant for retrieval. By end of Day 2, both your graph and your vector store
should be populated and ready for Day 3 (RAG copilot).

## Setup (one-time, ~15 minutes)

1. **Get free API keys / instances:**
   - Gemini API key: https://aistudio.google.com/app/apikey (free, no card required)
   - Neo4j AuraDB Free instance: https://console.neo4j.io → "Create Free Instance" (no card required)
   - Qdrant Cloud free cluster: https://cloud.qdrant.io → create a free cluster

2. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```
   (If you're on a system that requires it: `pip install -r requirements.txt --break-system-packages`)

3. **Set up your environment file:**
   ```
   cp .env.example .env
   ```
   Then open `.env` and paste in your actual Gemini key, Neo4j URI/username/password,
   and Qdrant URL/API key (all from step 1).

4. **That's it for env setup.** The scripts automatically load your `.env` file
   (via `python-dotenv`), so you do NOT need to manually `export` anything —
   just make sure `.env` is in the same folder as the scripts when you run them.

5. **Make sure your `plant-docs` folder** (the 12 documents from Day 1) is one level
   above this `ingestion` folder, i.e.:
   ```
   your-project/
   ├── plant-docs/        <- the 12 .md files from Day 1
   └── ingestion/         <- this folder
   ```
   If your folder layout is different, edit the path in the `if __name__ == "__main__":`
   block at the bottom of `extract.py` and `load_vectors.py`.

## Run order (do these in this exact order)

### Step 1 — Extract entities/relationships from documents
```
python3 extract.py
```
This calls Gemini once per document (12 calls total, ~1 minute with rate-limit spacing)
and saves the result to `extracted_graph.json`. **Open this file and skim it** before
moving on — this is your one checkpoint to catch bad extractions before they go into
the graph. Look especially for: did it create a `SUPERSEDES` edge between the two
SOP-009 nodes? Did it create a `SIMILAR_TO` edge between INC-031 and INC-044?

### Step 2 — Load the graph into Neo4j
```
python3 load_graph.py
```
This wipes any existing graph (safe to re-run during development) and writes all
nodes/relationships from `extracted_graph.json`. Watch the console output for
`[SKIP]` or `[FAIL]` lines — a few `[FAIL]` lines on relationships are expected if
the extraction created a relationship pointing to a node that didn't get created
(usually fixable by re-running extract.py, or manually patching extracted_graph.json).

### Step 3 — Load embeddings into Qdrant
```
python3 load_vectors.py
```
This runs independently of Steps 1-2 — it re-reads the raw documents directly
(not the extracted JSON), chunks them, and embeds each chunk via Gemini. Takes
a few minutes due to one embedding call per chunk with rate-limit spacing.

## How to know Day 2 is actually done (not just "ran without crashing")

Open Neo4j AuraDB's browser query interface (link is in your AuraDB console) and run:

```cypher
MATCH (n) RETURN labels(n)[0] as type, count(*) as count ORDER BY count DESC
```
You should see counts across most of your 11 node types — if everything shows up
under one type, or several types are at zero, something went wrong in extraction.

Then run this to confirm your single most important relationship exists:
```cypher
MATCH (a:SOP)-[r:SUPERSEDES]->(b:SOP) RETURN a.id, r, b.id
```
This MUST return one row (Rev.2 supersedes Rev.1) — if it doesn't, your Day 3 "stale
SOP catch" demo moment has no data behind it. Fix this before moving to Day 3.

And confirm the RCA pattern-match edge:
```cypher
MATCH (a:IncidentReport)-[r:SIMILAR_TO]->(b:IncidentReport) RETURN a.id, r, b.id
```
This MUST return one row (INC-031 similar to INC-044) for the same reason.

For Qdrant, the easiest check is the Qdrant Cloud dashboard's collection view —
confirm `plant_documents` collection shows roughly 30-40 points (12 docs, a few
chunks each).

## If something goes wrong

- **JSON parse errors in extract.py:** Gemini occasionally wraps JSON in markdown
  fences despite the `response_mime_type` setting. The current code expects raw JSON;
  if you see `[WARN] Failed to parse JSON`, check the printed raw response — if it's
  wrapped in ```json fences, strip them before `json.loads()` (quick fix, ask your
  AI coding tool to add a `.strip('`').removeprefix('json')`-style cleanup).
- **Rate limit (429) errors:** increase `RATE_LIMIT_DELAY_SECONDS` in extract.py and
  load_vectors.py — free tier limits are generous but not unlimited.
- **Neo4j connection errors:** double check your AuraDB instance is not paused
  (free instances can auto-pause after inactivity — resume it from the console).
