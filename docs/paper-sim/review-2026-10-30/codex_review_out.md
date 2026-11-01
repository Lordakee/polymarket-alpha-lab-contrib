# Optimization Review Findings

**This review is incomplete because the runtime could not read the supplied files.** Even a direct `cat` of the ledger failed before execution with `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`. I have not inspected the ledger, model source, scan tools, or xG exports. No project files were modified, no database was accessed, and `~/pal-artifacts/` was not accessed.

The three findings below are supported by the numbers and system description in your prompt. They are **preliminary findings, not a completed source-code and ledger audit**.

1. **The aggregate O/U record does not establish that the tightened gates improved selection.**

   If the stated post-Oct-24 **4W–2L** cohort is a subset of the overall **11W–6L**, the remaining cohort is **7W–4L**:

   | O/U cohort | Record | Win rate | 95% Wilson interval |
   |---|---:|---:|---:|
   | Before the stated tightening cohort | 7W–4L | 63.6% | 35.4%–84.8% |
   | After the stated tightening cohort | 4W–2L | 66.7% | 30.0%–90.3% |
   | Overall | 11W–6L | 64.7% | 41.3%–82.7% |

   The observed improvement is **3.0 percentage points**, with substantial uncertainty. This comparison also requires verification that the cohorts reflect **entry under the old/new gates**, rather than settlement dates.

   The early **7W–0L** run does not establish that the original edge was reliable. At a hypothetical constant 65% win probability, seven specified consecutive wins occur with probability **4.9%**. That calculation does not prove the later deterioration was luck; different entry prices, fixtures, and correlated exposures could explain it.

   **Concrete action:** retain `executable_edge >= 0.05`, `worst_variant_edge >= 0.04`, and `variant_spread <= 0.06` as provisional settings. Do not claim improvement or choose replacement thresholds from these six outcomes. A threshold replay needs frozen entry forecasts, executable prices, gate versions, and outcomes for rejected candidates as well as accepted bets. The supplied settled ledger must first be checked for those fields.

2. **For standard Dixon–Coles, changing `rho` cannot recalibrate Over 2.5 or higher total-goals probabilities.**

   The standard correction changes only the probabilities of **0–0, 0–1, 1–0, and 1–1**. Those corrections sum to zero, and all four scorelines lie below an Over 2.5 threshold. Therefore:

   - For **Over 2.5, Over 3.5, and higher lines**, changing `rho` has **zero theoretical effect** on fair probability.
   - Binary outcomes on those lines provide **no information with which to estimate `rho`**.
   - Standard Dixon–Coles also preserves each team’s marginal goal distribution, so it cannot repair team-total calibration.

   There is also a directional implication for the away-underdog hypothesis. Holding scoring intensities fixed, changing `rho` from **−0.1 to 0** increases both home-win and away-win probabilities. Each increase is
   \[
   0.1\,\lambda_h\lambda_a e^{-(\lambda_h+\lambda_a)},
   \]
   which is at most **1.35 percentage points**. That change would increase modeled away-win probability, potentially worsening the suspected overrating.

   **Concrete action:** do not use the O/U losses to justify a new `rho`. First inspect the implementation in [model_round5c.py](/home/ubuntu/paper-sim/round5/tools/model_round5c.py) and the production [soccer tools](/home/ubuntu/paper-sim/round15/soccer_tools/) to verify that they use the standard correction. Estimate `rho` from a broader, dated scoreline dataset; investigate scoring intensities and their uncertainty for higher-total and team-total errors. **No fitted replacement value is defensible from the information currently accessible.**

3. **Counting discretionary exits as losses confounds forecast accuracy with position management.**

   You explicitly identify this behavior in the [model-performance export](/home/ubuntu/paper-sim/review/model_performance.json). A position exited before resolution does not yet supply a binary outcome for assessing the original probability forecast. Its realized PnL remains valid financial evidence.

   **Concrete action:** distinguish these concepts in the reporting schema:

   | Field or metric | Proposed treatment |
   |---|---|
   | `position_status` | Separate `open`, `exited`, and `settled` |
   | `resolution_outcome` | Store the contract’s actual outcome separately; leave unknown until resolved |
   | Resolved forecast win rate / Brier score | Use known contract outcomes and frozen entry probabilities |
   | Realized PnL | Include exits and settlements |
   | Exit performance | Report exit count, proceeds, realized PnL, and reason separately |

   If an exited contract subsequently resolves, its entry forecast can still be scored against that outcome. Keep that forecast score separate from the actual exit PnL.

   **Expected effect:** no direct trading-profit uplift can be estimated, but this removes a known distortion in the evidence used to suspend or recalibrate models. The affected counts and dollars require inspection of the [settled ledger](/home/ubuntu/paper-sim/review/settled_ledger.json).

