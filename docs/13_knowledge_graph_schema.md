# Knowledge Graph Schema — Ashoka Precision Manufacturing
## Industrial Knowledge Intelligence Platform — Day 1 Deliverable

This schema is built specifically to match the 12 documents already created (doc set: 01–12).
Every node type and relationship below has at least one real example from those documents,
so ingestion tomorrow has concrete data to map against.

---

## 1. Node Types

| Node Label | Purpose | Key Properties | Example from our docs |
|---|---|---|---|
| `Plant` | Top of hierarchy | `name` | Ashoka Precision Manufacturing |
| `Unit` | Sub-division of plant | `name`, `unit_id` | Unit 2 (Fabrication & Assembly) |
| `Zone` | Physical area within a unit | `name`, `zone_id`, `ppe_classification` | Zone B — Machining Bay (Restricted PPE Zone) |
| `Equipment` | Physical asset | `equipment_id`, `name`, `type`, `manufacturer`, `install_date`, `criticality` | PMP-204, Hydraulic Coolant Pump, Centrifugal Pump, Kirloskar Brothers, 2018-06-12, High |
| `SOP` | A versioned procedure document | `doc_no`, `revision`, `title`, `status` (current/superseded), `effective_date` | APM-SOP-009 Rev. 2, "Preventive Maintenance — PMP-204," current, 2025-08-15 |
| `RegulatoryClause` | A specific section from the regulatory excerpt | `doc_no`, `section_no`, `title` | APM-REG-001 Section 41 |
| `IncidentReport` | A logged incident / work order / near-miss | `report_no`, `date`, `severity`, `status` | APM-INC-044, 2025-08-09, Moderate, Closed |
| `WorkOrder` | A maintenance work order tied to an incident or routine task | `wo_no`, `date` | APM-WO-2025-0791 |
| `Engineer` | A named person who authored, performed, or is referenced in a document | `name`, `role`, `tenure_years` (if known) | R. Iyer, Senior Maintenance Engineer, 22 years |
| `TacitKnowledge` | An informal/uncontrolled knowledge snippet | `source`, `topic`, `captured_date` | R. Iyer's note on PMP-204 seal-whine early warning |
| `Vendor` | Equipment manufacturer/supplier | `name` | Kirloskar Brothers, Atlas Copco, Kuka Robotics, Cummins India |
| `FailureMode` | An abstracted recurring failure pattern (derived, not from a single doc — this is what RCA agent builds up over time) | `name`, `description` | "Humidity-driven mechanical seal pitting" |

---

## 2. Relationship Types

