#!/usr/bin/env python3
"""只使用公开ETF份额与行情；绝不推断真实国家队交易。"""
import json, math, sys
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parent
DEST=ROOT/"data"/"dashboard.json"
WATCH=[
("510300","华泰柏瑞沪深300ETF","沪深300"),("510310","易方达沪深300ETF","沪深300"),("510330","华夏沪深300ETF","沪深300"),("159919","嘉实沪深300ETF","沪深300"),("510050","华夏上证50ETF","上证50"),("510100","易方达上证50ETF","上证50"),("510500","南方中证500ETF","中证500"),("512500","华夏中证500ETF","中证500"),("159922","嘉实中证500ETF","中证500"),("512100","南方中证1000ETF","中证1000"),("159845","华夏中证1000ETF","中证1000"),("588000","华夏科创50ETF","科创50"),("588080","易方达科创50ETF","科创50"),("159915","易方达创业板ETF","创业板"),("159949","华安创业板50ETF","创业板")]
def num(v):
 try:
  z=float(v)
  return z if math.isfinite(z) else None
 except (TypeError,ValueError):return None
def day(v):
 s=str(v)[:10]
 if len(s)==8 and s.isdigit():return f"{s[:4]}-{s[4:6]}-{s[6:]}"
 return s
def main():
 import akshare as ak
 now=datetime.now(ZoneInfo("Asia/Shanghai"))
 old={}
 try:old=json.loads(DEST.read_text(encoding="utf8"))
 except (OSError,ValueError):pass
 prev={x["code"]:x for x in old.get("funds",[])}
 errors=[];quotes={};shares={}
 try:
  df=ak.fund_etf_spot_em()
  for _,r in df.iterrows():
   code=str(r.get("代码","")).zfill(6)
   if code in {x[0] for x in WATCH}:
    quotes[code]={"price":num(r.get("最新价"))}
 except Exception as e:errors.append("行情获取失败: "+str(e)[:180])
 # SSE 官方公开份额，AKShare接口单位为万份，转换为亿份
 for i in range(7):
  d=(now-timedelta(days=i+1)).date()
  if d.weekday()>=5:continue
  try:
   df=ak.fund_etf_scale_sse(date=d.strftime("%Y%m%d"))
   for _,r in df.iterrows():
    code=str(r.get("基金代码","")).replace(".0","").zfill(6)
    if code in {x[0] for x in WATCH}:
     val=num(r.get("基金份额"))
     if val and val>0:shares.setdefault(code,{})[day(r.get("统计日期") or d.strftime("%Y%m%d"))]=val/10000
  except Exception as e: errors.append("上交所"+str(d)+": "+str(e)[:100])
 # SZSE public historic shares, unit raw shares; failure must not become zero
 try:
  df=ak.fund_scale_daily_szse(start_date=(now-timedelta(days=14)).strftime("%Y%m%d"),end_date=now.strftime("%Y%m%d"),symbol="ETF")
  for _,r in df.iterrows():
   code=str(r.get("基金代码","")).replace(".0","").zfill(6)
   if code in {x[0] for x in WATCH}:
    val=num(r.get("基金份额"))
    if val and val>0:shares.setdefault(code,{})[day(r.get("日期"))]=val/1e8
 except Exception as e:errors.append("深交所份额获取失败: "+str(e)[:180])
 funds=[]
 for code,name,cat in WATCH:
  previous=prev.get(code,{})
  hist={h["date"]:h["shares_100m"] for h in previous.get("history",[]) if h.get("date") and num(h.get("shares_100m"))}
  hist.update(shares.get(code,{}))
  history=[{"date":d,"shares_100m":round(v,6)} for d,v in sorted(hist.items())][-120:]
  latest=history[-1] if history else None
  change=history[-1]["shares_100m"]-history[-2]["shares_100m"] if len(history)>=2 else None
  price=quotes.get(code,{}).get("price")
  funds.append({"code":code,"name":name,"category":cat,"price":price,"shares_100m":latest["shares_100m"] if latest else None,"shares_change_100m":round(change,5) if change is not None else None,"flow_est_100m":round(change*price,4) if change is not None and price else None,"share_date":latest["date"] if latest else None,"history":history})
 DEST.parent.mkdir(parents=True,exist_ok=True)
 payload={"status":"ok" if any(x["shares_100m"] is not None for x in funds) else "partial","collected_at":now.isoformat(timespec="seconds"),"errors":errors,"funds":funds,"disclaimer":"ETF份额变化不等于国家队交易"}
 DEST.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf8")
 print("采集完成，具有份额数据ETF：",sum(x["shares_100m"] is not None for x in funds),"错误数量：",len(errors))
 for err in errors[:4]:print(err,file=sys.stderr)
if __name__=="__main__":main()
