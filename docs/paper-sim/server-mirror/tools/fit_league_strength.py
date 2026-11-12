#!/usr/bin/env python3
"""WP-P2a Phase B: Poisson MLE league-strength fit (kappa) from UCL/UEL results.

Model (per match m, home club i from league X, away club j from league Y):

    log mu_home = log H_comp + log alpha_i + log delta_j + (kappa_X - kappa_Y)
    log mu_away = log A_comp + log alpha_j + log delta_i + (kappa_Y - kappa_X)

SIGN CONVENTION (documented deviation from the task text):
The task text writes the kappa differential as (kappa_Y - kappa_X) in
log mu_home. That parameterisation makes kappa a league-WEAKNESS score
(weak leagues get high kappa). The same task also requires a ridge prior
toward UEFA country coefficients (England strongest) and gate G-B
Spearman(kappa ranking, UEFA coef ranking) >= 0.8, which only make sense
if kappa is league-STRENGTH. lambda = -kappa_task rewrites the model
identically as (kappa_X - kappa_Y) above, i.e. the SAME likelihood with
kappa published as strength (higher = stronger league). We fit that form
so kappa, the UEFA ridge and gate G-B share one coherent convention.

    - alpha_i, delta_j: club attack / defensive-weakness multipliers from
      Understat 2025/26 season snapshot (round25/raw/xg_understat_25.json,
      keys X_2025 = season 2025/26, complete 38/34 rounds). Club multiplier
      = (club xG per game)/(league mean xG per game). For 2023-24 and
      2024-25 UCL seasons the same 2025/26 multipliers are reused as an
      approximation (task instruction; documented).
    - Clubs absent from the Understat 2025/26 snapshot get alpha=delta=1.0
      (league-average placeholder; counted and reported).
    - H_comp/A_comp: per-competition base rates (UCL, UEL), pooled across
      the three seasons.
    - kappa for 6 groups: EPL, La_liga, Serie_A, Bundesliga, Ligue_1, and
      one shared nuisance group for every non-Big-5 league.
    - Estimation: joint Newton-Raphson on 10 parameters with analytic
      gradient/Hessian, pure Python (no numpy/scipy). Poisson log-likelihood
      plus ridge penalty -LAMBDA * sum_{big5} (kappa_X - t_X)^2 toward UEFA
      country coefficients (targets in log space, centred at the Big-5
      geometric mean). The ridge also fixes the global-shift degeneracy of
      the difference-only parameterisation.
    - kappa capped to +/- log(1.35) (projected Newton: clipped each step).
    - Standard errors from the inverse penalized Fisher information.

Inputs : ~/paper-sim/round31/raw/ucl_uel_results_3seasons.json  (Phase A)
         ~/paper-sim/round25/raw/xg_understat_25.json            (Understat)
Output : ~/paper-sim/round31/raw/league_strength_kappa.json
"""
import json
import math

RESULTS = "/home/ubuntu/paper-sim/round31/raw/ucl_uel_results_3seasons.json"
UNDERSTAT = "/home/ubuntu/paper-sim/round25/raw/xg_understat_25.json"
OUT = "/home/ubuntu/paper-sim/round31/raw/league_strength_kappa.json"

BIG5 = ["EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1"]
GROUPS = BIG5 + ["nuisance"]
CAP = math.log(1.35)

# UEFA country coefficients, 5-season table published on Wikipedia
# ("UEFA coefficient", current ranking as of 22 Oct 2026). Per-season columns
# 2022-23..2026-27; we sum the four COMPLETED seasons 2022-23..2025-26 to
# match the UCL/UEL data window (Sep 2023 - Jan 2026).
UEFA_RAW = {
    "EPL":        [23.000, 17.375, 29.464, 28.680],  # England
    "Serie_A":    [22.357, 21.000, 21.875, 19.000],  # Italy
    "La_liga":    [16.571, 16.062, 23.892, 22.093],  # Spain
    "Bundesliga": [17.125, 19.357, 18.421, 21.785],  # Germany
    "Ligue_1":    [12.583, 16.250, 17.928, 18.321],  # France
}
UEFA_4SEASON = {lg: sum(v) for lg, v in UEFA_RAW.items()}
LAMBDA_RIDGE = 15.0


def load_multipliers():
    d = json.load(open(UNDERSTAT))
    mult = {}
    for lg in BIG5:
        key = lg + "_2025"  # 2025/26 season, complete
        teams = d[key]["teams"]
        per_game = {}
        for tid, t in teams.items():
            h = t["history"]
            if not h:
                continue
            n = len(h)
            xg = sum(float(m["xG"]) for m in h)
            xga = sum(float(m["xGA"]) for m in h)
            per_game[t["title"]] = (xg / n, xga / n, n)
        league_mean_att = sum(v[0] for v in per_game.values()) / len(per_game)
        league_mean_def = sum(v[1] for v in per_game.values()) / len(per_game)
        for name, (att, dfn, n) in per_game.items():
            mult[name] = {
                "league": lg,
                "alpha": att / league_mean_att,
                "delta": dfn / league_mean_def,
                "xg_pg": att, "xga_pg": dfn, "games": n,
            }
    return mult


