"""Round-23 Serie A early sub-scan: 10-variant xG-Poisson for round-11 (Oct31-Nov2), paper-only.
Methodology identical to r15/r19-r22: blend sweeps w=.25/.5/1.0 p=4/8/16, DC rho=-0.1,
current-only, last-only, cross-shrink .8/1.1; median/min/max across variants.
xG base: round22/raw/xg_understat_22.json Serie_A 2025+2026 (88 played thru 2026-10-28)."""
import json, math, time
from collections import defaultdict

XG = json.load(open('/home/ubuntu/paper-sim/round22/raw/xg_understat_22.json'))
GAMMA = json.load(open('/home/ubuntu/paper-sim/round23/raw/gamma_sweep23.json'))
ESPN = json.load(open('/home/ubuntu/paper-sim/round23/raw/espn_ita1_r11.json'))
RHO_DC = -0.1

def load(lg, se): return XG['%s_%s' % (lg, se)]

_c = {}
def ratings_for(LASTW, PRIOR, mode):
    key = (LASTW, PRIOR, mode)
    if key in _c: return _c[key]
    d25 = load('Serie_A','2025'); d26 = load('Serie_A','2026')
    ms = [m for m in d25['dates'] if m.get('isResult')]
    bh = sum(float(m['xG']['h']) for m in ms)/len(ms)
    ba = sum(float(m['xG']['a']) for m in ms)/len(ms)
    lgf = (bh+ba)/2.0
    last = {}
    for t in d25['teams'].values():
        h = t['history']
        last[t['title']] = (sum(float(x['xG']) for x in h)/len(h), sum(float(x['xGA']) for x in h)/len(h))
    r = {}
    for t in d26['teams'].values():
        h = t['history']; name = t['title']
        if not h: continue
        cf = sum(float(x['xG']) for x in h)/len(h)
        ca = sum(float(x['xGA']) for x in h)/len(h)
        nc = len(h)
        if mode=='cur': f,a = cf,ca
        elif mode=='last': f,a = last.get(name,(lgf,lgf))
        else:
            lf,la_ = last.get(name,(lgf,lgf))
            f = (nc*cf + LASTW*38*lf + PRIOR*lgf)/(nc+LASTW*38+PRIOR)
            a = (nc*ca + LASTW*38*la_ + PRIOR*lgf)/(nc+LASTW*38+PRIOR)
        r[name] = (f/lgf, a/lgf)
    _c[key] = (bh, ba, lgf, r)
    return _c[key]

SWEEPS = [('blend w=.5 p=8 rho0',0.5,8,0.0,'blend'),('blend w=.5 p=8 DC',0.5,8,RHO_DC,'blend'),
 ('blend w=1.0 p=8',1.0,8,0.0,'blend'),('blend w=.25 p=8',0.25,8,0.0,'blend'),
 ('blend w=.5 p=16',0.5,16,0.0,'blend'),('blend w=.5 p=4',0.5,4,0.0,'blend'),
 ('current-only',None,None,0.0,'cur'),('last-only',None,None,0.0,'last'),
 ('cross-shrink .8',0.5,8,0.0,'blend'),('cross-shrink 1.1',0.5,8,0.0,'blend')]

def pois(l,k): return math.exp(-l)*l**k/math.factorial(k)

def gridf(lh,la,N=10,rho=0.0):
    g=[[pois(lh,i)*pois(la,j) for j in range(N+1)] for i in range(N+1)]
    if rho:
        g[0][0]*=max(1-lh*la*rho,.01); g[0][1]*=max(1+lh*rho,.01)
        g[1][0]*=max(1+la*rho,.01); g[1][1]*=max(1-rho,.01)
    s=sum(sum(r_) for r_ in g)
    return [[v/s for v in row] for row in g]

def variant_outputs(lh,la,rho):
    g=gridf(lh,la,10,rho)
    ph=sum(g[i][j] for i in range(11) for j in range(11) if i>j)
    pd=sum(g[i][i] for i in range(11)); pa=1.0-ph-pd
    tot=defaultdict(float); btts=0.0
    for i in range(11):
        for j in range(11):
            p=g[i][j]; tot[i+j]+=p
            if i>=1 and j>=1: btts+=p
    out={'H':ph,'D':pd,'A':pa,'btts':btts}
    for line in (0.5,1.5,2.5,3.5,4.5,5.5,6.5):
        out['o%.1f'%line]=sum(v for k,v in tot.items() if k>=line+0.5)
    for n in (1,2,3):
        out['h_ge%d'%n]=sum(g[i][j] for i in range(11) for j in range(11) if i>=n)
        out['a_ge%d'%n]=sum(g[i][j] for i in range(11) for j in range(11) if j>=n)
    for n in (2,3,4,5,6):
        out['h_cov%d'%n]=sum(g[i][j] for i in range(11) for j in range(11) if i-j>=n)
        out['a_cov%d'%n]=sum(g[i][j] for i in range(11) for j in range(11) if j-i>=n)
    return out

