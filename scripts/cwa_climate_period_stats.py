# -*- coding: utf-8 -*-
import sys, io, json, statistics as st
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
j=json.load(open("codis_467410_monthly_raw.json",encoding="utf-8"))
rec={}
for d in j["data"][0]["dts"]:
    ym=d["DataYearMonth"][:7]; y,m=int(ym[:4]),int(ym[5:7])
    at=d.get("AirTemperature") or {}; pr=d.get("Precipitation") or {}; sd=d.get("SunshineDuration") or {}
    rec[(y,m)]=dict(tmax=at.get("MeanDailyMaximum"),tmean=at.get("Mean"),tmin=at.get("MeanDailyMinimum"),
                    rain=pr.get("Accumulation"),sun=sd.get("Total"))
def series(y0,y1,k,m):
    return [rec[(y,m)][k] for y in range(y0,y1+1) if rec.get((y,m)) and rec[(y,m)][k] is not None]
def annual_rain(y0,y1):
    out=[]
    for y in range(y0,y1+1):
        vs=[rec[(y,m)]['rain'] for m in range(1,13) if rec.get((y,m)) and rec[(y,m)]['rain'] is not None]
        if len(vs)==12: out.append(sum(vs))
    return out
def annual_sun(y0,y1):
    out=[]
    for y in range(y0,y1+1):
        vs=[rec[(y,m)]['sun'] for m in range(1,13) if rec.get((y,m)) and rec[(y,m)]['sun'] is not None]
        if len(vs)==12: out.append(sum(vs))
    return out

def build(y0,y1):
    r={'tmax':[],'tmean':[],'tmin':[],'rain':[],'sun':[],'n':[]}
    for m in range(1,13):
        r['tmax'].append(round(st.mean(series(y0,y1,'tmax',m)),1))
        r['tmean'].append(round(st.mean(series(y0,y1,'tmean',m)),1))
        r['tmin'].append(round(st.mean(series(y0,y1,'tmin',m)),1))
        r['rain'].append(round(st.median(series(y0,y1,'rain',m)),1))
        r['sun'].append(round(st.mean(series(y0,y1,'sun',m)),1))
        r['n'].append(len(series(y0,y1,'tmean',m)))
    r['tmax_y']=round(st.mean(r['tmax']),1); r['tmean_y']=round(st.mean(r['tmean']),1)
    r['tmin_y']=round(st.mean(r['tmin']),1)
    r['rain_y']=round(st.median(annual_rain(y0,y1)),1)
    r['sun_y']=round(st.mean(annual_sun(y0,y1)),1)
    r['years']=len(annual_rain(y0,y1))
    return r

periods={'2016-2025':(2016,2025),'1991-2025':(1991,2025)}
res={k:build(*v) for k,v in periods.items()}
json.dump(res, open("new_table31.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
mon=[f"{m}月" for m in range(1,13)]
book={'tmax':[23.0,24.0,26.6,29.3,31.4,32.4,33.0,32.6,32.4,30.8,28.1,24.4],
      'tmean':[17.9,18.9,21.6,24.9,27.4,28.8,29.3,28.9,28.5,26.3,23.4,19.6],
      'tmin':[14.6,15.4,18.0,21.6,24.6,26.2,26.6,26.3,25.8,23.3,20.2,16.4],
      'rain':[12.2,9.7,14.0,52.9,132.8,278.5,388.6,315.9,90.2,4.5,6.6,7.7],
      'sun':[176.4,163.8,183.1,177.2,190.8,193.0,201.4,178.7,184.6,198.3,169.9,167.8]}
for key,label in [('tmax','最高溫度(°C)'),('tmean','平均溫度(°C)'),('tmin','最低溫度(°C)'),('rain','降水量(mm)'),('sun','日照時數(hr)')]:
    print(f"\n### {label}")
    print("期間        " + "".join(f"{x:>8}" for x in mon) + f"{'全年':>10}")
    print(f"{'原表91-20':<12}" + "".join(f"{v:>8}" for v in book[key]) + f"{'—':>10}")
    for p,r in res.items():
        yr = {'tmax':r['tmax_y'],'tmean':r['tmean_y'],'tmin':r['tmin_y'],'rain':r['rain_y'],'sun':r['sun_y']}[key]
        print(f"{p:<12}" + "".join(f"{v:>8}" for v in r[key]) + f"{yr:>10}")
print("\n完整年數:", {p:r['years'] for p,r in res.items()})
