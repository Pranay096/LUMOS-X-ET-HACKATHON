<div align="center">

# 🔆 Lumos AI
### Industrial Knowledge Intelligence Platform

**ET AI Hackathon 2026 — Problem Statement #8: AI for Industrial Knowledge Intelligence**

*Turning a plant's scattered documents into a living, queryable knowledge graph —
delivered hands-free through AI-powered smart glasses, backed by a mobile
console and a documentation gap tracker.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[Solution Doc](docs/Lumos_AI_Solution_Description.docx) · [Pitch Deck](docs/Lumos_AI_PS8_Pitch.pptx) · [Architecture](#architecture)

</div>

---

## Table of Contents

- [What We're Building](#what-were-building)
- [Why We're Building This](#why-were-building-this)
- [Architecture](#architecture)
- [Why a Knowledge Graph, Not Just RAG](#why-a-knowledge-graph-not-just-rag)
- [Tech Stack](#tech-stack)
- [Why Two AI Backends — Gemini + Ollama](#why-two-ai-backends--gemini--ollama)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [Live Demo Output](#live-demo-output)
- [Why the Glasses](#why-the-glasses)
- [Why the Mobile Console](#why-the-mobile-console)
- [Judging Criteria Alignment](#judging-criteria-alignment)
- [Honest Scope Notes](#honest-scope-notes)
- [License](#license)

---

## What We're Building

Lumos AI ingests a plant's fragmented documents — SOPs, maintenance records,
incident reports, and regulatory clauses — into a single knowledge graph, and
delivers two AI capabilities through three interfaces:

- **Expert Knowledge Copilot** — answers operational and maintenance
  questions by combining knowledge-graph traversal with retrieval-augmented
  generation, always citing sources and always checking whether a procedure
  has been superseded before recommending it.
- **Compliance Agent** — checks an observed equipment or worker state
  against the governing SOPs and regulations for that equipment, returning a
  `PASS` / `FLAG` / `UNKNOWN` verdict with a citation — running entirely on a
  **local** AI model, no cloud dependency.

Delivered through: **Lumos AI Glasses** (hands-free field use), a **mobile web
console** (manual-entry fallback and general interface), and a backend
architecturally ready to serve a plant-manager dashboard.

## Why We're Building This

| Statistic | Source |
|---|---|
| 35% of engineer hours lost searching for information that already exists | McKinsey, 2024 global survey |
| 7–12 disconnected document systems per average large Indian plant | NASSCOM-EY |
| 18–22% of unplanned downtime caused by incomplete equipment history | BIS Research |
| 25% of India's experienced industrial engineers retiring within a decade | PS #8 problem context |

The visible symptom is document fragmentation. The real problem is **knowledge
custody loss**: when an experienced engineer retires, decades of tribal
knowledge — *"this pump always fails this way when it's humid"* — disappears
permanently, because it was never captured anywhere structured. This project
directly answers four of the five "what you may build" bullets in the official
PS #8 brief: universal document ingestion, an expert knowledge copilot with
citations built for mobile, a maintenance/RCA capability, and a compliance
intelligence layer.

## Architecture

![System Architecture](docs/architecture-diagram.png)

Five layers, each with one job: raw documents come in, Gemini extracts
structured entities and relationships against a fixed schema, the results
live in Neo4j (graph) and Qdrant (vectors), two reasoning agents query those
stores, and the result reaches a human through glasses, mobile, or (future)
a dashboard.

## Why a Knowledge Graph, Not Just RAG

Plain RAG answers *"what does this document say."* A knowledge graph answers
*"what is true across all documents about this equipment"* — traversing
relationships no vector search has any concept of.

> **Worked example — "Why does PMP-204 keep failing?"**
> `PMP-204` (Equipment) ← two incident reports linked to each other by
> `SIMILAR_TO`, confirming a recurring pattern → both incidents linked via
> `REVISED_DUE_TO` to a `SUPERSEDES` relationship between two SOP revisions,
> so the system knows the 180-day-interval procedure is outdated **and why**
> → the current procedure `CITES` a regulatory clause → an engineer's
> undocumented tacit-knowledge note about an early-warning sign is linked in
> too. **Seven hops, five node types, one answer** — impossible for a flat
> vector search, which treats every chunk independently.

**Knowledge graph, in numbers:** 12 source documents → **88 nodes**, **144
relationships**, 11 node types, 24 relationship types.

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Backend framework | Python 3.11 + FastAPI | One API, reasoning endpoints, auto docs at `/docs` |
| Knowledge graph | Neo4j AuraDB (free tier) | Multi-hop Cypher traversal |
| Vector store | Qdrant Cloud (free tier) | 768-dim normalized embeddings, metadata-filtered |
| Copilot generation | Gemini 2.5 Flash-Lite | Free tier — powers `/ask` |
| Embeddings | Gemini `embedding-001` | 768-dim, manually normalized |
| Compliance generation | **Ollama + `qwen3-vl:4b`, fully local** | Zero API calls, zero cloud dependency |
| Document extraction | Gemini 2.5 Flash-Lite | Structured JSON against a fixed schema |
| Glasses hardware | Raspberry Pi Zero W + CSI camera + transparent SSD1309 OLED | Edge capture/render only — no on-device inference |
| Glasses software | `picamera2`, OpenCV (QR decode), `luma.oled`, `requests` | |
| Mobile console | Single-file HTML/CSS/vanilla JS | No build step; includes live browser speech-to-text |
| Gap tracker | JSON-file backed, served via `/gaps` | Logs every low-confidence Copilot answer |

## Why Two AI Backends — Gemini + Ollama

**Gemini is not fully replaced.** Two backends deliberately do two different jobs:

- **Gemini** (`gemini-2.5-flash-lite` + `gemini-embedding-001`) still powers
  document extraction and the Expert Copilot's `/ask` endpoint — built,
  tested, and working before a local model was introduced.
- **Ollama** (`qwen3-vl:4b`, fully local) powers *only* the Compliance Agent
  — chosen because a safety-critical field check should keep working even if
  shop-floor internet drops, and because it matches the real product's
  planned local-inference architecture (an RTX 4050 laptop as an offline
  inference server).

> If asked *"is this fully offline"* — the honest answer: the safety-critical
> Compliance Agent is fully local today; the Expert Copilot currently uses
> Gemini's free tier and is architected to move to the same local model with
> no interface change — a natural next milestone, not a redesign.

## Repository Structure

```
lumos-ai/
├── plant-docs/          12 source documents (equipment list, SOPs,
│                         regulatory excerpt, incident reports, tacit
│                         knowledge capture) — the demo dataset
│
├── ingestion/            Document → Knowledge Graph + Vector Store
│   ├── schema.py          Node/relationship type definitions
│   ├── extract.py         Gemini-based structured entity extraction
│   ├── load_graph.py      Writes extracted entities to Neo4j
│   ├── load_vectors.py    Chunks + embeds documents into Qdrant
│   └── check_models.py    Utility: checks which Gemini models have quota
│
├── rag/                  Expert Copilot (Gemini-based RAG)
│   ├── retrieve.py         Hybrid graph + vector retrieval
│   ├── synthesize.py       Cited, confidence-scored answer generation
│   └── test_questions.py   10-question test harness
│
├── compliance/           Compliance Agent (Ollama, fully local)
│   ├── attach_full_text.py   One-time graph enrichment (SOP full text)
│   ├── ollama_client.py      Local model wrapper (retry, thinking-mode handling)
│   ├── compliance_agent.py   PASS / FLAG / UNKNOWN reasoning
│   ├── gap_tracker.py        Documentation Gap logging
│   ├── api.py                 FastAPI app — all HTTP endpoints
│   └── test_compliance.py    4-scenario test harness
│
├── glasses/              Raspberry Pi Zero W client
│   ├── glasses_client.py        Camera → QR decode → API → OLED render
│   ├── generate_demo_qrcodes.py Generates the 5 physical demo markers
│   └── demo_qrcodes/            Pre-generated, round-trip tested QR codes
│
├── webui/                Manual-input fallback / mobile console
│   └── mobile_ui.html      Ask (+ live voice input) · Compliance · Gaps
│
└── docs/                 Reference material
    ├── Lumos_AI_Solution_Description.docx   Full written solution description
    ├── Lumos_AI_PS8_Pitch.pptx               Pitch deck
    ├── architecture-diagram.png              Diagram used above
    ├── 13_knowledge_graph_schema.md          Full graph schema reference
    └── 14_tech_stack_decision.md             Original stack-selection rationale
```

Each component folder (`ingestion/`, `rag/`, `compliance/`, `glasses/`) has
its own `README.md` with detailed setup steps and its own `requirements.txt`
— you can `cd` into any one of them and get running without needing context
from the others, except where noted (the API layer imports `rag/` directly;
see `compliance/api.py`).

## Getting Started

**Prerequisites:** Python 3.11+, a free [Neo4j AuraDB](https://console.neo4j.io)
instance, a free [Qdrant Cloud](https://cloud.qdrant.io) cluster, a free
[Gemini API key](https://aistudio.google.com/app/apikey), and
[Ollama](https://ollama.com/download) with `qwen3-vl:4b` pulled locally.

```bash
git clone <your-repo-url>
cd lumos-ai

# 1. Ingest the 12 documents into Neo4j + Qdrant
cd ingestion && pip install -r requirements.txt
cp .env.example .env   # fill in your Gemini / Neo4j / Qdrant credentials
python extract.py && python load_graph.py && python load_vectors.py

# 2. Enrich the graph with full SOP text (needed by the Compliance Agent)
cd ../compliance && pip install -r requirements.txt
cp .env.example .env   # Neo4j creds + Gemini key (for /ask via ../rag)
python attach_full_text.py

# 3. Pull the local compliance model
ollama pull qwen3-vl:4b

# 4. Run the backend API
uvicorn api:app --reload --host 0.0.0.0 --port 8000

# 5. Open the mobile console (update API_BASE_URL inside the file first)
open ../webui/mobile_ui.html
```

Full step-by-step instructions, including the Pi Zero W glasses setup, are in
each component's own `README.md`.

## Live Demo Output

Real output from this running pipeline (not mocked):

> **Q: How should I maintain PMP-204?**
> A: Perform preventive maintenance every 90 days (or within 48 hours if Zone
> B humidity exceeds 75% RH)... The prior procedure (Rev.1, 180-day interval)
> has been superseded because two humidity-related seal failures (APM-INC-031,
> APM-INC-044) occurred within 3 weeks of each other...
> ✅ `used_superseded_check: True` · confidence `1.0`
> Cited: `03_sop_pump_maintenance_v2_current.md`, `02_sop_pump_maintenance_v1_superseded.md`

> **Q: Why does PMP-204 keep failing?**
> A: PMP-204 experienced two identical mechanical seal failures within 3
> weeks... Both are linked by a SIMILAR_TO relationship in the knowledge
> graph and trace to the same confirmed root cause: elevated ambient humidity
> accelerates seal pitting...
> ✅ `flagged_recurring_pattern: True` · confidence `1.0`

## Why the Glasses

The glasses are the **hands-free delivery interface** — not where any
reasoning happens. A Raspberry Pi Zero W has no GPU/NPU; it captures a QR
marker, sends it to the backend, and renders the response on the transparent
OLED. The brain is the backend; the glasses are eyes and a screen.

The honest case for glasses over a phone is narrow and specific: moments
where **both hands are occupied** — holding a part, mid-repair — and glancing
at a phone isn't practical. That's a real, recurring field scenario. For a
walk-up-and-look question, a phone works just as well, which is exactly why
the mobile console exists and proves the same intelligence independent of
the hardware.

## Why the Mobile Console

Not a conversational chatbot — a structured three-tab console (Ask,
Compliance Check, Documentation Gaps) calling the same two backend endpoints
the glasses call.

1. **It's the manual-input fallback** the architecture is built around — if
   the glasses' camera fails, the same equipment ID and observation get typed
   by hand into the same backend. No separate code path.
2. **PS #8 asks for it explicitly** — the official brief specifies the
   copilot should be *"built to work on mobile for field technicians, not
   just desktops for engineers."*
3. **It proves the platform, not just the hardware** — the same cited answer,
   available on a plain browser, shows the knowledge intelligence is the
   product and the glasses are one interface choice among several.

## Judging Criteria Alignment

| Criteria | Weight | How this project addresses it |
|---|---|---|
| Innovation | 25% | Hybrid knowledge-graph + RAG with full provenance; working AR glasses hardware; a local-AI safety agent alongside a cloud-AI copilot, each deliberately chosen for the job it does. |
| Business Impact | 25% | Directly targets the 35%-of-hours and 18–22%-of-downtime figures from PS #8's own problem context, with a measurable reduction in time-to-answer. |
| Technical Excellence | 20% | Live prototype: 88 real graph nodes, 144 relationships, a tested hybrid retrieval pipeline, a local LLM compliance agent, real hardware. |
| Scalability | 15% | Cloud-native graph/vector stores; graph grows with every ingested document; one API serves glasses, mobile, and (architecturally) a manager dashboard. |
| User Experience | 15% | Hands-free glasses delivery; a mobile fallback satisfying PS #8's own mobile requirement; a Documentation Gap tracker turning uncertainty into an actionable list. |

## Honest Scope Notes

Built in a compressed timeline — these are deliberate, disclosed MVP
decisions, not hidden gaps:

- **QR-encoded demo scenarios, not live computer vision.** The glasses'
  camera reads a QR marker that encodes the "observed state" a real CV model
  would eventually detect automatically. Every part of the actual reasoning
  downstream — retrieval, graph traversal, the Ollama compliance check — is
  completely real.
- **Gemini is still in the loop** for document extraction and the general
  Expert Copilot, as detailed above — not a fully offline system yet, by
  design, with a clear migration path.
- **Synthetic-but-realistic documents.** The 12 plant documents are written
  to mirror real SOP structure and cross-reference each other consistently,
  rather than sourced from a real plant — a deliberate choice to avoid
  proprietary-document sourcing risk within the build window.

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

**Built for ET AI Hackathon 2026 · Problem Statement #8**

</div>