def build_targets():
    logs = {lg: math.log(v) for lg, v in UEFA_4SEASON.items()}
    mean_log = sum(logs.values()) / len(logs)
    return {lg: logs[lg] - mean_log for lg in BIG5}


def lin_solve(a, b):
    """Solve a x = b (a list of lists, b list). Gaussian elimination + partial pivot."""
    n = len(a)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-14:
            raise ValueError("singular matrix")
        m[c], m[p] = m[p], m[c]
        piv = m[c][c]
        for r in range(n):
            if r == c:
                continue
            f = m[r][c] / piv
            if f != 0.0:
                for k in range(c, n + 1):
                    m[r][k] -= f * m[c][k]
    return [m[i][n] / m[i][i] for i in range(n)]


def mat_inv(a):
    n = len(a)
    cols = []
    for j in range(n):
        e = [1.0 if i == j else 0.0 for i in range(n)]
        cols.append(lin_solve([row[:] for row in a], e))
    return [[cols[j][i] for j in range(n)] for i in range(n)]


class Fit:
    """Parameters theta = [logH_UCL, logA_UCL, logH_UEL, logA_UEL, kappa per group in groups]."""

    def __init__(self, obs, targets, lam, groups=None):
        self.obs = obs
        self.targets = targets
        self.lam = lam
        self.groups = list(groups) if groups is not None else list(GROUPS)
        self.p = 4 + len(self.groups)
        self.gidx = {g: 4 + i for i, g in enumerate(self.groups)}

    def negll_grad_hess(self, theta):
        g = [0.0] * self.p
        h = [[0.0] * self.p for _ in range(self.p)]
        nll = 0.0
        for o in self.obs:
            kh = self.gidx[o["lg_h"]]
            ka = self.gidx[o["lg_a"]]
            # home term
            eta_h = theta[0 if o["comp"] == "UCL" else 2] + o["lc_h"] + theta[kh] - theta[ka]
            mu_h = math.exp(eta_h)
            y = o["y_h"]
            nll += mu_h - y * eta_h
            dh = [0.0] * self.p
            dh[0 if o["comp"] == "UCL" else 2] = 1.0
            dh[kh] = 1.0
            dh[ka] = -1.0
            r = y - mu_h
            for a in range(self.p):
                if dh[a] != 0.0:
                    g[a] -= r * dh[a]
                    for b in range(self.p):
                        if dh[b] != 0.0:
                            h[a][b] += mu_h * dh[a] * dh[b]
            # away term
            eta_a = theta[1 if o["comp"] == "UCL" else 3] + o["lc_a"] + theta[ka] - theta[kh]
            mu_a = math.exp(eta_a)
            y = o["y_a"]
            nll += mu_a - y * eta_a
            da = [0.0] * self.p
            da[1 if o["comp"] == "UCL" else 3] = 1.0
            da[ka] = 1.0
            da[kh] = -1.0
            r = y - mu_a
            for a in range(self.p):
                if da[a] != 0.0:
                    g[a] -= r * da[a]
                    for b in range(self.p):
                        if da[b] != 0.0:
                            h[a][b] += mu_a * da[a] * da[b]
        # ridge on big5 kappa (only for groups present in this fit)
        for lg in self.groups:
            if lg not in BIG5:
                continue
            k = self.gidx[lg]
            g[k] += 2.0 * self.lam * (theta[k] - self.targets[lg])
            h[k][k] += 2.0 * self.lam
        return nll, g, h

    def run(self, iters=200, tol=1e-11):
        theta = [0.0] * self.p
        # init base rates from mean goals
        for comp_i, comp in enumerate(["UCL", "UEL"]):
            hy = [o["y_h"] for o in self.obs if o["comp"] == comp]
            ay = [o["y_a"] for o in self.obs if o["comp"] == comp]
            theta[2 * comp_i] = math.log(max(1e-6, sum(hy) / max(1, len(hy))))
            theta[2 * comp_i + 1] = math.log(max(1e-6, sum(ay) / max(1, len(ay))))
        for lg in self.groups:
            if lg in BIG5:
                theta[self.gidx[lg]] = self.targets[lg]
        # active-set projected Newton: kappa params sitting at a cap with the
        # gradient pushing outward stay FIXED at the bound; Newton solves the
        # reduced system over the free parameters each iteration.
        free_grad_final = None
        for it in range(iters):
            nll, g, h = self.negll_grad_hess(theta)
            free_idx = list(range(4))  # base rates are unbounded
            for i in range(4, self.p):
                at_lo = theta[i] <= -CAP + 1e-12
                at_hi = theta[i] >= CAP - 1e-12
                if (at_lo and g[i] > 0.0) or (at_hi and g[i] < 0.0):
                    continue  # active constraint: hold at the bound
                free_idx.append(i)
            sub_h = [[h[a][b] for b in free_idx] for a in free_idx]
            sub_g = [g[a] for a in free_idx]
            try:
                sub_step = lin_solve(sub_h, [-x for x in sub_g])
            except ValueError:
                break
            step = [0.0] * self.p
            for j, a in enumerate(free_idx):
                step[a] = sub_step[j]
            # step halving on the penalized objective; project kappa to caps
            t = 1.0
            cand = None
            for _ in range(60):
                cand = [theta[i] + t * step[i] for i in range(self.p)]
                for i in range(4, self.p):
                    cand[i] = max(-CAP, min(CAP, cand[i]))
                n2, _, _ = self.negll_grad_hess(cand)
                if n2 <= nll + 1e-12:
                    break
                t *= 0.5
            theta = cand
            free_grad_final = max(abs(g[a]) for a in free_idx)
            if max(abs(x) for x in step) < tol:
                break
        nll, g, h = self.negll_grad_hess(theta)
        cov = mat_inv(h)  # penalized curvature (Fisher) at the constrained optimum
        se = [math.sqrt(max(cov[i][i], 0.0)) for i in range(self.p)]
        self.free_grad_final = free_grad_final
        return theta, se, nll, it


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    d2 = sum((a - b) ** 2 for a, b in zip(rx, ry))
    return 1.0 - 6.0 * d2 / (n * (n * n - 1))