def lambdas(home,away,LASTW,PRIOR,mode,shrink=1.0):
    bh,ba,lgf,r = ratings_for(LASTW,PRIOR,mode)
    ah,dh = r.get(home,(1.0,1.0)); aa,da = r.get(away,(1.0,1.0))
    return bh*(ah**shrink)*(da**shrink), ba*(aa**shrink)*(dh**shrink)

def med(v):
    s=sorted(v); n=len(s)
    return s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2.0

G2U = {
 'Bologna FC 1909':'Bologna','AC Monza':'Monza','Udinese Calcio':'Udinese','AS Roma':'Roma',
 'AC Milan':'AC Milan','FC Internazionale Milano':'Inter','Como 1907':'Como','Venezia FC':'Venezia',
 'Frosinone Calcio':'Frosinone','Torino FC':'Torino','SS Lazio':'Lazio','Cagliari Calcio':'Cagliari',
 'US Lecce':'Lecce','Genoa CFC':'Genoa','Juventus FC':'Juventus','SSC Napoli':'Napoli',
 'US Sassuolo Calcio':'Sassuolo','ACF Fiorentina':'Fiorentina','Atalanta BC':'Atalanta',
 'Parma Calcio 1913':'Parma Calcio 1913'}

FIX = [
 ('Bologna FC 1909 vs. AC Monza','Bologna','Monza','2026-10-31T14:00:00Z','Bologna-Monza'),
 ('Udinese Calcio vs. AS Roma','Udinese','Roma','2026-10-31T17:00:00Z','Udinese-Roma'),
 ('AC Milan vs. FC Internazionale Milano','AC Milan','Inter','2026-10-31T19:45:00Z','DERBY Milan-Inter'),
 ('Como 1907 vs. Venezia FC','Como','Venezia','2026-11-01T11:30:00Z','Como-Venezia'),
 ('Frosinone Calcio vs. Torino FC','Frosinone','Torino','2026-11-01T14:00:00Z','Frosinone-Torino'),
 ('SS Lazio vs. Cagliari Calcio','Lazio','Cagliari','2026-11-01T14:00:00Z','Lazio-Cagliari'),
 ('US Lecce vs. Genoa CFC','Lecce','Genoa','2026-11-01T17:00:00Z','Lecce-Genoa'),
 ('Juventus FC vs. SSC Napoli','Juventus','Napoli','2026-11-01T19:45:00Z','Juventus-Napoli'),
 ('US Sassuolo Calcio vs. ACF Fiorentina','Sassuolo','Fiorentina','2026-11-02T17:30:00Z','Sassuolo-Fiorentina'),
 ('Atalanta BC vs. Parma Calcio 1913','Atalanta','Parma Calcio 1913','2026-11-02T19:45:00Z','Atalanta-Parma')]

MM = {}
for e in GAMMA['sea']:
    if e['title'].endswith(' - More Markets'):
        MM[e['title'][:-len(' - More Markets')]] = e

