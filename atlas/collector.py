"""ATLAS 定时研究快照（仅公开日线；不代表实时资金净流入）。"""
import json
import math
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

import pandas as pd
import yfinance as yf

BASE = Path(__file__).resolve().parent
OUT = BASE / "data" / "overview.json"
MARKETS = [
    ("^GSPC", "标普500", "美国", "美洲", "USD", "US"),
    ("^IXIC", "纳斯达克综合", "美国", "美洲", "USD", "US"),
    ("^DJI", "道琼斯", "美国", "美洲", "USD", "US"),
    ("000001.SS", "上证指数", "中国A股", "亚洲", "CNY", "CN"),
    ("000300.SS", "沪深300", "中国A股", "亚洲", "CNY", "CN"),
    ("^HSI", "恒生指数", "中国香港", "亚洲", "HKD", "HK"),
    ("^HSTECH", "恒生科技", "中国香港", "亚洲", "HKD", "HK"),
    ("^N225", "日经225", "日本", "亚洲", "JPY", "JP"),
    ("^KS11", "韩国综合", "韩国", "亚洲", "KRW", "KR"),
    ("^TWII", "台湾加权", "中国台湾", "亚洲", "TWD", "TW"),
    ("^NSEI", "印度Nifty50", "印度", "亚洲", "INR", "IN"),
    ("^FTSE", "英国富时100", "英国", "欧洲", "GBP", "GB"),
    ("^GDAXI", "德国DAX", "德国", "欧洲", "EUR", "DE"),
    ("^FCHI", "法国CAC40", "法国", "欧洲", "EUR", "FR"),
    ("^AXJO", "澳洲ASX200", "澳大利亚", "亚太", "AUD", "AU"),
    ("^BVSP", "巴西Bovespa", "巴西", "美洲", "BRL", "BR"),
]
ETFS = [
    ("SPY", "美国大盘", "美股宽基"), ("QQQ", "美国科技", "成长科技"),
    ("SOXX", "美国半导体", "半导体"), ("FXI", "中国大盘ETF", "中概/港股代理"),
    ("EWJ", "日本股票ETF", "日本"), ("EEM", "新兴市场ETF", "新兴市场"),
    ("GLD", "黄金ETF", "避险资产"), ("TLT", "长期美债ETF", "利率敏感"),
]
PRIMARY = {"^GSPC","000300.SS","^HSI","^N225","^KS11","^NSEI","^GDAXI","^FTSE","^BVSP","^AXJO"}
NEWS = [
    ("全球宏观","global stock markets central banks inflation when:2d","en-US","US","US:en"),
    ("美股与科技","S&P 500 Nasdaq AI chips earnings when:2d","en-US","US","US:en"),
    ("中国市场","A股 沪深 股市 货币政策 when:2d","zh-CN","CN","CN:zh-Hans"),
    ("亚洲市场","Nikkei Hang Seng KOSPI markets when:2d","en-US","US","US:en"),
]

def num(x, places=2):
    try:
        x=float(x)
        return round(x, places) if math.isfinite(x) else None
    except (ValueError, TypeError):
        return None

def frame(raw, symbol):
    if raw is None or raw.empty:
        return pd.DataFrame()
    if not isinstance(raw.columns, pd.MultiIndex):
        return raw
    try:
        return raw[symbol]
    except (KeyError, TypeError):
        try:
            return raw.xs(symbol, axis=1, level=1)
        except (KeyError, TypeError):
            return pd.DataFrame()

def quote_row(df, symbol):
    if df.empty or "Close" not in df:
        return None
    prices=pd.to_numeric(df["Close"],errors="coerce").dropna()
    if len(prices)<22:
        return None
    last=float(prices.iloc[-1]); prev=float(prices.iloc[-2])
    ma20=float(prices.tail(20).mean())
    ma60=float(prices.tail(60).mean()) if len(prices)>=60 else None
    r20=(last/float(prices.iloc[-21])-1)*100
    r60=(last/float(prices.iloc[-61])-1)*100 if len(prices)>60 else None
    regime="震荡"
    if ma60 is not None and last>ma20>ma60 and r20>0: regime="上行"
    if ma60 is not None and last<ma20<ma60: regime="下行"
    changes=prices.pct_change(fill_method=None).dropna().tail(20)
    vol=num(changes.std()*math.sqrt(252)*100) if len(changes)>5 else None
    ratio=None
    if "Volume" in df:
        vols=pd.to_numeric(df["Volume"],errors="coerce").dropna()
        if len(vols)>=21:
            valid=vols.iloc[-21:-1]; valid=valid[valid>0]
            if len(valid)>=12 and valid.median()>0 and float(vols.iloc[-1])>0:
                ratio=num(float(vols.iloc[-1])/float(valid.median()))
    hist=[{"date":str(i)[:10],"close":num(v,3)} for i,v in prices.tail(100).items()]
    return dict(symbol=symbol,price=num(last,3),pct=num((last/prev-1)*100),ret20=num(r20),ret60=num(r60),
        ma20=num(ma20,3),ma60=num(ma60,3),volatility20=vol,volume_ratio=ratio,
        regime=regime,asof=hist[-1]["date"],history=hist,
        price_type="最近交易日收盘价，可能延迟，不是实时报价")

