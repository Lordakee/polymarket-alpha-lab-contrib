import json
RAW='/home/ubuntu/paper-sim/round5/raw'
RES=json.load(open(RAW+'/model_round5d.json'))
M=RES['report']['BOU-SUN']['markets']
# restore true -2.5 row from fresh-run values (cov_ask 0.09 / fail 0.93, model [0.1439,0.1561,0.1877])
M['SPREAD_H_m2.5']={'mid':M['SPREAD_H_m2.5']['mid'],'team':'AFC Bournemouth','line':-2.5,
  'model':[0.1439,0.1561,0.1877],'cover_ask':0.09,'cover_vwap':0.09,'fail_ask':0.93,'fail_vwap':0.93,
  'edge_cover':0.0539,'edge_fail':-0.1177,'flag':'COVER','liq':201838.8839,'note':'-3.5/-4.5/-5.5 lines also flagged by >=3 model by key collision; not separately modeled (P(>=4) not computed); ignored'}
seen=[]; fl=[]
for f in RES['flags']:
    t=tuple(f)
    if t not in seen: seen.append(t)
fl=[list(t) for t in seen if not (t[0]=='BOU-SUN' and t[1]=='SPREAD_H_m2.5')] 
fl.append(['BOU-SUN','SPREAD_H_m2.5','COVER'])
RES['flags']=fl
json.dump(RES,open(RAW+'/model_round5d.json','w'),indent=1)
print('FINAL FLAGS:',fl)
