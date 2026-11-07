# Phase 2 synthetic dataset examples

Every record represents fictional engineering data; no production manufacturer data is used.

| File | Contents | Clean reference |
|---|---|---|
| `legacy_A.json` | Three fleets, 39 records, schema A, seed 42 | `../ground_truth/legacy_A_canonical.json` |
| `legacy_B.json` | Same engineering configuration under schema B naming conventions | `../ground_truth/legacy_B_canonical.json` |
| `corrupted_revision.json` | Schema A example with one unsupported hardware revision | `../ground_truth/legacy_A_canonical.json` |

Mapping truth is stored in the separate `../ground_truth/legacy_*_mappings.json` files. The corruption label is `../ground_truth/corrupted_revision_fault.json`; never merge it into an input envelope or mapping prompt. Fault labels explicitly identify themselves as synthetic. The agent receives field profiles and source examples, not truth files.

Each fleet contains one platform, one approved change, four ECU hardware records, four software records, two vehicle trims and one multi-level BOM. Even fleets use revision B/software 2.10.0/speed.v1; odd fleets use revision C/software 3.0.0/speed.v2. Two fictional suppliers and four ECU functions provide controlled diversity. Seed changes affect suppliers and masses; topology and compatibility structure follow the deterministic fleet template. This is a reproducible engineering fixture, not a statistical model of automotive production data.

Use `python -m app.cli generate --fleets N --seed 42 --source A --output PATH` for 1–1,000 fleets (13–13,000 records). Generate mapping/canonical truth to a separate directory automatically. `python -m app.cli inject INPUT --fault FAULT --output PATH` exports corrupt inputs separately from their labels. Surviving source IDs are preserved, including custom identifiers; an injected duplicate gets a new source ID while retaining its duplicated engineering identity.
