import json, urllib.request, urllib.parse, time, sys

BASE='https://gamma-api.polymarket.com'
def get(url, tries=3):
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if i==tries-1: raise
            time.sleep(2)

slugs=json.load(open('/home/ubuntu/paper-sim/round4/raw/slug_map.json'))
extra={
 'ufc_fn_blanchfield':'ufc-fight-night-erin-blanchfield-vs-jasmine-jasudavicius',
 'ufc333_merab':'ufc-333-merab-dvalishvili-vs-petr-yan',
 'ufc_fn_malott':'ufc-fight-night-mike-malott-vs-joaquin-buckley',
 'cpi_annual':'september-inflation-us-annual',
 'cpi_monthly':'september-inflation-us-monthly',
 'core_cpi_mom':'core-cpi-mom-september-2026',
 'core_cpi_yoy':'core-cpi-yoy-september-2026',
 'ppi_yoy':'ppi-yoy-september-2026',
 'fed_oct':'fed-decision-in-october-20260617190323537',
 'fed_dec':'fed-decision-in-december-20260729232808632',
 'fed_jan':'fed-decision-in-january-20260729233815502',
 'fed_path_sepdec':'fed-decisions-sepdec',
 'fed_eoy':'what-will-the-fed-rate-be-at-the-end-of-2026',
 'fed_cutcount':'how-many-fed-rate-cuts-in-2026',
 'fed_hikecount':'how-many-fed-rate-hikes-in-2026',
 'fed_another_hike':'another-fed-rate-hike-in-2026',
 'french_advance':'who-will-advance-to-the-second-round-of-the-next-french-presidential-election',
 'brazil_runoff_amapa':'brazil-presidential-election-second-round-1st-place-in-amapa',
 'spx_dec':'spx-hit-dec-2026',
 'oil_oct':'what-will-wti-crude-oil-wti-hit-in-october-2026',
}
allmap=dict(slugs)
allmap.update(extra)
out={}
for name,slug in allmap.items():
    try:
        ev=get(BASE+'/events?slug='+urllib.parse.quote(slug))
        if ev: out[name]={'slug':slug,'event':ev[0]}
        print('OK ',name,slug if not ev else '', flush=True)
    except Exception as e:
        print('ERR',name,slug,e, flush=True)
    time.sleep(0.6)
json.dump(out, open('/home/ubuntu/paper-sim/round4/raw/events_detail.json','w'))
print('saved',len(out))
