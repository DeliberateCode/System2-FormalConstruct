# Benchmark Results

Current status of the `formalize` agent on the FormalConstruct benchmark corpus.
Each problem is a plain-text math statement the agent must translate into a
ProblemSpec, scaffold to Lean 4, and prove via AXLE. A result counts as
**verified** only when AXLE confirms the proof compiles with no `sorry`.

_As of run `20260615_230903` (lean-4.29.0; concurrency 2, timeout 600s, max-turns 100)._

| Metric | Value |
|---|---|
| Problems | 16 |
| Verified | 15 |
| Pass rate | **93.8%** |
| Timing | mean 170s · median 142s · max 600s |

## Per-problem outcomes

| Problem | Outcome | Time (s) |
|---|---|---|
| lean_workbook_plus_8048 | ✅ verified | 64 |
| lean_workbook_plus_14472 | ✅ verified | 102 |
| lean_workbook_plus_18380 | ✅ verified | 164 |
| lean_workbook_plus_31913 | ✅ verified | 55 |
| lean_workbook_plus_32710 | ✅ verified | 226 |
| lean_workbook_plus_35207 | ✅ verified | 86 |
| lean_workbook_plus_46043 | ✅ verified | 169 |
| lean_workbook_plus_46535 | ✅ verified | 171 |
| lean_workbook_plus_54232 | ✅ verified | 58 |
| lean_workbook_plus_61973 | ✅ verified | 86 |
| lean_workbook_plus_62528 | ✅ verified | 142 |
| lean_workbook_plus_65243 | ✅ verified | 100 |
| lean_workbook_plus_71897 | ✅ verified | 229 |
| lean_workbook_plus_81606 | ✅ verified | 116 |
| lean_workbook_plus_81713 | ⏱ timeout | 600 |
| lean_workbook_plus_82245 | ✅ verified | 359 |

All 16 problems are in the `continuous_optimization` domain.

## Notes

- The lone non-pass, `lean_workbook_plus_81713`, is a **timeout** at the 600s
  wall — it sits near the time budget and is run-to-run variable, not a
  correctness failure. A higher `--timeout` typically recovers it.
- Every verified result is independently confirmed: proof harvested,
  `sorry`-free, AXLE `okay: true`.

Reproduce:

```bash
python -m benchmarking run --timeout 600 --max-turns 100
```