out_matches = []
for base,uhome,uaway,ko,label in FIX:
    ev = MM.get(base)
    per=[]
    for name,LASTW,PRIOR,rho,mode in SWEEPS:
        shrink = 0.8 if name.startswith('cross-shrink .8') else (1.1 if name.startswith('cross-shrink 1.1') else 1.0)
        lh,la = lambdas(uhome,uaway,LASTW,PRIOR,mode,shrink)
        per.append({'name':name,'lh':round(lh,3),'la':round(la,3),
                    'o':{k:round(v,4) for k,v in variant_outputs(lh,la,rho).items()}})
    def vs(k): return [v['o'][k] for v in per]
    def agg(k): return {'med':round(med(vs(k)),4),'min':round(min(vs(k)),4),'max':round(max(vs(k)),4)}
    fair={}
    for k in ['H','D','A','btts','o0.5','o1.5','o2.5','o3.5','o4.5','o5.5','o6.5',
              'h_ge1','h_ge2','h_ge3','a_ge1','a_ge2','a_ge3',
              'h_cov2','h_cov3','h_cov4','h_cov5','h_cov6','a_cov2','a_cov3','a_cov4','a_cov5','a_cov6']:
        fair[k]=agg(k)
    d26=load('Serie_A','2026')
    def form5(team):
        rows=[]
        for m in d26['dates']:
            if not m.get('isResult'): continue
            if m['h']['title']==team: rows.append((int(m['goals']['h']),int(m['goals']['a']),float(m['xG']['h']),float(m['xG']['a'])))
            elif m['a']['title']==team: rows.append((int(m['goals']['a']),int(m['goals']['h']),float(m['xG']['a']),float(m['xG']['h'])))
        rows=rows[-5:]
        return {'gp':len(rows),'gf':sum(r[0] for r in rows),'ga':sum(r[1] for r in rows),
                'xg_for':round(sum(r[2] for r in rows),2),'xg_ag':round(sum(r[3] for r in rows),2),
                'o25_team_hits':sum(1 for r in rows if r[0]+r[1]>=3),'btts_hits':sum(1 for r in rows if r[0]>=1 and r[1]>=1)}
    rec={'match':base,'label':label,'kickoff_utc':ko,'gamma_event_id':ev['id'] if ev else None,
         'lambda_home':round(med([v['lh'] for v in per]),3),'lambda_away':round(med([v['la'] for v in per]),3),
         'lambda_total':round(med([v['lh']+v['la'] for v in per]),3),
         'form_home':form5(uhome),'form_away':form5(uaway),
         'p1x2_med':{'H':fair['H']['med'],'D':fair['D']['med'],'A':fair['A']['med']},
         'fair':fair,'markets':{}}
    if ev:
        gh = base.split(' vs. ')[0]; ga = base.split(' vs. ')[1]
        for m in ev['markets']:
            q=m['q']; kind=None; key=None
            if q==base+': Both Teams to Score': kind='btts'; key='btts'
            elif q.startswith(base+': O/U '):
                line=float(q.split('O/U ')[1]); kind='total'; key='o%.1f'%line
            elif q.startswith(base+': '+gh+' O/U '):
                line=float(q.split('O/U ')[1]); kind='team_total_home'; key='h_ge%d'%int(line+0.5)
            elif q.startswith(base+': '+ga+' O/U '):
                line=float(q.split('O/U ')[1]); kind='team_total_away'; key='a_ge%d'%int(line+0.5)
            elif q.startswith('Spread: '+gh+' (-'):
                line=float(q.split('(-')[1].rstrip(')')); kind='spread_home'; key='h_cov%d'%int(line+0.5)
            elif q.startswith('Spread: '+ga+' (-'):
                line=float(q.split('(-')[1].rstrip(')')); kind='spread_away'; key='a_cov%d'%int(line+0.5)
            else: continue
            if key not in fair: continue
            rec['markets'][q]={'kind':kind,'key':key,'id':m['id'],'outcomes':m['outcomes'],
                'prices':m['prices'],'liq':m['liq'],'vol24':m['vol24'],
                'bestBid':m['bestBid'],'bestAsk':m['bestAsk'],'tokens':m['tokens'],
                'p0_med':fair[key]['med'],'p0_min':fair[key]['min'],'p0_max':fair[key]['max'],
                'var_spread':round(fair[key]['max']-fair[key]['min'],4)}
    out_matches.append(rec)

res={'generated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
     'scan':'seriea-r23-early','round':23,'seriea_round':11,'paper_only':True,
     'window_utc':{'lo':'2026-10-31T00:00:00Z','hi':'2026-11-03T00:00:00Z'},
     'xg_base':'round22/raw/xg_understat_22.json Serie_A 2025+2026, 88 matches thru 2026-10-28 (Monza-Napoli); file contains Serie A only (other leagues owned by their own sub-scans)',
     'method':'10-variant xG-Poisson (r15/r19-r22): blend w=.25/.5/1.0 p=4/8/16, DC rho=-0.1, current-only, last-only, cross-shrink .8/1.1; median/min/max',
     'matches':out_matches}
json.dump(res, open('/home/ubuntu/paper-sim/round23/raw/seriea_model23.json','w'), indent=1)
for r in out_matches:
    f=r['fair']
    print('%-22s lam %.2f-%2.2f (tot %.2f) | H %.2f D %.2f A %.2f | O2.5 %.3f BTTS %.3f | mks %d' % (
        r['label'], r['lambda_home'], r['lambda_away'], r['lambda_total'],
        f['H']['med'], f['D']['med'], f['A']['med'], f['o2.5']['med'], f['btts']['med'], len(r['markets'])))
print('saved seriea_model23.json')
