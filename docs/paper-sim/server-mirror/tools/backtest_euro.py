#!/usr/bin/env python3
"""WP-P2b: European cup walk-forward backtest of the WP-P2a league-strength bridge.

Question: does the kappa bridge (league_strength_kappa.json / WP-P2a) justify
unbanning cross-league match_winner predictions? Walk-forward protocol: for
each evaluation season t in {2024-25, 2025-26}, fit kappa (and per-competition
base rates) on UCL/UEL matches from seasons strictly before t only, then score
predictions for every season-t match involving >=1 Big-5 club.

Model variants scored per match (all independent Poisson, 0..25 goal grid,
renormalized; matches the kappa estimation model exactly — no Dixon-Coles tau
in either estimation or evaluation):

  bridged          mu_h = H_comp * a_h * d_a * exp(kX - kY)
                   mu_a = A_comp * a_a * d_h * exp(kY - kX)        (fit model)
  bridged_clamped25  same, kappa differential clamped to +/- ln(1.25)
                   (the production bridge clamp, papersim league_strength)
  unbridged        kappa = 0 everywhere (the historical defect); base rates
                   re-fit closed-form on the same training window so the
                   paired T1 comparison isolates the bridge, not stale rates
  homefield        per-competition train mean home/away goals, all clubs
                   equal (no ratings, no bridge)
  leagueavg        constant 1X2 / O-U probabilities = training-window
                   outcome frequencies (no-skill reference)

Metrics: ranked probability score (RPS) on H/D/A, multiclass Brier on 1X2
(sum of 3 squared errors), Brier and calibration error on Over 2.5.

Cohorts: eval set (>=1 Big-5 club, settled full-time), cross-league subset,
Big-5 vs Big-5 direct pairs (different leagues — the pairs where the bridge
actually moves the prediction), and away-side selections (bridged argmax =
away win).

Pre-registered thresholds:
  T1  mean RPS(bridged) < mean RPS(unbridged) on Big-5 pairs (paired)
  T2  |sum p_away - actual away wins| / n <= 0.08 on away-side selections
  T3  |over2.5 cal err(bridged) - over2.5 cal err(unbridged)| <= 0.015
  T4  >= 20 settled cross-league MW paper bets before registry flip (future;
      noted, not computable from this backtest)
  T5  whole backtest re-runs bit-for-bit (verified externally by running the
      script twice and comparing SHA256; no wall-clock values are emitted)

Determinism: no timestamps, no dict-order dependence on unordered sets,
fixed iteration orders everywhere; identical inputs -> identical bytes.

Pure Python stdlib only (no numpy/scipy on the server).
"""

import hashlib
import json
import math
import os
import sys

TOOLS_DIR = "/home/ubuntu/paper-sim/tools"
REPO_SRC = "/home/ubuntu/polymarket-alpha-lab/src"
RESULTS = "/home/ubuntu/paper-sim/round31/raw/ucl_uel_results_3seasons.json"
KAPPA_FROZEN = "/home/ubuntu/paper-sim/round31/raw/league_strength_kappa.json"
OUT_JSON = "/home/ubuntu/paper-sim/round31/backtest_report.json"
OUT_MD = "/home/ubuntu/paper-sim/round31/backtest_report.md"

EVAL_SEASONS = ["2024-25", "2025-26"]
MODELS = ["bridged", "bridged_clamped25", "unbridged", "homefield", "leagueavg"]
GRID = 26  # goals 0..25 per side, renormalized
BRIDGE_CLAMP = math.log(1.25)  # production clamp (papersim league_strength)

sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, REPO_SRC)
import fit_league_strength as fls  # noqa: E402  (WP-P2a estimation tool)


# ---------------------------------------------------------------- utilities

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def pois_vec(lmb):
    out = []
    for k in range(GRID):
        try:
            logp = -lmb + k * math.log(lmb) - math.lgamma(k + 1)
        except ValueError:  # lmb == 0 (cannot happen; defensive)
            logp = 0.0 if k == 0 else -math.inf
        out.append(math.exp(logp) if logp > -745.0 else 0.0)
    s = sum(out)
    return [x / s for x in out]  # renormalize truncated tail


