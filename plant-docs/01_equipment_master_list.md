# ASHOKA PRECISION MANUFACTURING PVT. LTD.
## Equipment Master List — Unit 2 (Fabrication & Assembly)

**Document No:** APM-EML-002
**Revision:** 3
**Effective Date:** 2026-03-01
**Owner:** Plant Engineering Department

---

| Equipment ID | Equipment Name | Type | Unit/Zone | Install Date | Manufacturer | Criticality |
|---|---|---|---|---|---|---|
| PMP-204 | Hydraulic Coolant Pump | Centrifugal Pump | Zone B — Machining Bay | 2018-06-12 | Kirloskar Brothers | High |
| CNV-112 | Main Feed Conveyor | Belt Conveyor | Zone A — Material Handling | 2017-11-03 | Flexlink Systems | Medium |
| CMP-301 | Air Compressor Unit 1 | Reciprocating Compressor | Zone C — Utility Bay | 2019-02-20 | Atlas Copco | High |
| PRS-088 | Hydraulic Press Station | Hydraulic Press | Zone B — Machining Bay | 2016-09-08 | Schuler India | High |
| GEN-450 | Standby DG Set | Diesel Generator | Zone D — Power House | 2020-01-15 | Cummins India | Critical |
| WLD-077 | Robotic Welding Cell | Robotic Welder | Zone B — Machining Bay | 2021-07-22 | Kuka Robotics | Medium |

### Equipment Hierarchy

```
Ashoka Precision Manufacturing
└── Unit 2 (Fabrication & Assembly)
    ├── Zone A — Material Handling
    │   └── CNV-112 (Main Feed Conveyor)
    ├── Zone B — Machining Bay
    │   ├── PMP-204 (Hydraulic Coolant Pump)
    │   ├── PRS-088 (Hydraulic Press Station)
    │   └── WLD-077 (Robotic Welding Cell)
    ├── Zone C — Utility Bay
    │   └── CMP-301 (Air Compressor Unit 1)
    └── Zone D — Power House
        └── GEN-450 (Standby DG Set)
```

### Notes
- PMP-204 supplies coolant directly to PRS-088 and the machining lines in Zone B; a PMP-204 failure has downstream impact on Zone B throughput.
- CMP-301 supplies compressed air to WLD-077 and pneumatic tooling across Zone B and Zone C.
- Zone B is classified as a **Restricted PPE Zone** (see APM-SOP-014).
- GEN-450 is classified **Critical** — loss of standby power affects safety systems plant-wide.

---
*This document is controlled. Refer to the Document Control Register for the current revision before use.*
