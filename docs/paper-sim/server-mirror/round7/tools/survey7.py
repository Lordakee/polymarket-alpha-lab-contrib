import json, datetime, re

res = json.load(open('/home/ubuntu/paper-sim/round7/raw/discover7.json'))

def gmt(e):
    for m in e.get('markets') or []:
        if m.get('gameStartTime'): return m['gameStartTime']
    return None

def league(e):
    s = e.get('slug') or ''
    m = re.match(r'^([a-z0-9]+)-[a-z]+-[a-z]+-2026', s)
    if m: return m.group(1)
    return s.split('-')[0]

# ---- SOCCER ----
print('#'*20, 'SOCCER fixtures Oct20-22 (liq>=25k)')
for e in sorted(res.get('soccer',[]), key=lambda x:-(x.get('liquidityNum') or 0)):
    liq = e.get('liquidity') or 0
    g = gmt(e)
    if not g: continue
    if not ('2026-10-20' in g or '2026-10-21' in g or '2026-10-22' in g): continue
    if liq < 25000: continue
    mk = e.get('markets') or []
    print('%-8s %-46s liq=%8d gs=%s mkts=%d' % (league(e), str(e.get('title'))[:46], liq, g[11:16], len(mk)))

# ---- CRYPTO ----
print('#'*20, 'CRYPTO events (liq>=20k, ETH/BTC in title or Q)')
seen=set()
for tag in ['crypto','eth','btc']:
    for e in sorted(res.get(tag,[]), key=lambda x:-(x.get('liquidityNum') or 0)):
        liq = e.get('liquidity') or 0
        t = str(e.get('title') or ''); slug=e.get('slug') or ''
        if slug in seen: continue
        blob = (t + ' ' + slug).lower()
        if not any(k in blob for k in ['eth','bitcoin','btc']): continue
        end = str(e.get('endDate'))[:16]
        # keep near-dated (resolve within ~35d) or big
        if liq < 20000: continue
        if not any(k in blob for k in ['eth','bitcoin','btc']): continue
        seen.add(slug)
        print('%-55s liq=%8d end=%s vol24=%7d' % (t[:55], liq, end, e.get('volume24hr') or 0))

# ---- NBA ----
print('#'*20, 'NBA')
for e in sorted(res.get('nba',[]), key=lambda x:-(x.get('liquidityNum') or 0)):
    liq = e.get('liquidity') or 0
    g = gmt(e) or ''
    print('%-55s liq=%8d end=%s gs=%s' % (str(e.get('title'))[:55], liq, str(e.get('endDate'))[:16], g[5:16]))

# ---- NFL ----
print('#'*20, 'NFL')
for e in sorted(res.get('nfl',[]), key=lambda x:-(x.get('liquidityNum') or 0)):
    liq = e.get('liquidity') or 0
    g = gmt(e) or ''
    if liq < 15000: continue
    print('%-55s liq=%8d end=%s gs=%s' % (str(e.get('title'))[:55], liq, str(e.get('endDate'))[:16], g[5:16]))

# ---- FED / ECON ----
print('#'*20, 'FED/ECON')
for tag in ['fed','econ']:
    for e in sorted(res.get(tag,[]), key=lambda x:-(x.get('liquidityNum') or 0)):
        liq = e.get('liquidity') or 0
        print('%-60s liq=%8d end=%s' % (str(e.get('title'))[:60], liq, str(e.get('endDate'))[:16]))

# ---- POLITICS top ----
print('#'*20, 'POLITICS (liq>=100k)')
for e in sorted(res.get('politics',[]), key=lambda x:-(x.get('liquidityNum') or 0)):
    liq = e.get('liquidity') or 0
    if liq < 100000: continue
    print('%-60s liq=%9d end=%s' % (str(e.get('title'))[:60], liq, str(e.get('endDate'))[:16]))

# ---- MLB / UFC / NHL ----
for tag, minliq in [('mlb',10000),('ufc',10000),('nhl',25000)]:
    print('#'*20, tag.upper())
    for e in sorted(res.get(tag,[]), key=lambda x:-(x.get('liquidityNum') or 0)):
        liq = e.get('liquidity') or 0
        if liq < minliq: continue
        print('%-55s liq=%8d end=%s' % (str(e.get('title'))[:55], liq, str(e.get('endDate'))[:16]))