def prepare_obs(matches, mult, league_map):
    obs = []
    fallback = {}
    skipped = 0
    for mrec in matches:
        hn, an = mrec["home_name"], mrec["away_name"]
        hl = league_map.get(hn, {}).get("league")
        al = league_map.get(an, {}).get("league")
        if not hl or not al:
            skipped += 1
            continue
        hkey = league_map[hn].get("understat_name") or hn
        akey = league_map[an].get("understat_name") or an
        mh = mult.get(hkey)
        ma = mult.get(akey)
        alpha_h, delta_h = (mh["alpha"], mh["delta"]) if mh else (1.0, 1.0)
        alpha_a, delta_a = (ma["alpha"], ma["delta"]) if ma else (1.0, 1.0)
        if not mh:
            fallback[hn] = fallback.get(hn, 0) + 1
        if not ma:
            fallback[an] = fallback.get(an, 0) + 1
        obs.append({
            "comp": mrec["comp"], "season": mrec["season_bucket"],
            "lg_h": hl if hl in GROUPS else "nuisance",
            "lg_a": al if al in GROUPS else "nuisance",
            "lc_h": math.log(alpha_h * delta_a),
            "lc_a": math.log(alpha_a * delta_h),
            "y_h": float(mrec["score_home"]), "y_a": float(mrec["score_away"]),
            "big5_big5": (hl in BIG5 and al in BIG5 and hl != al),
        })
    return obs, fallback, skipped