def download():
    symbols=[x[0] for x in MARKETS+ETFS]
    errors=[]
    quotes={}
    for group in [symbols[i:i+8] for i in range(0,len(symbols),8)]:
        try:
            raw=yf.download(tickers=group,period="7mo",interval="1d",auto_adjust=True,
                group_by="ticker",threads=True,progress=False,timeout=20)
            for sym in group:
                try:
                    item=quote_row(frame(raw,sym),sym)
                    if item: quotes[sym]=item
                except Exception as exc:
                    errors.append(f"{sym} 解析失败：{type(exc).__name__}")
        except Exception as exc:
            errors.append(f"行情采集暂不可用：{type(exc).__name__}")
    markets=[dict(quotes[sym],name=name,country=country,region=region,currency=currency,iso=iso)
             for sym,name,country,region,currency,iso in MARKETS if sym in quotes]
    etfs=[dict(quotes[sym],name=name,theme=theme)
          for sym,name,theme in ETFS if sym in quotes]
    if len(markets)<len(MARKETS):
        errors.append(f"{len(MARKETS)-len(markets)}个指数缺失，未填造数据")
    return markets,etfs,errors

def read_news():
    rows=[]; errors=[]
    for category,query,hl,gl,ceid in NEWS:
        try:
            uri=f"https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={ceid}"
            req=Request(uri,headers={"User-Agent":"Mozilla/5.0 ATLASResearch/1.0"})
            with urlopen(req,timeout=12) as r: root=ET.fromstring(r.read())
            for item in root.findall(".//item")[:8]:
                title=(item.findtext("title") or "").strip()
                link=(item.findtext("link") or "").strip()
                if not title or not link.startswith("https://"): continue
                source=item.find("source")
                rows.append(dict(title=title[:220],url=link,category=category,
                    published=(item.findtext("pubDate") or "").strip(),
                    source=source.text.strip() if source is not None and source.text else "Google 新闻聚合"))
        except Exception as exc:
            errors.append(f"{category} RSS 不可用：{type(exc).__name__}")
    return list({x["title"]:x for x in rows}.values())[:28],errors

def main():
    markets,etfs,merrors=download()
    news,nerrors=read_news()
    if not markets:
        print("WARNING: 未取得可靠指数行情，保留旧快照，绝不伪造。")
        if OUT.exists(): return
        raise SystemExit("首次采集失败，尚无真实快照；网页将提示未接通")
    sample=[x for x in markets if x["symbol"] in PRIMARY and x["ma60"] is not None]
    rising=sum(x["regime"]=="上行" for x in sample)
    falling=sum(x["regime"]=="下行" for x in sample)
    score=round(sum(80 if x["regime"]=="上行" else 20 if x["regime"]=="下行" else 50 for x in sample)/len(sample)) if sample else None
    market_summary=dict(score=score,regime="偏强" if score is not None and score>=65 else "偏弱" if score is not None and score<40 else "分化震荡" if score is not None else "数据不足",
        rising=rising,falling=falling,sample_size=len(sample),
        comment="10个主要市场等权价格趋势指标；非资金净流入、非预测胜率")
    data=dict(mode="live",collected_at=datetime.now(timezone.utc).isoformat(),
        timezone="Asia/Shanghai",price_source="Yahoo Finance / yfinance（非官方研究级日线；可能延迟）",
        news_source="Google News RSS（仅聚合标题，需核验）",
        markets=markets,etfs=etfs,news=news,market_summary=market_summary,
        coverage=dict(indices=len(markets),indices_total=len(MARKETS),etfs=len(etfs),etfs_total=len(ETFS),news=len(news)),
        errors=merrors+nerrors,stale=False,
        flow_notice="成交量与ETF交易活跃度不等于净申购、不表示真正机构资金净流入。")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(f"ATLAS 行情 {len(markets)}/{len(MARKETS)}，ETF {len(etfs)}，新闻 {len(news)}，采集 {data['collected_at']}")

if __name__=="__main__":
    main()
