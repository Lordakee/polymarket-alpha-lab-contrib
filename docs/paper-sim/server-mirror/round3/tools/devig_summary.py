import json, math

def am_prob(o):
    o = int(o)
    return (-o / (-o + 100)) if o < 0 else (100.0 / (100 + o))

def pois_cdf(lam, k):
    s = 0.0
    for i in range(k + 1):
        s += math.exp(-lam) * lam ** i / math.factorial(i)
    return s

def lam_for_over(line, p):  # line = 2.5 -> P(total >= 3); 3.5 -> >=4; 4.5 -> >=5
    lo, hi = 0.5, 12.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if (1 - pois_cdf(mid, int(line))) < p: lo = mid
        else: hi = mid
    return (lo + hi) / 2

DK = json.load(open("/home/ubuntu/paper-sim/round3/raw/dk_odds.json"))
OUT = {}
for eid, r in DK.items():
    tag = "%s|%s" % (r["home"], r["away"])
    if not any(k in tag for k in ["Atl", "Arsenal", "Internazionale", "Galatasaray"]): continue
    pO = am_prob(r["over_close_odds"]); pU = am_prob(r["under_close_odds"])
    s = pO + pU
    devig = pO / s
    line = float(r["total_line"])
    lam = lam_for_over(line, devig)
    p_o25 = 1 - pois_cdf(lam, 2)
    OUT[tag] = {"dk_line": line, "devig_over": round(devig, 4), "poisson_lambda": round(lam, 3), "implied_O25": round(p_o25, 4),
                "over_open": r["over_close_odds"], "over_open_line": r.get("over_open", {}).get("line")}
    print("%-38s DK line %.1f devig P(>%.1f)=%.3f -> lam=%.2f -> P(O2.5)=%.3f [open %s]" % (
        tag, line, line, devig, lam, p_o25, r.get("over_open", {}).get("line")))

# MD1 league-phase anchor
MD1 = [("AEK",1,0),("Brugge",2,3),("Dortmund",3,1),("Porto",0,2),("Lille",2,3),("RMA",2,1),
       ("Barca",5,1),("Stuttgart",3,1),("Liverpool",0,1),("PSG",6,1),("Sporting",3,1),("Napoli",0,1),
       ("Fener",1,1),("PSV",1,1),("Como",4,1),("Bayern",5,0),("ManUtd",4,0),("Slavia",2,3)]
g = [a + b for _, a, b in MD1]
print()
print("UCL MD1: n=%d goals=%d gpg=%.3f over2.5=%d/%d=%.3f" % (len(g), sum(g), sum(g)/len(g), sum(1 for x in g if x >= 3), len(g), sum(1 for x in g if x >= 3)/len(g)))
json.dump(OUT, open("/home/ubuntu/paper-sim/round3/raw/dk_devig.json", "w"), indent=1)
print("saved dk_devig.json")
