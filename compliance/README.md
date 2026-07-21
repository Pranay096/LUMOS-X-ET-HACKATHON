# Day A — Compliance Agent (local, Ollama-based) + API layer

## What changed from the plan
- **Compliance Agent runs 100% locally** via Ollama + `qwen3-vl:4b` — no cloud
  API, no API key, no quota walls. This matches your real Lumos glasses
  product architecture (RTX 4050 laptop as local inference server), so the
  hackathon prototype and the real product story now match.
- **No new embedding model needed.** The agent goes straight from
  `equipment_id` → governing SOPs via graph traversal (deterministic, no
  vector search). Procedural detail comes from a `full_text` property
  attached directly to SOP/RegulatoryClause nodes — see `attach_full_text.py`.
- **Day 3's RAG (`/ask`) stays on Gemini** — it's already built, tested, and
  working. Re-platforming it to Ollama too is possible later but wasn't worth
  the risk with 2 days left; ask if you want that as a fast-follow.
- **The "manual-input fallback" is the API design itself**, not separate
  code: `check_compliance(equipment_id, observed_state)` doesn't know or care
  whether `equipment_id` came from a QR scan or a manual dropdown — both
  paths call the exact same function.

## One-time setup

### 1. Install Ollama
Download from **https://ollama.com/download** (Windows/Mac/Linux installer).
After installing, Ollama runs automatically in the background (check your
system tray / menu bar for its icon).

### 2. Pull the model
```
ollama pull qwen3-vl:4b
```
This downloads the model once (a few GB). Your RTX 4050 has enough VRAM to
run this comfortably.

### 3. Verify Ollama is working
```
ollama run qwen3-vl:4b "say hello in one word"
```
If this prints a response, you're good. If it hangs or errors, Ollama isn't
running correctly — check the desktop app.

### 4. Folder structure
```
your-project/
├── plant-docs/
├── ingestion/        (Day 2)
├── rag/              (Day 3 — still Gemini-based, untouched)
└── compliance/       (Day A — these files)
```

### 5. Install Python dependencies
```
cd compliance
pip install -r requirements.txt
```

### 6. Environment file
Copy your existing `.env` from `rag/` into `compliance/` — it already has
the Neo4j credentials this folder needs. (The Gemini key in there is still
used by `/ask`, which imports from `rag/`.)

### 7. Attach full document text to the graph (run once)
```
python attach_full_text.py
```
This reads your 12 plant-docs and attaches the raw text onto the matching
SOP/RegulatoryClause nodes in Neo4j — the Compliance Agent needs this to
reason about specific requirements (e.g. "face shield required within 2m of
WLD-077"), which isn't captured as a structured graph property.

**Verify it worked**: run this in Neo4j Browser —
```cypher
MATCH (s:SOP {id: "APM-SOP-014"}) RETURN s.full_text IS NOT NULL as has_text
```
Should return `true`.

## Test the Compliance Agent standalone
```
python test_compliance.py
```
Runs 4 scenarios (clear PPE violation, compliant state, LOTO violation,
ambiguous input) and self-checks the verdicts. This uses your GPU/CPU to run
`qwen3-vl:4b` locally — expect each check to take a few seconds, not
milliseconds, especially on the first call (model loads into memory).

**What "good" looks like:**
- Scenario 1 (no face shield) → `FLAG`, citing `APM-SOP-014`
- Scenario 2 (full PPE) → `PASS`
- Scenario 3 (no LOTO) → `FLAG`, citing `APM-SOP-017`
- Scenario 4 (vague) → `UNKNOWN`, not a confident guess

## Run the full API
```
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```
Two endpoints, both testable via curl or the auto-generated docs at
`http://localhost:8000/docs`:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How should I maintain PMP-204?"}'

curl -X POST http://localhost:8000/check-compliance \
  -H "Content-Type: application/json" \
  -d '{"equipment_id": "PMP-204", "observed_state": "Technician has no face shield on"}'
```

## If something goes wrong
- **"Could not connect to Ollama"** → Ollama desktop app isn't running.
  Restart it, or run `ollama serve` manually in a terminal.
- **"Model not pulled locally"** → run `ollama pull qwen3-vl:4b` again.
- **Compliance Agent always returns UNKNOWN** → almost certainly means
  `attach_full_text.py` hasn't been run yet, so `full_text` is empty on every
  SOP node. Run it, then re-verify with the Cypher check above.
- **Slow responses** → normal for local inference on a laptop GPU, especially
  the first call after Ollama starts (model load time). If it's too slow for
  a live demo, you can pre-warm the model right before presenting by running
  one throwaway query a minute or two beforehand.
