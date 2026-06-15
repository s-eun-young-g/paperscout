# paperscout triple benchmark

## Summary

| Metric | Value |
| --- | --- |
| drugs | 18 |
| errors | 0 |
| target_accuracy | 1.0 |
| targets_evaluated | 17 |
| readout_recall | 1.0 |
| readouts_expected | 23 |
| readouts_found | 23 |
| direction_accuracy | 0.957 |
| triple_accuracy | 0.957 |
| triples_correct | 22 |

## Per-triple

| Drug | Target | Triple | Expected | Predicted | Evidence | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| rosuvastatin | hit | HMGCR -> LDL | down | down | 20 | ok |
| rosuvastatin | hit | HMGCR -> CRP | down | down | 2 | ok |
| atorvastatin | hit | HMGCR -> LDL | down | down | 10 | ok |
| evolocumab | hit | PCSK9 -> LDL | down | down | 30 | ok |
| alirocumab | hit | PCSK9 -> LDL | down | down | 27 | ok |
| ezetimibe | hit | NPC1L1 -> LDL | down | down | 20 | ok |
| fenofibrate | hit | PPARA -> triglycerides | down | down | 9 | ok |
| fenofibrate | hit | PPARA -> HDL | up | down | 3 | dir |
| canakinumab | hit | IL1B -> CRP | down | down | 2 | ok |
| tocilizumab | hit | IL6R -> CRP | down | down | 1 | ok |
| adalimumab | hit | TNF -> CRP | down | down | 2 | ok |
| infliximab | hit | TNF -> CRP | down | down | 1 | ok |
| sitagliptin | hit | DPP4 -> HbA1c | down | down | 6 | ok |
| sitagliptin | hit | DPP4 -> glucose | down | down | 3 | ok |
| empagliflozin | hit | SLC5A2 -> HbA1c | down | down | 12 | ok |
| empagliflozin | hit | SLC5A2 -> glucose | down | down | 5 | ok |
| dapagliflozin | hit | SLC5A2 -> HbA1c | down | down | 5 | ok |
| liraglutide | hit | GLP1R -> HbA1c | down | down | 3 | ok |
| semaglutide | hit | GLP1R -> HbA1c | down | down | 12 | ok |
| anastrozole | hit | CYP19A1 -> estradiol | down | down | 2 | ok |
| metformin | n/a | - -> glucose | down | down | 5 | ok |
| metformin | n/a | - -> HbA1c | down | down | 12 | ok |
| somatropin | hit | GHR -> IGF-1 | up | up | 5 | ok |
