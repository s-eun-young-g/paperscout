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
| direction_accuracy | 1.0 |
| wrong_direction | 0 |
| triple_accuracy | 0.826 |
| triples_correct | 19 |

## Per-triple

| Drug | Target | Triple | Expected | Predicted | Evidence | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| rosuvastatin | hit | HMGCR -> LDL | down | down | 21 | ok |
| rosuvastatin | hit | HMGCR -> CRP | down | down | 2 | ok |
| atorvastatin | hit | HMGCR -> LDL | down | down | 11 | ok |
| evolocumab | hit | PCSK9 -> LDL | down | down | 29 | ok |
| alirocumab | hit | PCSK9 -> LDL | down | down | 20 | ok |
| ezetimibe | hit | NPC1L1 -> LDL | down | down | 20 | ok |
| fenofibrate | hit | PPARA -> triglycerides | down | down | 12 | ok |
| fenofibrate | hit | PPARA -> HDL | up | up | 4 | ok |
| canakinumab | hit | IL1B -> CRP | down | down | 2 | ok |
| tocilizumab | hit | IL6R -> CRP | down | unclear | 1 | abstain |
| adalimumab | hit | TNF -> CRP | down | down | 2 | ok |
| infliximab | hit | TNF -> CRP | down | unclear | 1 | abstain |
| sitagliptin | hit | DPP4 -> HbA1c | down | down | 6 | ok |
| sitagliptin | hit | DPP4 -> glucose | down | down | 5 | ok |
| empagliflozin | hit | SLC5A2 -> HbA1c | down | down | 12 | ok |
| empagliflozin | hit | SLC5A2 -> glucose | down | down | 4 | ok |
| dapagliflozin | hit | SLC5A2 -> HbA1c | down | down | 6 | ok |
| liraglutide | hit | GLP1R -> HbA1c | down | down | 2 | ok |
| semaglutide | hit | GLP1R -> HbA1c | down | down | 9 | ok |
| anastrozole | hit | CYP19A1 -> estradiol | down | unclear | 2 | abstain |
| metformin | n/a | - -> glucose | down | down | 5 | ok |
| metformin | n/a | - -> HbA1c | down | down | 10 | ok |
| somatropin | hit | GHR -> IGF-1 | up | unclear | 7 | abstain |