The inaccessible files prevent the requested away-underdog breakdown, recent-form counterfactuals, alternative-gate replay, GBM implementation audit, duplication assessment, schema audit, and defensible **top-five ranking by expected PnL impact / effort**. Assigning parameter changes, maintenance-risk estimates, or dollar benefits to those areas would invent evidence.

Automatic approval review rejected the browser file-read fallback because those calls require approval and this session’s approval policy is `never`. Completing the review requires working read-only file access; the two JSON exports pasted as text would unblock the ledger analysis.

VERDICT: 3 preliminary items, top priority = separate exits from resolved outcomes
dard Dixon–Coles. If it does, focus those investigations on goal-rate estimation and the goal-distribution tails.

**4. The away-underdog hypothesis is plausible but unquantified; 2W–4L does not establish systematic overrating.**

A 2/6 win rate has a 95% Wilson interval of approximately **9.7%–70.0%**. More fundamentally, six underdog forecasts should not be judged against a 50% win-rate benchmark. Their expected wins are the sum of their entry probabilities.

For the requested ledger analysis, define the subgroup explicitly: a **90-minute away-win selection whose entry market probability is below the home team’s probability**. Simply using “probability below 50%” would misclassify some favorites in three-outcome markets.

For that subgroup, compare:

- Actual wins versus \(\sum p_{\text{model}}\).
- Actual wins versus \(\sum p_{\text{market}}\), using comparable contemporaneous prices.
- Model-minus-market probability, Brier score, and realized PnL.
- Domestic fixtures versus cross-league European fixtures.

The European cases particularly warrant checking whether domestic league-relative xG strengths are being treated as comparable across leagues. That is a concrete code and feature audit, **not an established defect from the supplied results**.

**Recommendation:** retain the suspension while reconstructing this comparison. Do not introduce an arbitrary away-underdog haircut from six outcomes. Keep spread/blowout-tail suspended as well: its 1W–1L forward record cannot justify a tail parameter.

**5. Extreme xG inputs deserve a shrinkage experiment; the potential probability effect is large enough to erase the entry edge.**

Targets: [xg_epl_23.json](/home/ubuntu/paper-sim/round23/raw/xg_epl_23.json), [xg_understat_22.json](/home/ubuntu/paper-sim/round22/raw/xg_understat_22.json), and the soccer model’s blending logic.

PSG at 4.47 xG per game and Köln at 3.66 are investigation triggers. Köln’s approximately 1.6 actual goals per game is **not, by itself, evidence that its xG estimate should be replaced by 1.6**: finishing variation and chance creation measure different things.

First verify the inputs’ match counts, season identifiers, aggregation method, and timestamps. Then run a small, specified shadow comparison:

| Configuration | Purpose |
|---|---|
| `w=.5, p=8` | Existing baseline |
| `w=.5, p=16` | Stronger shrinkage |
| `w=.25, p=8` | Weight sensitivity |
| `w=.75, p=8` | Weight sensitivity |

The meaning of `w` must be confirmed from the code before describing either alternative as “more recent form.” If `p` is a conventional pseudo-match prior strength, increasing it from 8 to 16 reduces the observed-data weight at eight matches from **50% to 33.3%**, attenuating deviation from the prior by one third.

The economically relevant sensitivity is substantial. Under a Poisson total:

| Total-goal mean change | Over 2.5 probability change |
|---|---:|
| 2.5 → 2.3 | 45.62% → 40.40%, **−5.22c** |
| 3.0 → 2.8 | 57.68% → 53.05%, **−4.63c** |
| 4.0 → 3.8 | 76.19% → 73.11%, **−3.08c** |

These are mathematical sensitivities, not estimated errors in the actual bets. They show why a modest goal-rate bias could consume most of the 5c entry requirement.

Also, a ≤6c range across ten related variants is a sensitivity envelope, **not a calibrated confidence interval**. Shared bias can produce ten closely agreeing wrong forecasts. Choose a shrinkage change using chronological forecast evaluation across available matches, not only the selected bets.

**6. The crypto convention labels require reconciliation; additional model changes are not justified by the two cited adverse outcomes alone.**