def probs_1x2_over(lh, la):
    ph = pois_vec(lh)
    pa = pois_vec(la)
    phw = pd = paw = pover = 0.0
    for i, pi in enumerate(ph):
        for j, pj in enumerate(pa):
            m = pi * pj
            if i > j:
                phw += m
            elif i == j:
                pd += m
            else:
                paw += m
            if i + j >= 3:
                pover += m
    return phw, pd, paw, pover


def rps_1x2(phw, pd, paw, oh, od, oa):
    ch, cd = phw, phw + pd
    rh, rd = 1.0 if oh else 0.0, (1.0 if oh else 0.0) + (1.0 if od else 0.0)
    return 0.5 * ((ch - rh) ** 2 + (cd - rd) ** 2)


def brier_1x2(phw, pd, paw, oh, od, oa):
    return ((phw - (1.0 if oh else 0.0)) ** 2
            + (pd - (1.0 if od else 0.0)) ** 2
            + (paw - (1.0 if oa else 0.0)) ** 2)


def sign_test_p(diffs):
    """Exact two-sided sign-test p-value (ties dropped)."""
    wins = sum(1 for x in diffs if x < 0.0)   # bridged better (lower RPS)
    losses = sum(1 for x in diffs if x > 0.0)
    n = wins + losses
    if n == 0:
        return 1.0, wins, losses
    k = min(wins, losses)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2.0 ** n)
    return min(1.0, 2.0 * tail), wins, losses


def ttest_p(diffs):
    """Paired t statistic and two-sided normal-approximation p-value."""
    n = len(diffs)
    if n < 2:
        return 0.0, 1.0
    mean = sum(diffs) / n
    var = sum((x - mean) ** 2 for x in diffs) / (n - 1)
    if var <= 0.0:
        return 0.0, 1.0
    t = mean / math.sqrt(var / n)
    return t, math.erfc(abs(t) / math.sqrt(2.0))


# ---------------------------------------------------------------- fitting

def unbridged_base_rates(obs):
    """Closed-form Poisson MLE base rates with kappa fixed at 0."""
    out = {}
    for comp in ("UCL", "UEL"):
        sub = [o for o in obs if o["comp"] == comp]
        sy_h = sum(o["y_h"] for o in sub)
        se_h = sum(math.exp(o["lc_h"]) for o in sub)
        sy_a = sum(o["y_a"] for o in sub)
        se_a = sum(math.exp(o["lc_a"]) for o in sub)
        out[comp] = (sy_h / se_h, sy_a / se_a)
    return out


def homefield_rates(matches_train):
    out = {}
    for comp in ("UCL", "UEL"):
        sub = [m for m in matches_train if m["comp"] == comp]
        out[comp] = (sum(m["score_home"] for m in sub) / len(sub),
                     sum(m["score_away"] for m in sub) / len(sub))
    return out


def leagueavg_probs(matches_train):
    n = len(matches_train)
    h = sum(1 for m in matches_train if m["score_home"] > m["score_away"])
    d = sum(1 for m in matches_train if m["score_home"] == m["score_away"])
    a = sum(1 for m in matches_train if m["score_home"] < m["score_away"])
    ov = sum(1 for m in matches_train if m["score_home"] + m["score_away"] >= 3)
    return h / n, d / n, a / n, ov / n


def fit_window(matches_train, mult, league_map):
    obs, fallback, skipped = fls.prepare_obs(matches_train, mult, league_map)
    fit = fls.Fit(obs, fls.build_targets(), fls.LAMBDA_RIDGE)
    theta, se, nll, iters = fit.run()
    kappa = {g: theta[4 + i] for i, g in enumerate(fls.GROUPS)}
    kappa_se = {g: se[4 + i] for i, g in enumerate(fls.GROUPS)}
    base = {
        "UCL": (math.exp(theta[0]), math.exp(theta[1])),
        "UEL": (math.exp(theta[2]), math.exp(theta[3])),
    }
    return {
        "obs": obs, "kappa": kappa, "kappa_se": kappa_se, "base": base,
        "nll": nll, "iters": iters, "fallback": fallback, "skipped": skipped,
        "unbridged_base": unbridged_base_rates(obs),
        "homefield": homefield_rates(matches_train),
        "leagueavg": leagueavg_probs(matches_train),
    }


# ---------------------------------------------------------------- build/run

