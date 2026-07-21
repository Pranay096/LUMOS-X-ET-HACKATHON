# Tech Stack Decision — Day 1 Final Item

Decided with one rule: every choice optimizes for "can an AI coding tool (Claude/ChatGPT/Gemini/Antigravity) set this up correctly in under an hour, with minimal moving parts to debug at 11pm on Day 6." Not optimizing for "most impressive sounding" — optimizing for "actually works in 10 days."

---

## The Stack

| Layer | Choice | Why this, not the alternative |
|---|---|---|
| **Backend language** | Python (FastAPI) | Every AI tool generates Python fluently; FastAPI gives you a working API with auto-docs (`/docs`) for free, which doubles as your Day 6 testing interface |
| **Graph database** | **Neo4j (free AuraDB cloud tier, or Docker locally)** | Purpose-built for the multi-hop traversal your whole pitch depends on (the worked example in the schema doc). Cypher query language is well-represented in AI training data, so your AI tool will write correct queries reliably. Alternative considered: storing graph edges in Postgres — rejected because multi-hop traversal queries become painful hand-written joins, and that's exactly the part of your demo that needs to look effortless. |
| **Vector database** | **Qdrant (free cloud tier, or Docker locally)** | Simple REST/Python API, generous free tier, no auth complexity to fight with. Alternative considered: pgvector — would let you avoid running two databases, but Qdrant's metadata filtering (by equipment ID, doc status) is more straightforward for the hybrid retrieval your RAG needs. |
| **LLM API** | **Google Gemini API (gemini-2.0-flash or gemini-1.5-flash, free tier)** | Free tier with a real usable rate limit, strong structured-output/JSON-mode support, good instruction-following for the "always cite source_doc" rule baked into your schema. Use it for: entity extraction (Day 2), RAG synthesis (Day 3), Compliance/RCA agent reasoning (Days 4–5). **No paid APIs (Claude, OpenAI) — Gemini free tier only, for everything.** |
| **Embeddings** | **Gemini `text-embedding-004` (free tier)** | Stay inside the same free Google AI Studio account/key as the LLM calls — one API key, one rate limit to track, one less thing to misconfigure under time pressure. |
| **Orchestration / agent routing** | Plain Python function routing (if/LLM-classifier), **not** a heavy framework like LangGraph | At your scale (4 agents, 1 router) a framework adds setup risk for no visible benefit. A simple intent-classify-then-call-function router is faster to build correctly and just as demoable. Revisit only if Day 6 integration is going smoothly with time to spare. |
| **Frontend (dashboard + mobile view)** | Single React web app (responsive), deployed simply (Vercel/Netlify free tier) | One codebase serves both "dashboard" and "mobile" requirements from the PS — no need for a separate native app. |
| **Glasses backend bridge** | FastAPI endpoint the Pi Zero W calls directly over Wi-Fi (HTTP POST with image/marker ID → JSON response) | No special protocol needed; keep the Pi Zero W's job as dumb as possible — capture, POST, render response. |

---

## Why not the "more impressive" alternatives

- **Why not LangGraph/CrewAI/AutoGen for agents:** these read well on an architecture diagram but add a real debugging tax when something breaks on Day 9, and judges are evaluating agent *outputs* (citation quality, correct routing), not which orchestration library you used internally. Mention in your pitch deck that the architecture is "designed to support LangGraph-style orchestration at scale" — true, and lets you reference it without taking on the build risk.
- **Why not a fully custom ontology-extraction model:** your 12 documents are clean, structured Markdown — Claude/GPT-4 class models extract entities from this reliably via a well-written prompt. Training or fine-tuning anything here would burn days for no demo-visible benefit.
- **Why not Neo4j Desktop / fully local-only setup:** cloud free tiers (AuraDB, Qdrant Cloud) remove "is my laptop's Docker working during the demo" as a failure point — important since you said multiple people/tools will be touching this build across 10 days.

---

## What to tell your AI coding tool, concretely, tomorrow (Day 2 kickoff)

When you sit down with Claude/ChatGPT/Gemini for Day 2, the prompt should specify this stack explicitly rather than asking the tool to choose — e.g.:

> "Build a Python FastAPI ingestion pipeline that reads Markdown documents from a folder, uses the Gemini API (free tier) to extract entities and relationships matching this schema [paste schema doc], writes nodes/relationships to Neo4j (AuraDB), and writes chunk embeddings to Qdrant using Gemini's text-embedding-004 with metadata (equipment_id, doc_type, status, source_doc)."

Locking the stack now means every AI tool you use for the rest of the 10 days builds against the same target instead of each one improvising a different architecture.
