# WP-P4/P4-2 sparse-team k study — SHADOW ONLY

Every nested selection uses earlier out-of-time predictions whose outcomes are already in the outer training history. The fixed-grid holdout winner below is descriptive; it is not an independently validated final k.

| League | Outer fixtures | Matchweeks | Nested selected LL | Descriptive k |
|---|---:|---:|---:|---|
| Eredivisie | 35 | 6 | 0.955994 | 0 |
| Championship | 58 | 6 | 1.057256 | 4 |

| Cohort | k | Outer LL | LL difference vs k8 | Paired95% CI |
|---|---:|---:|---:|---|
| Eredivisie | 0 | 0.955994 | -0.053529 | [-0.133125, 0.030859] |
| Eredivisie | 4 | 0.990216 | -0.019306 | [-0.037797, -0.000175] |
| Eredivisie | 8 | 1.009523 | 0.000000 | [0.000000, 0.000000] |
| Eredivisie | 12 | 1.022466 | 0.012943 | [0.003176, 0.022263] |
| Eredivisie | 16 | 1.031887 | 0.022364 | [0.006425, 0.037376] |
| Eredivisie | inf | 1.096075 | 0.086552 | [0.041410, 0.122990] |
| Championship | 0 | 1.037019 | -0.003756 | [-0.030702, 0.032066] |
| Championship | 4 | 1.036177 | -0.004598 | [-0.012763, 0.005787] |
| Championship | 8 | 1.040775 | 0.000000 | [0.000000, 0.000000] |
| Championship | 12 | 1.044312 | 0.003537 | [-0.002451, 0.008941] |
| Championship | 16 | 1.047069 | 0.006294 | [-0.003765, 0.015546] |
| Championship | inf | 1.068908 | 0.028133 | [-0.004944, 0.060792] |
| Pooled | 0 | 1.006526 | -0.022488 | [-0.061995, 0.015909] |
| Pooled | 4 | 1.018880 | -0.010133 | [-0.020285, -0.000138] |
| Pooled | 8 | 1.029013 | 0.000000 | [0.000000, 0.000000] |
| Pooled | 12 | 1.036090 | 0.007077 | [0.001286, 0.012734] |
| Pooled | 16 | 1.041355 | 0.012342 | [0.002624, 0.021748] |
| Pooled | inf | 1.079132 | 0.050119 | [0.019001, 0.080008] |

Inner sparse warmup: 75 fixtures. Neither league has a2024 xG prior;2025 promotion labels cannot be established from these data.

Numerical fits: 114; nonconverged: 0. The iteration limit is1000, held constant for every candidate.

Final selections using training data only:
- Eredivisie: k=0 before 2026 round11, inner n=59 across8 matchweeks.
- Championship: k=12 before 2026 round13, inner n=101 across9 matchweeks.

Intervals resample whole matchweeks, retaining fixture pairing. Few blocks, shared teams, season dependence, multiple candidates and multiple leagues make these exploratory intervals; they do not establish equivalence or significance after selection.

k8 is not established: it did not satisfy training-only selection and positive paired superiority over every alternative in both outer league cohorts. Wide intervals cannot establish equivalence.

No production promotion. Preserve section73 and prospective >=2 complete matchweeks plus predeclared sample and A-E gates.