Targets: [round19/raw](/home/ubuntu/paper-sim/round19/raw/) and [crypto_scan.json](/home/ubuntu/paper-sim/round15/raw/crypto_scan.json).

For standard GBM,

\[
dS/S=\mu\,dt+\sigma\,dW,\qquad
\log(S_T/S_0)=(\mu-\sigma^2/2)T+\sigma W_T.
\]

Thus **zero log drift and a flat median are the same convention**: both require \(\mu=\sigma^2/2\). A zero-arithmetic-drift model instead sets \(\mu=0\), giving log drift \(-\sigma^2/2\).

If A and B actually produce different probabilities, inspect their equations and rename them precisely. If their equations are identical, they supply no independent drift stress. This is a mathematical issue with the supplied labels; I cannot establish which implementation applies without reading the files.

Also verify that conservative probabilities are chosen **after orienting to the purchased side**. For touch probabilities \(p_A,p_B\):

\[
p_{\text{YES,conservative}}=\min(p_A,p_B),\qquad
p_{\text{NO,conservative}}=1-\max(p_A,p_B).
\]

Using the smaller touch probability to price a conservative NO would instead make NO more optimistic.

The −$200 daily-market resolution error does not establish a volatility defect. A terminal-price event and an intraday-touch event require different probability functions. At zero log drift, for a lower barrier, continuous touch probability is twice the terminal-below probability. Bind the validated resolution rule to the correct payoff function.

**Recommendation:** audit those three semantics—drift, selected-side conservatism, and payoff function. If correct, no additional model-side repair follows from the stated daily loss or discretionary touch exit. The +$1,305 ETH win likewise does not establish calibration.

**7. Consolidate active implementations while preserving historical round artifacts.**

Targets span [round5/tools](/home/ubuntu/paper-sim/round5/tools/), [round15/soccer_tools](/home/ubuntu/paper-sim/round15/soccer_tools/), [round22](/home/ubuntu/paper-sim/round22/), and [round23](/home/ubuntu/paper-sim/round23/).

Use one shared package for the active calculation paths:

| Shared component | Responsibility |
|---|---|
| Soccer model | xG blending, shrinkage, score matrix, market probabilities, variant definitions |
| Crypto model | Volatility units, drift definitions, terminal and barrier probabilities |
| Execution and gates | Side selection, $250 VWAP, fees, liquidity, gate decisions |
| Data and reporting | Timestamped snapshots, team identities, rule metadata, outcome/exit separation |

Keep round-specific scripts as thin configuration-driven entry points. Each run should record the shared model version, configuration, feature snapshot, rule version, and gate version. Preserve old round outputs and the versions needed to reproduce them.

Start by reproducing frozen existing examples before moving calculations. Useful regression checks include Dixon–Coles invariants, YES/NO complementarity, touch-versus-terminal behavior, and order-book VWAP calculations.

**Maintenance-risk estimate:** potentially material, but not measurable from directory count alone. Twenty-three rounds do not prove twenty-three model copies. If the same calculation exists in \(N\) active implementations, each correction has \(N\) propagation and verification surfaces; consolidation reduces that to one. Counting those implementations and identifying actual divergence remains an unfinished source audit.

The **provisional top five**, ranked by likely decision value and PnL relevance relative to effort, are:

| Rank | Optimization | Expected impact | Relative effort |
|---:|---|---|---|
| 1 | **Settlement-aware performance accounting and cohort reconstruction** | Corrects a stated defect before it drives suspensions, calibration, or gate changes | Low–medium |
| 2 | xG input validation and stronger-shrinkage shadow experiment | A 0.2-goal correction can move Over 2.5 fair value by roughly 3–5c | Medium |
| 3 | Away-underdog and cross-league calibration audit | Addresses the stated match-winner failure hypothesis; effect size remains unestimated | Medium–high |
| 4 | Shared probability and execution library | Reduces inconsistent fixes and makes model comparisons reproducible | Medium |
| 5 | Crypto drift, selected-side conservatism, and payoff-function audit | Potentially material if an equation or side-selection defect exists; no demonstrated incremental benefit otherwise | Low–medium |

There is insufficient evidence to rank a new gate threshold as an improvement or to quote an expected dollar PnL gain. Completing those parts requires the entry-level ledger and scan/source inspection.

Automatic approval review rejected browser file access because it required approval while this session’s policy is `never`. Shell reads separately failed with `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`. Those access failures prevented the requested bet-level replay and source-code verification.

VERDICT: 7 items, top priority = settlement-aware performance accounting
