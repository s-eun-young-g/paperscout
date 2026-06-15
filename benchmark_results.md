# paperscout triple benchmark

## Summary

| Metric | Value |
| --- | --- |
| drugs | 18 |
| errors | 0 |
| target_accuracy | 1.0 |
| targets_evaluated | 17 |
| readout_recall | 0.739 |
| readouts_expected | 23 |
| readouts_found | 17 |
| direction_accuracy | 0.765 |
| triple_accuracy | 0.565 |
| triples_correct | 13 |

## Per-triple

| Drug | Target | Triple | Expected | Predicted | Evidence | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| rosuvastatin | hit | HMGCR -> LDL | down | down | 3 | ok |
| rosuvastatin | hit | HMGCR -> CRP | down | down | 1 | ok |
| atorvastatin | hit | HMGCR -> LDL | down | changes | 1 | dir |
| evolocumab | hit | PCSK9 -> LDL | down | down | 12 | ok |
| alirocumab | hit | PCSK9 -> LDL | down | down | 12 | ok |
| ezetimibe | hit | NPC1L1 -> LDL | down | down | 5 | ok |
| fenofibrate | hit | PPARA -> triglycerides | down | up | 3 | dir |
| fenofibrate | hit | PPARA -> HDL | up | changes | 1 | dir |
| canakinumab | hit | IL1B -> CRP | down | - | 0 | MISS |
| tocilizumab | hit | IL6R -> CRP | down | - | 0 | MISS |
| adalimumab | hit | TNF -> CRP | down | - | 0 | MISS |
| infliximab | hit | TNF -> CRP | down | down | 1 | ok |
| sitagliptin | hit | DPP4 -> HbA1c | down | down | 3 | ok |
| sitagliptin | hit | DPP4 -> glucose | down | down | 2 | ok |
| empagliflozin | hit | SLC5A2 -> HbA1c | down | down | 6 | ok |
| empagliflozin | hit | SLC5A2 -> glucose | down | down | 2 | ok |
| dapagliflozin | hit | SLC5A2 -> HbA1c | down | - | 0 | MISS |
| liraglutide | hit | GLP1R -> HbA1c | down | - | 0 | MISS |
| semaglutide | hit | GLP1R -> HbA1c | down | down | 5 | ok |
| anastrozole | hit | CYP19A1 -> estradiol | down | down | 1 | ok |
| metformin | n/a | - -> glucose | down | down | 1 | ok |
| metformin | n/a | - -> HbA1c | down | up | 1 | dir |
| somatropin | hit | GHR -> IGF-1 | up | - | 0 | MISS |