def build_report():
    results = json.load(open(RESULTS))
    matches = results["matches"]
    league_map = results["league_map"]
    mult = fls.load_multipliers()
    big5 = set(fls.BIG5)
    frozen = json.load(open(KAPPA_FROZEN))

    matches_ft = [m for m in matches if m.get("status") == "STATUS_FULL_TIME"]
    n_non_ft = len(matches) - len(matches_ft)

    # ---------------- walk-forward fits
    wf = {}
    for t in EVAL_SEASONS:
        train = [m for m in matches_ft if m["season_bucket"] < t]
        wf[t] = fit_window(train, mult, league_map)

    # reproducibility check: refit on all matches reproduces the frozen table
    obs_all, _, _ = fls.prepare_obs(matches_ft, mult, league_map)
    fit_all = fls.Fit(obs_all, fls.build_targets(), fls.LAMBDA_RIDGE)
    theta_all, _, _, _ = fit_all.run()
    kappa_all = {g: theta_all[4 + i] for i, g in enumerate(fls.GROUPS)}
    refit_diff = max(abs(kappa_all[g] - frozen["kappa"][g]) for g in fls.GROUPS)

    # ---------------- per-match prediction + scoring
    per_match = []
    eval_rows = {t: [] for t in EVAL_SEASONS}
    for t in EVAL_SEASONS:
        f = wf[t]
        kap = f["kappa"]
        base = f["base"]
        ub = f["unbridged_base"]
        hf = f["homefield"]
        lg_probs = f["leagueavg"]
        for m in matches_ft:
            if m["season_bucket"] != t:
                continue
            hn, an = m["home_name"], m["away_name"]
            hl = league_map[hn]["league"]
            al = league_map[an]["league"]
            if hl not in big5 and al not in big5:
                continue  # prediction scope: >=1 Big-5 club
            hkey = league_map[hn].get("understat_name") or hn
            akey = league_map[an].get("understat_name") or an
            mh = mult.get(hkey)
            ma = mult.get(akey)
            alpha_h, delta_h = (mh["alpha"], mh["delta"]) if mh else (1.0, 1.0)
            alpha_a, delta_a = (ma["alpha"], ma["delta"]) if ma else (1.0, 1.0)
            lc_h = math.log(alpha_h * delta_a)
            lc_a = math.log(alpha_a * delta_h)
            lgh = hl if hl in fls.GROUPS else "nuisance"
            lga = al if al in fls.GROUPS else "nuisance"
            kd = kap[lgh] - kap[lga]
            kd_c = max(-BRIDGE_CLAMP, min(BRIDGE_CLAMP, kd))
            comp = m["comp"]
            bh, ba = base[comp]
            uh, ua = ub[comp]
            hh, ha = hf[comp]
            lambdas = {
                "bridged": (bh * math.exp(lc_h + kd), ba * math.exp(lc_a - kd)),
                "bridged_clamped25": (bh * math.exp(lc_h + kd_c), ba * math.exp(lc_a - kd_c)),
                "unbridged": (uh * math.exp(lc_h), ua * math.exp(lc_a)),
                "homefield": (hh, ha),
            }
            sh, sa = m["score_home"], m["score_away"]
            oh, od, oa = sh > sa, sh == sa, sh < sa
            over = sh + sa >= 3
            row = {
                "event_id": m["event_id"], "date": m["date"], "comp": comp,
                "season": t, "home": hn, "away": an,
                "lg_h": hl, "lg_a": al, "score": f"{sh}-{sa}",
                "outcome": "H" if oh else ("D" if od else "A"), "over25": over,
                "big5_pair_cross": (hl in big5 and al in big5 and hl != al),
                "big5_pair_any": (hl in big5 and al in big5),
                "cross_league": hl != al,
                "models": {},
            }
            for name, (lh, la) in lambdas.items():
                ph, pd_, pa, pov = probs_1x2_over(lh, la)
                row["models"][name] = {
                    "lh": round(lh, 6), "la": round(la, 6),
                    "pH": round(ph, 6), "pD": round(pd_, 6), "pA": round(pa, 6),
                    "pOver": round(pov, 6),
                    "rps": round(rps_1x2(ph, pd_, pa, oh, od, oa), 6),
                    "brier": round(brier_1x2(ph, pd_, pa, oh, od, oa), 6),
                    "over_brier": round((pov - (1.0 if over else 0.0)) ** 2, 6),
                }
            # league average: constant probabilities
            lh_, ld_, la_, lov_ = lg_probs
            row["models"]["leagueavg"] = {
                "lh": None, "la": None,
                "pH": round(lh_, 6), "pD": round(ld_, 6), "pA": round(la_, 6),
                "pOver": round(lov_, 6),
                "rps": round(rps_1x2(lh_, ld_, la_, oh, od, oa), 6),
                "brier": round(brier_1x2(lh_, ld_, la_, oh, od, oa), 6),
                "over_brier": round((lov_ - (1.0 if over else 0.0)) ** 2, 6),
            }
            row["away_selected_bridged"] = row["models"]["bridged"]["pA"] >= max(
                row["models"]["bridged"]["pH"], row["models"]["bridged"]["pD"])
            per_match.append(row)
            eval_rows[t].append(row)

    # ---------------- aggregate metrics
    def cohort_metrics(rows):
        out = {}
        for name in MODELS:
            n = len(rows)
            if n == 0:
                continue
            mset = [r["models"][name] for r in rows]
            freq_over = sum(1 for r in rows if r["over25"]) / n
            mean_p_over = sum(x["pOver"] for x in mset) / n
            out[name] = {
                "n": n,
                "rps_mean": round(sum(x["rps"] for x in mset) / n, 6),
                "brier1x2_mean": round(sum(x["brier"] for x in mset) / n, 6),
                "over_brier_mean": round(sum(x["over_brier"] for x in mset) / n, 6),
                "over_cal_err": round(mean_p_over - freq_over, 6),
                "over_cal_abs": round(abs(mean_p_over - freq_over), 6),
                "mean_pA": round(sum(x["pA"] for x in mset) / n, 6),
                "freq_away_win": round(sum(1 for r in rows if r["outcome"] == "A") / n, 6),
            }
        return out

    def cohorts(rows):
        return {
            "eval_all": cohort_metrics(rows),
            "cross_league": cohort_metrics([r for r in rows if r["cross_league"]]),
            "big5_pair_cross": cohort_metrics([r for r in rows if r["big5_pair_cross"]]),
            "big5_pair_any": cohort_metrics([r for r in rows if r["big5_pair_any"]]),
            "away_selected": cohort_metrics([r for r in rows if r["away_selected_bridged"]]),
        }

    pooled = [r for r in per_match]
    metrics = {"pooled": cohorts(pooled)}
    for t in EVAL_SEASONS:
        metrics[t] = cohorts(eval_rows[t])

    # ---------------- thresholds
    def paired_t1(rows, model_a="bridged", model_b="unbridged"):
        sel = [r for r in rows if r["big5_pair_cross"]]
        d = [r["models"][model_a]["rps"] - r["models"][model_b]["rps"] for r in sel]
        if not d:
            return None
        mean_d = sum(d) / len(d)
        t, p_t = ttest_p(d)
        p_s, wins, losses = sign_test_p(d)
        return {
            "n": len(d), "mean_rps_a": round(sum(x["models"][model_a]["rps"] for x in sel) / len(d), 6),
            "mean_rps_b": round(sum(x["models"][model_b]["rps"] for x in sel) / len(d), 6),
            "mean_diff": round(mean_d, 6),
            "t_stat": round(t, 4), "p_t_normal": round(p_t, 6),
            "sign_wins_a_better": wins, "sign_losses": losses,
            "p_sign_exact": round(p_s, 6),
        }

    t1 = paired_t1(pooled)
    t1["by_season"] = {t: paired_t1(eval_rows[t]) for t in EVAL_SEASONS}
    t1["clamped_variant"] = paired_t1(pooled, "bridged_clamped25", "unbridged")
    t1["pass"] = bool(t1["mean_rps_a"] < t1["mean_rps_b"])

    def t2_stat(rows):
        sel = [r for r in rows if r["away_selected_bridged"]]
        n = len(sel)
        if n == 0:
            return None
        sump = sum(r["models"]["bridged"]["pA"] for r in sel)
        wins = sum(1 for r in sel if r["outcome"] == "A")
        return {"n": n, "sum_pA": round(sump, 4), "away_wins": wins,
                "cal_err": round(abs(sump - wins) / n, 6)}

    t2 = t2_stat(pooled)
    t2["by_season"] = {t: t2_stat(eval_rows[t]) for t in EVAL_SEASONS}
    # secondary definition: explicit pA > 0.5 selections
    def t2_alt(rows):
        sel = [r for r in rows if r["models"]["bridged"]["pA"] > 0.5]
        n = len(sel)
        if n == 0:
            return None
        sump = sum(r["models"]["bridged"]["pA"] for r in sel)
        wins = sum(1 for r in sel if r["outcome"] == "A")
        return {"n": n, "cal_err": round(abs(sump - wins) / n, 6)}
    t2["alt_definition_pA_gt_050"] = t2_alt(pooled)
    t2["pass"] = bool(t2["cal_err"] <= 0.08)

    def t3_stat(rows):
        def cal(rows_, name):
            n = len(rows_)
            return sum(r["models"][name]["pOver"] for r in rows_) / n - (
                sum(1 for r in rows_ if r["over25"]) / n)
        cb = cal(rows, "bridged")
        cu = cal(rows, "unbridged")
        return {"cal_bridged": round(cb, 6), "cal_unbridged": round(cu, 6),
                "diff": round(cb - cu, 6), "abs_diff": round(abs(cb - cu), 6)}
    t3 = t3_stat(pooled)
    t3["by_season"] = {t: t3_stat(eval_rows[t]) for t in EVAL_SEASONS}
    t3["pass"] = bool(t3["abs_diff"] <= 0.015)

    t5 = {"requirement": "whole backtest re-runs bit-for-bit from the frozen fixture",
          "method": "two independent in-process builds serialized and byte-compared (plus external two-process file-hash compare at dispatch)",
          "emits_wall_clock": False, "pass": None}  # filled by double-build compare in main()

    thresholds = {"T1": t1, "T2": t2, "T3": t3,
                  "T4": {"requirement": ">=20 settled cross-league MW paper bets before registry flip",
                         "status": "future", "pass": None},
                  "T5": t5}

    hard = [t1["pass"], t2["pass"], t3["pass"]]  # T5 joined in main() after double-build
    overall = "PASS" if all(hard) else "FAIL"
    # main() recomputes this including T5 once the double-build compare is done

    # ---------------- counts
    counts = {}
    for m in matches_ft:
        key = m["season_bucket"] + "|" + m["comp"]
        counts[key] = counts.get(key, 0) + 1
    eval_counts = {}
    for r in per_match:
        key = r["season"] + "|" + r["comp"]
        eval_counts[key] = eval_counts.get(key, 0) + 1
    cohort_counts = {
        "pooled_eval": len(per_match),
        "pooled_big5_pair_cross": sum(1 for r in per_match if r["big5_pair_cross"]),
        "pooled_big5_pair_any": sum(1 for r in per_match if r["big5_pair_any"]),
        "pooled_away_selected": sum(1 for r in per_match if r["away_selected_bridged"]),
    }

    report = {
        "work_package": "WP-P2b",
        "question": "does the WP-P2a kappa bridge justify unbanning cross-league match_winner",
        "inputs": {
            RESULTS: {"sha256": sha256_file(RESULTS), "bytes": os.path.getsize(RESULTS)},
            KAPPA_FROZEN: {"sha256": sha256_file(KAPPA_FROZEN), "bytes": os.path.getsize(KAPPA_FROZEN)},
            fls.UNDERSTAT: {"sha256": sha256_file(fls.UNDERSTAT), "bytes": os.path.getsize(fls.UNDERSTAT)},
        },
        "protocol": {
            "eval_seasons": EVAL_SEASONS,
            "train_rule": "season_bucket strictly < evaluation season, STATUS_FULL_TIME only",
            "prediction_scope": "matches involving >=1 Big-5 club",
            "goal_model": "independent Poisson grid 0..25, renormalized (matches kappa estimation; no Dixon-Coles tau)",
            "multipliers": "Understat 2025/26 snapshot reused for all seasons (documented approximation, same as WP-P2a fit)",
            "kappa_estimator": "fit_league_strength.Fit (projected Newton, ridge lambda=15 toward UEFA targets, cap +/-ln1.35)",
            "unbridged_baseline": "kappa=0 with base rates re-fit closed-form on the same training window",
            "homefield_baseline": "per-competition train mean home/away goals, clubs equal",
            "leagueavg_baseline": "constant training-window outcome frequencies (no-skill reference)",
            "brier_definition": "3-outcome sum of squared errors; over2.5 Brier is binary squared error",
            "rps_definition": "0.5*[(F1(p)-F1(o))^2+(F2(p)-F2(o))^2] over ordered H,D,A",
            "away_side_selection": "bridged model argmax == away win (draw counts against selection)",
            "non_ft_matches_excluded": n_non_ft,
        },
        "counts": {"all_matches_by_season_comp": counts,
                   "eval_matches_by_season_comp": eval_counts,
                   "cohorts": cohort_counts},
        "walk_forward": {
            t: {
                "n_train_matches": len([m for m in matches_ft if m["season_bucket"] < t]),
                "kappa": {g: round(wf[t]["kappa"][g], 6) for g in fls.GROUPS},
                "kappa_se": {g: round(wf[t]["kappa_se"][g], 6) for g in fls.GROUPS},
                "base_rates_bridged": {
                    "UCL_home": round(wf[t]["base"]["UCL"][0], 4),
                    "UCL_away": round(wf[t]["base"]["UCL"][1], 4),
                    "UEL_home": round(wf[t]["base"]["UEL"][0], 4),
                    "UEL_away": round(wf[t]["base"]["UEL"][1], 4),
                },
                "base_rates_unbridged": {
                    "UCL_home": round(wf[t]["unbridged_base"]["UCL"][0], 4),
                    "UCL_away": round(wf[t]["unbridged_base"]["UCL"][1], 4),
                    "UEL_home": round(wf[t]["unbridged_base"]["UEL"][0], 4),
                    "UEL_away": round(wf[t]["unbridged_base"]["UEL"][1], 4),
                },
                "neg_log_likelihood_penalized": round(wf[t]["nll"], 4),
                "newton_iters": wf[t]["iters"],
            } for t in EVAL_SEASONS
        },
        "full_sample_reference": {
            "kappa_published": frozen["kappa"],
            "kappa_refit_check_max_abs_diff": round(refit_diff, 9),
            "refit_matches": len(obs_all),
        },
        "metrics": metrics,
        "thresholds": thresholds,
        "overall_verdict": overall,
        "per_match": per_match,
    }

    return report


