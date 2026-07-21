# Day 3 — RAG Copilot (Hybrid Graph + Vector Retrieval)

## What this does
Takes a natural-language question → searches Qdrant for relevant document
chunks → uses the equipment IDs found in those chunks to run targeted Neo4j
graph traversals (current vs superseded SOPs, similar incidents, regulatory
citations, tacit knowledge) → sends both to Gemini → returns a cited,
honest answer.

## Files
- `retrieve.py` — the hybrid retrieval logic (Qdrant + Neo4j)
- `synthesize.py` — turns retrieved context into a cited natural-language answer
- `test_questions.py` — runs your 8-10 test questions and self-checks the two
  critical demo moments

## Setup
1. Place these 3 files in a new folder, e.g. `rag/`, **alongside** (not inside)
   your existing `ingestion/` folder:
   ```
   your-project/
   ├── plant-docs/
   ├── ingestion/        <- Day 2 files
   └── rag/              <- these 3 new files
   ```
2. Copy your existing `.env` file into the `rag/` folder too (same Gemini,
   Neo4j, and Qdrant credentials — nothing new to sign up for).
3. From inside `rag/`:
   ```
   pip install -r ../ingestion/requirements.txt
   ```
   (Reuses the same dependencies from Day 2 — no new packages needed.)

## Run it
```
python test_questions.py
```
This runs all 10 questions one at a time (with delays between calls to respect
your daily/per-minute quota), printing each answer as it goes, then a summary
at the end checking:
- Q1 (PMP-204 maintenance) → did it correctly flag the superseded SOP?
- Q2 (why does PMP-204 keep failing) → did it correctly flag the recurring pattern?
- Q9 (HVAC unit, doesn't exist in our docs) → did it correctly say "not confident"
  instead of making something up?

Full results also get saved to `test_results.json` for later reference (useful
for your Day 10 pitch deck — you can quote real example Q&A pairs).

## What "good" looks like
- **Q1 answer** should mention something like: current procedure is a 90-day
  interval (not 180), and that the older version was superseded due to
  humidity-related seal failures.
- **Q2 answer** should explicitly connect APM-INC-031 and APM-INC-044 as the
  same recurring failure, not just describe one incident in isolation.
- **Q9 answer** should have a noticeably lower confidence score and should NOT
  invent plausible-sounding HVAC maintenance details — if it does invent
  details, that's a real problem to fix before the demo, since judges
  specifically watch for hallucination under exactly this kind of pressure.

## If something looks wrong
- **Empty `vector_chunks` or `graph_contexts`** for a question that should
  clearly match (like Q1, about PMP-204) → check that `load_vectors.py` and
  `load_graph.py` from Day 2 actually completed successfully; re-verify with
  the Neo4j/Qdrant checks from the Day 2 README.
- **Citations look wrong or missing** → open `test_results.json` and check the
  `_context_used` isn't being saved (it's intentionally stripped before saving
  to keep the file readable — re-run with print statements if you need to debug
  exactly what context the LLM saw).
- **Quota errors** → same daily-cap issue as Day 2; the script will tell you
  clearly via `SystemExit` if that's what happened. Wait for the reset or space
  out your testing across the day.

## Known limitations of this MVP (fine for now, worth knowing)
- Equipment-anchor detection only uses the `equipment_id` metadata tag from
  Qdrant chunks — if a question is phrased in a way that retrieves chunks with
  no equipment_id (e.g., a very generic SOP question), graph context will be
  empty and the answer will rely on vector search alone. This is an acceptable
  Day 3 limitation; Day 4-5 agents can be smarter about entity extraction from
  the question text itself if needed.
- No conversation memory — each question is independent. Fine for the demo's
  single-question-at-a-time flow.