```
(Zone)-[PART_OF]->(Unit)
(Unit)-[PART_OF]->(Plant)
(Equipment)-[LOCATED_IN]->(Zone)
(Equipment)-[MANUFACTURED_BY]->(Vendor)
(Equipment)-[SUPPLIES_TO]->(Equipment)                 -- e.g. PMP-204 SUPPLIES_TO PRS-088 (coolant)
(Equipment)-[SUPPLIES_TO]->(Equipment)                 -- e.g. CMP-301 SUPPLIES_TO WLD-077 (compressed air)

(SOP)-[GOVERNS]->(Equipment)                            -- APM-SOP-009 GOVERNS PMP-204
(SOP)-[APPLIES_TO]->(Zone)                               -- APM-SOP-014 APPLIES_TO Zone B
(SOP)-[SUPERSEDES]->(SOP)                                -- v2 SUPERSEDES v1  ★ stale-doc catch
(SOP)-[REFERENCES]->(SOP)                                -- SOP-009 REFERENCES SOP-014 (PPE)
(SOP)-[AUTHORED_BY]->(Engineer)
(SOP)-[CITES]->(RegulatoryClause)                        -- SOP-014 CITES REG-001 Section 41
(SOP)-[REVISED_DUE_TO]->(IncidentReport)                 -- SOP-009 Rev.2 REVISED_DUE_TO INC-031, INC-044  ★ key inference edge

(RegulatoryClause)-[MANDATES]->(SOP)                     -- inverse of CITES, kept for query convenience

(IncidentReport)-[OCCURRED_ON]->(Equipment)
(IncidentReport)-[REPORTED_BY]->(Engineer)
(IncidentReport)-[RESULTED_IN]->(WorkOrder)
(IncidentReport)-[SIMILAR_TO]->(IncidentReport)          -- INC-031 SIMILAR_TO INC-044  ★ RCA pattern-match edge
(IncidentReport)-[EXHIBITS]->(FailureMode)
(IncidentReport)-[VIOLATES]->(SOP)                       -- INC-061 VIOLATES SOP-017 (LOTO near-miss)
(IncidentReport)-[REPORTABLE_UNDER]->(RegulatoryClause)  -- INC-061 REPORTABLE_UNDER REG-001 Section 38/59

(WorkOrder)-[PERFORMED_ON]->(Equipment)
(WorkOrder)-[PERFORMED_BY]->(Engineer)
(WorkOrder)-[FOLLOWED_PROCEDURE]->(SOP)                  -- ties a specific repair to the SOP revision active at that time

(Engineer)-[EXPERT_IN]->(Equipment)                      -- derived from TacitKnowledge + repeated WorkOrder/IncidentReport authorship
(Engineer)-[AUTHORED]->(TacitKnowledge)

(TacitKnowledge)-[RELATES_TO]->(Equipment)
(TacitKnowledge)-[ANTICIPATES]->(FailureMode)            -- R. Iyer's "seal whine" note ANTICIPATES the pitting failure mode

(FailureMode)-[OBSERVED_ON]->(Equipment)
```

---

## 3. Worked Example — How a Real Query Traverses This Graph

**Query:** "Why does PMP-204 keep failing, and what's the current fix?"

```
PMP-204 (Equipment)
  ← OCCURRED_ON ← APM-INC-031 (IncidentReport, 2025-07-18)
  ← OCCURRED_ON ← APM-INC-044 (IncidentReport, 2025-08-09)
       [APM-INC-031]-[SIMILAR_TO]->[APM-INC-044]          → confirms recurring pattern
       both -[EXHIBITS]-> "Humidity-driven seal pitting" (FailureMode)
  ← GOVERNS ← APM-SOP-009 Rev.2 (SOP, current)
       [Rev.2]-[SUPERSEDES]->[Rev.1]                       → system knows NOT to use Rev.1
       [Rev.2]-[REVISED_DUE_TO]->[INC-031, INC-044]        → explains WHY it changed
  ← RELATES_TO ← TacitKnowledge (R. Iyer's seal-whine note)
       -[ANTICIPATES]-> "Humidity-driven seal pitting" (FailureMode)
```

**This is the answer a flat RAG/vector search cannot construct** — it requires walking five relationship types across four node types to arrive at: *current procedure, why it changed, the historical pattern that triggered the change, and an undocumented early-warning sign no SOP captures yet.* This worked example is your single best slide for explaining "why knowledge graph, not just RAG" to judges.

---

## 4. Provenance Rule (apply to every node)

Every `IncidentReport`, `SOP`, `RegulatoryClause`, and `TacitKnowledge` node must carry:
- `source_doc` (filename/doc number it was extracted from)
- `extraction_confidence` (score from your ingestion pipeline tomorrow)

This is what powers your citation requirement (PS #8 explicitly asks for "source citations, confidence scores, and direct links to originating documents") and your Documentation Gap dashboard later.

---

## 5. What NOT to build (scope discipline reminder)

- No need for a `Sensor` node type yet — none of your 12 docs reference live sensor data; don't build graph capacity for data you don't have.
- `FailureMode` nodes are the only node type not directly extractable from a single document — these get created by the RCA agent's reasoning (Day 5), not the ingestion pipeline (Day 2). Don't try to auto-extract these on Day 2; that's tomorrow's agent logic, not today's ingestion logic.