def main():
    # T5: two independent builds of the whole pipeline must serialize identically.
    r1 = build_report()
    r2 = build_report()
    identical = json.dumps(r1, indent=1) == json.dumps(r2, indent=1)
    report = r1
    t5 = report["thresholds"]["T5"]
    t5["in_process_double_build_identical"] = bool(identical)
    t5["pass"] = bool(identical)
    t1 = report["thresholds"]["T1"]
    t2 = report["thresholds"]["T2"]
    t3 = report["thresholds"]["T3"]
    report["overall_verdict"] = "PASS" if all(
        [t1["pass"], t2["pass"], t3["pass"], t5["pass"]]) else "FAIL"
    overall = report["overall_verdict"]
    counts = report["counts"]["all_matches_by_season_comp"]
    eval_counts = report["counts"]["eval_matches_by_season_comp"]
    cohort_counts = report["counts"]["cohorts"]
    wf_kappa = {t: report["walk_forward"][t]["kappa"] for t in EVAL_SEASONS}
    frozen_kappa = report["full_sample_reference"]["kappa_published"]
    refit_diff = report["full_sample_reference"]["kappa_refit_check_max_abs_diff"]
    per_match = report["per_match"]
    metrics = report["metrics"]

    with open(OUT_JSON, "w") as fh:
        json.dump(report, fh, indent=1)
    jsha = sha256_file(OUT_JSON)

    # ---------------- markdown report
    md = []
    md.append("# WP-P2b: European cup walk-forward backtest (cross-league MW unban)\n")
    md.append("Question: does the WP-P2a league-strength kappa bridge justify unbanning")
    md.append("cross-league `match_winner` predictions?\n")
    md.append("## Inputs (frozen)\n")
    for p, meta in report["inputs"].items():
        md.append(f"- `{p}` — sha256 `{meta['sha256']}`, {meta['bytes']} bytes")
    md.append("")
    md.append("## Protocol\n")
    for k, v in report["protocol"].items():
        md.append(f"- **{k}**: {v}")
    md.append("")
    md.append("## (1) Match counts\n")
    md.append("| season | comp | all (FT) | in eval scope |")
    md.append("|---|---|---|---|")
    for t in ["2023-24", "2024-25", "2025-26"]:
        for comp in ["UCL", "UEL"]:
            k = f"{t}|{comp}"
            md.append(f"| {t} | {comp} | {counts.get(k, 0)} | {eval_counts.get(k, 0)} |")
    md.append("")
    for k, v in cohort_counts.items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## (2) Walk-forward kappa\n")
    md.append("| group | 2024-25 eval (train 2023-24, n=%d) | 2025-26 eval (train 2023-24+2024-25, n=%d) | full-sample (frozen) |"
               % (report["walk_forward"]["2024-25"]["n_train_matches"],
                  report["walk_forward"]["2025-26"]["n_train_matches"]))
    md.append("|---|---|---|---|")
    for g in fls.GROUPS:
        md.append("| %s | %.6f | %.6f | %.6f |" % (
            g, wf_kappa["2024-25"][g], wf_kappa["2025-26"][g], frozen_kappa[g]))
    md.append("")
    md.append("Refit-on-all-matches check vs frozen table: max abs kappa diff = %.2e (estimator reproduction).\n"
              % refit_diff)
    md.append("## Metrics (pooled eval set, n=%d)\n" % len(per_match))
    for cohort in ["eval_all", "cross_league", "big5_pair_cross", "away_selected"]:
        md.append(f"### Cohort: {cohort}\n")
        md.append("| model | n | RPS 1X2 | Brier 1X2 | O/U Brier | O/U cal err | mean pA | freq away win |")
        md.append("|---|---|---|---|---|---|---|---|")
        blk = metrics["pooled"][cohort]
        for name in MODELS:
            if name in blk:
                x = blk[name]
                md.append("| %s | %d | %.4f | %.4f | %.4f | %+.4f | %.4f | %.4f |" % (
                    name, x["n"], x["rps_mean"], x["brier1x2_mean"], x["over_brier_mean"],
                    x["over_cal_err"], x["mean_pA"], x["freq_away_win"]))
        md.append("")
    md.append("Per-season detail in backtest_report.json (`metrics.by_season`, `thresholds.T*.by_season`).\n")
    md.append("## (3) Thresholds T1-T5\n")
    md.append("| id | requirement | observed | verdict |")
    md.append("|---|---|---|---|")
    md.append("| T1 | bridged 1X2 RPS < unbridged on Big-5 pairs (paired) | "
              "%.4f vs %.4f, mean diff %+.4f, sign %d/%d, p_sign %.4f, t %.2f (p_t %.4f) | %s |" % (
                  t1["mean_rps_a"], t1["mean_rps_b"], t1["mean_diff"],
                  t1["sign_wins_a_better"], t1["sign_losses"], t1["p_sign_exact"],
                  t1["t_stat"], t1["p_t_normal"], "PASS" if t1["pass"] else "FAIL"))
    md.append("| T2 | abs(sum pA - away wins)/n <= 0.08 on away-side selections | "
              "n=%d, |%.2f - %d|/%d = %.4f | %s |" % (
                  t2["n"], t2["sum_pA"], t2["away_wins"], t2["n"], t2["cal_err"],
                  "PASS" if t2["pass"] else "FAIL"))
    md.append("| T3 | bridged O/U 2.5 cal err within 1.5pp of unbridged | "
              "%+.4f vs %+.4f, abs diff %.4f | %s |" % (
                  t3["cal_bridged"], t3["cal_unbridged"], t3["abs_diff"],
                  "PASS" if t3["pass"] else "FAIL"))
    md.append("| T4 | >=20 settled cross-league MW paper bets before registry flip | future requirement, not computable from this backtest | N/A (noted) |")
    md.append("| T5 | whole backtest re-runs bit-for-bit | in-process double-build identical = %s (external two-process file-hash compare also done at dispatch) | %s |" % (
        t5["in_process_double_build_identical"], "PASS" if t5["pass"] else "FAIL"))
    md.append("")
    md.append("## (4) Verdict\n")
    md.append("Overall: **%s** (T1 %s, T2 %s, T3 %s, T5 %s; T4 future-noted).\n"
              % (overall, "PASS" if t1["pass"] else "FAIL", "PASS" if t2["pass"] else "FAIL",
                 "PASS" if t3["pass"] else "FAIL", "PASS" if t5["pass"] else "FAIL"))
    md.append("Report JSON sha256: `%s`\n" % jsha)

    with open(OUT_MD, "w") as fh:
        fh.write("\n".join(md) + "\n")
    print("WROTE", OUT_JSON, jsha)
    print("WROTE", OUT_MD)
    print("OVERALL", overall)


if __name__ == "__main__":
    main()
