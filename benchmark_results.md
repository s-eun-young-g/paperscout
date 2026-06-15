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
| committed | 19 |
| abstained | 4 |
| direction_accuracy | 0.947 |
| wrong_direction | 1 |
| triple_accuracy | 0.783 |
| triples_correct | 18 |

## Per-triple

| Drug | Target | Triple | Expected | Predicted | Evidence | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| rosuvastatin | hit | HMGCR -> LDL | down | down | 22 | ok |
| rosuvastatin | hit | HMGCR -> CRP | down | unclear | 4 | abstain |
| atorvastatin | hit | HMGCR -> LDL | down | down | 14 | ok |
| evolocumab | hit | PCSK9 -> LDL | down | down | 32 | ok |
| alirocumab | hit | PCSK9 -> LDL | down | down | 28 | ok |
| ezetimibe | hit | NPC1L1 -> LDL | down | down | 23 | ok |
| fenofibrate | hit | PPARA -> triglycerides | down | down | 13 | ok |
| fenofibrate | hit | PPARA -> HDL | up | down | 5 | dir |
| canakinumab | hit | IL1B -> CRP | down | down | 2 | ok |
| tocilizumab | hit | IL6R -> CRP | down | down | 1 | ok |
| adalimumab | hit | TNF -> CRP | down | down | 2 | ok |
| infliximab | hit | TNF -> CRP | down | unclear | 2 | abstain |
| sitagliptin | hit | DPP4 -> HbA1c | down | down | 6 | ok |
| sitagliptin | hit | DPP4 -> glucose | down | down | 5 | ok |
| empagliflozin | hit | SLC5A2 -> HbA1c | down | down | 13 | ok |
| empagliflozin | hit | SLC5A2 -> glucose | down | down | 5 | ok |
| dapagliflozin | hit | SLC5A2 -> HbA1c | down | down | 7 | ok |
| liraglutide | hit | GLP1R -> HbA1c | down | down | 3 | ok |
| semaglutide | hit | GLP1R -> HbA1c | down | down | 12 | ok |
| anastrozole | hit | CYP19A1 -> estradiol | down | unclear | 3 | abstain |
| metformin | n/a | - -> glucose | down | down | 5 | ok |
| metformin | n/a | - -> HbA1c | down | down | 13 | ok |
| somatropin | hit | GHR -> IGF-1 | up | unclear | 11 | abstain |