def main():
    results = json.load(open(RESULTS))
    matches = results["matches"]
    league_map = results["league_map"]
    mult = load_multipliers()
    targets = build_targets()
    obs, fallback, skipped = prepare_obs(matches, mult, league_map)

    out = {
        "model": {
            "log_mu_home": "log H_comp + log alpha_i + log delta_j + (kappa_X - kappa_Y)",
            "log_mu_away": "log A_comp + log alpha_j + log delta_i + (kappa_Y - kappa_X)",
            "kappa_sign_convention": ("kappa is league STRENGTH (higher = stronger); it equals minus the "
                                      "weakness parameterisation written in the task text; identical likelihood"),
            "club_multipliers": ("Understat 2025/26 season (xg_understat_25.json keys *_2025, complete season); "
                                 "reused for 2023-24 and 2024-25 UCL seasons as approximation"),
            "multiplier_definition": "alpha = club xG/game / league mean xG/game; delta = club xGA/game / league mean xGA/game",
            "kappa_cap": CAP,
            "ridge_lambda": LAMBDA_RIDGE,
            "ridge_targets_log_centred": {k: round(v, 6) for k, v in targets.items()},
            "uefa_coefficients_4season_2223_2526": UEFA_4SEASON,
            "uefa_source": ("Wikipedia 'UEFA coefficient' current ranking table (as of 2026-10-22), "
                            "per-season columns 2022-23..2025-26 summed (4 completed seasons matching the data window)"),
        },
        "n_matches_fit": len(obs),
        "n_matches_skipped_unmapped": skipped,
        "fallback_multiplier_clubs": fallback,
    }

    # main fit
    f = Fit(obs, targets, LAMBDA_RIDGE)
    theta, se, nll, iters = f.run()
    kappas = {g: theta[4 + i] for i, g in enumerate(GROUPS)}
    kappa_se = {g: se[4 + i] for i, g in enumerate(GROUPS)}
    out["kappa"] = {g: round(kappas[g], 6) for g in GROUPS}
    out["kappa_se"] = {g: round(kappa_se[g], 6) for g in GROUPS}
    out["kappa_cap_binding"] = {g: bool(abs(kappas[g]) >= CAP - 1e-9) for g in GROUPS}
    out["neg_log_likelihood_penalized"] = round(nll, 4)
    out["newton_iters"] = iters
    out["convergence_max_free_grad"] = f.free_grad_final
    out["base_rates"] = {
        "UCL_home_goals_per_match": round(math.exp(theta[0]), 4),
        "UCL_away_goals_per_match": round(math.exp(theta[1]), 4),
        "UEL_home_goals_per_match": round(math.exp(theta[2]), 4),
        "UEL_away_goals_per_match": round(math.exp(theta[3]), 4),
    }
    out["base_rates_se"] = {"UCL_home": round(se[0], 6), "UCL_away": round(se[1], 6),
                            "UEL_home": round(se[2], 6), "UEL_away": round(se[3], 6)}

    # empirical vs model diagnostics per competition
    diag = {}
    for comp in ["UCL", "UEL"]:
        sub = [o for o in obs if o["comp"] == comp]
        gh = sum(o["y_h"] for o in sub) / len(sub)
        ga = sum(o["y_a"] for o in sub) / len(sub)
        mh = sum(math.exp(theta[0 if comp == "UCL" else 2] + o["lc_h"] + kappas[o["lg_h"]] - kappas[o["lg_a"]]) for o in sub) / len(sub)
        ma = sum(math.exp(theta[1 if comp == "UCL" else 3] + o["lc_a"] + kappas[o["lg_a"]] - kappas[o["lg_h"]]) for o in sub) / len(sub)
        diag[comp] = {"n": len(sub), "emp_home_gpm": round(gh, 4), "emp_away_gpm": round(ga, 4),
                      "model_home_gpm": round(mh, 4), "model_away_gpm": round(ma, 4)}
    out["diagnostics_by_comp"] = diag

    counts = {}
    for o in obs:
        counts[o["lg_h"] + "|home"] = counts.get(o["lg_h"] + "|home", 0) + 1
        counts[o["lg_a"] + "|away"] = counts.get(o["lg_a"] + "|away", 0) + 1
    out["league_appearances"] = counts

    # G-B: Spearman over Big-5 kappa vs UEFA coef
    kx = [kappas[lg] for lg in BIG5]
    uy = [UEFA_4SEASON[lg] for lg in BIG5]
    rho = spearman(kx, uy)
    out["gate_B"] = {
        "spearman_kappa_vs_uefa_big5": round(rho, 4),
        "threshold": 0.8,
        "passed": bool(rho >= 0.8),
        "kappa_ranking": [g for g, _ in sorted(zip(GROUPS, kx), key=lambda t: -t[1])],
        "uefa_ranking": [g for g, _ in sorted(zip(BIG5, uy), key=lambda t: -t[1])],
    }

    # sensitivities
    sens = {}
    for name, sel, lam in [
        ("big5_cross_only", [o for o in obs if o["big5_big5"]], LAMBDA_RIDGE),
        ("ridge_lambda_5", obs, 5.0),
        ("ridge_lambda_50", obs, 50.0),
    ]:
        if len(sel) < 30:
            continue
        groups_present = [g for g in GROUPS if any(o["lg_h"] == g or o["lg_a"] == g for o in sel)]
        f2 = Fit(sel, targets, lam, groups=groups_present)
        th2, se2, nll2, _ = f2.run()
        k2 = {g: th2[4 + i] for i, g in enumerate(groups_present)}
        rho2 = spearman([k2[lg] for lg in BIG5 if lg in k2], [UEFA_4SEASON[lg] for lg in BIG5 if lg in k2])
        sens[name] = {"n": len(sel), "kappa": {g: round(k2[g], 6) for g in groups_present},
                      "kappa_se": {g: round(se2[4 + i], 6) for i, g in enumerate(groups_present)},
                      "spearman": round(rho2, 4)}
    out["sensitivity"] = sens

    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({k: out[k] for k in ["n_matches_fit", "kappa", "kappa_se", "kappa_cap_binding",
                                          "base_rates", "gate_B"]}, indent=1))
    print("WROTE", OUT)


if __name__ == "__main__":
    main()
