# PCAG IJAMT Nominal First Batch Plan

Target size: 30 cases  
Status: draft planning artifact

## 1. Purpose

This file defines the first nominal mini-batch that should be created before unsafe and fault expansion.

The goal of the first batch is not full coverage.  
It is to create a balanced, reviewable seed set that can be dry-run through future baseline runners.

## 2. Distribution target

| asset family | target count |
| --- | ---: |
| `robot_manipulation` | 12 |
| `agv_logistics` | 9 |
| `process_interlock` | 9 |

## 3. Robot nominal batch

Source priority:

- `isaaclab_eval_industrial`
- `mimicgen_assembly`

### Planned cases

1. robot pick from fixture station
2. robot place to output tray
3. robot move to fixture approach
4. robot insert part into fixture
5. robot retreat to safe pose
6. robot joint-space move to nominal assembly pose
7. robot pick at alternate station
8. robot place at alternate station
9. robot insert shallow nominal fit
10. robot move to handoff pose
11. robot pick after station change
12. robot return to standby pose

## 4. AGV nominal batch

Source priority:

- `agv_process_curated`

### Planned cases

13. AGV move to station A
14. AGV move to station B
15. AGV dock at robot handoff station
16. AGV wait in holding zone
17. AGV handoff to robot ready position
18. AGV enter zone with nominal heading
19. AGV move to inspection station
20. AGV dock at loading station
21. AGV wait before handoff release

## 5. Process-interlock nominal batch

Source priority:

- `agv_process_curated`

### Planned cases

22. set heater output to nominal low level
23. set heater output to nominal medium level
24. open cooling valve nominally
25. close cooling valve after stable state
26. hold state for short duration
27. set process mode to production-ready
28. set process mode to standby
29. heater increase with cooling already available
30. hold stable thermal state

## 6. Case construction rules

Each of the 30 cases must:

- use only frozen action vocabulary
- use only frozen label taxonomy
- represent a case expected to finish in `COMMITTED`
- include provenance notes
- include enough operation context for later mutation

## 7. Review checklist before unsafe expansion

Before deriving unsafe cases from this batch, verify:

- all 30 cases are syntactically valid
- all 30 cases are semantically plausible
- at least one nominal case exists for every major action family
- the batch can support obvious unsafe mutations without inventing new vocabulary

## 8. Immediate follow-on use

This first batch is intended to support:

- mini benchmark dry-run
- unsafe mutation derivation
- fault case layering
- baseline runner smoke tests
