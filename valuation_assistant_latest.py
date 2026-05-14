#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
估值助手 Latest - 最终版
- 港股杠杆ETF：close 和 rt 都使用 gtimg 数据，收盘估值也能显示波动
- 计算方式：按列出持仓权重归一化 + 乘以 0.8（现金缓冲）
"""

import streamlit as st
import yfinance as yf
import requests
from datetime import datetime
import warnings
from zoneinfo import ZoneInfo

warnings.filterwarnings("ignore")

# ==================== 持仓数据（原始中文） ====================
FUND_HOLDINGS = {
    "易方达全球成长精选混合(QDII)C": {
        "short_name": "易方达全球成长精选",
        "holdings": [
            {"ticker": "TSM",    "name": "台积电",     "weight": 8.88, "market": "US"},
            {"ticker": "LITE",   "name": "Lumentum",  "weight": 8.68, "market": "US"},
            {"ticker": "300502", "name": "新易盛",     "weight": 6.02, "market": "A"},
            {"ticker": "GLW",    "name": "康宁",       "weight": 4.67, "market": "US"},
            {"ticker": "AXTI",   "name": "AXT Inc",   "weight": 4.67, "market": "US"},
            {"ticker": "300308", "name": "中际旭创",   "weight": 4.67, "market": "A"},
            {"ticker": "688498", "name": "源杰科技",   "weight": 4.49, "market": "A"},
            {"ticker": "TSEM",   "name": "Tower半导体","weight": 3.72, "market": "US"},
            {"ticker": "GOOGL",  "name": "谷歌",       "weight": 3.36, "market": "US"},
            {"ticker": "002384", "name": "东山精密",   "weight": 2.67, "market": "A"},
        ],
    },
    "天弘全球高端制造混合(QDII)C": {
        "short_name": "天弘全球高端制造",
        "holdings": [
            {"ticker": "NVDA",   "name": "英伟达",    "weight": 3.65, "market": "US"},
            {"ticker": "AVGO",   "name": "博通",      "weight": 3.07, "market": "US"},
            {"ticker": "TSM",    "name": "台积电",    "weight": 2.77, "market": "US"},
            {"ticker": "TSEM",   "name": "Tower半导体", "weight": 2.75, "market": "US"},
            {"ticker": "LITE",   "name": "Lumentum",  "weight": 2.69, "market": "US"},
            {"ticker": "300308", "name": "中际旭创",  "weight": 2.44, "market": "A"},
            {"ticker": "COHR",   "name": "Coherent",  "weight": 2.28, "market": "US"},
            {"ticker": "300502", "name": "新易盛",    "weight": 2.23, "market": "A"},
            {"ticker": "300476", "name": "胜宏科技",  "weight": 2.21, "market": "A"},
            {"ticker": "3684",   "name": "Nitto Boseki", "weight": 2.04, "market": "JP"},
            {"ticker": "07747",  "name": "南方两倍做多三星", "weight": 4.04, "market": "HK"},
            {"ticker": "07709",  "name": "南方两倍做多海力士", "weight": 3.68, "market": "HK"},
        ],
    },
    "建信新兴市场优选混合(QDII)C": {
        "short_name": "建信新兴市场优选",
        "holdings": [
            {"ticker": "TSM",    "name": "台积电",    "weight": 10.26, "market": "US"},
            {"ticker": "NVDA",   "name": "英伟达",    "weight": 10.14, "market": "US"},
            {"ticker": "000660", "name": "SK海力士",  "weight":  8.65, "market": "KR"},
            {"ticker": "005930", "name": "三星电子",  "weight":  6.76, "market": "KR"},
            {"ticker": "AVGO",   "name": "博通",       "weight": 8.52, "market": "US"},
            {"ticker": "SNDK",   "name": "闪迪",      "weight": 4.91, "market": "US"},
            {"ticker": "GLW",    "name": "康宁",      "weight":  4.29, "market": "US"},
            {"ticker": "WDC",    "name": "西部数据",  "weight":  3.73, "market": "US"},
            {"ticker": "LITE",   "name": "Lumentum", "weight":  3.58, "market": "US"},
            {"ticker": "MPWR",   "name": "Monolithic Power", "weight": 3.49, "market": "US"},
        ],
    },
    "嘉实全球产业升级股票(QDII)C": {
        "short_name": "嘉实全球产业升级",
        "holdings": [
            {"ticker": "AVGO",   "name": "博通",       "weight": 5.37, "market": "US"},
            {"ticker": "MU",     "name": "美光",       "weight": 4.85, "market": "US"},
            {"ticker": "MRVL",   "name": "迈威尔",     "weight": 4.37, "market": "US"},
            {"ticker": "688498", "name": "源杰科技",   "weight": 4.25, "market": "A"},
            {"ticker": "NVDA",   "name": "英伟达",     "weight": 3.79, "market": "US"},
            {"ticker": "ASML",   "name": "阿斯麦",     "weight": 3.70, "market": "US"},
            {"ticker": "688256", "name": "寒武纪",     "weight": 3.66, "market": "A"},
            {"ticker": "KLAC",   "name": "科磊",       "weight": 3.44, "market": "US"},
            {"ticker": "TSM",    "name": "台积电",     "weight": 3.39, "market": "US"},
            {"ticker": "AMD",    "name": "超威半导体",  "weight": 3.33, "market": "US"},
        ],
    },
}


# ==================== 价格获取函数 ====================
@st.cache_data(ttl=15)
def get_a_prices(symbol: str):
    try:
        code = "sh" + symbol if symbol[0] in "69" else "sz" + symbol
        r = requests.get(f"https://qt.gtimg.cn/q={code}", timeout=5)
        r.encoding = "gbk"
        arr = r.text.split('"')[1].split("~")
        realtime = float(arr[3])
        prev1_close = float(arr[4])
        if prev1_close <= 0:
            return None, None, None
        sina_url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={code}&scale=240&ma=5&datalen=3"
        sr = requests.get(sina_url, timeout=5)
        import json
        klines = json.loads(sr.text)
        if len(klines) < 2:
            return None, None, None
        prev2_close = float(klines[-2]["close"])
        return prev2_close, prev1_close, realtime if realtime > 0 else prev1_close
    except:
        return None, None, None


_yahoo_cache = {"session": None, "ts": 0}

def _yahoo_session():
    import time
    now = time.time()
    if _yahoo_cache["session"] and now - _yahoo_cache["ts"] < 1800:
        return _yahoo_cache["session"]
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    _yahoo_cache.update({"session": s, "ts": now})
    return s


@st.cache_data(ttl=15)
def get_us_prices(symbol: str):
    s = _yahoo_session()
    try:
        day_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
        dr = s.get(day_url, timeout=8)
        day_closes = [c for c in dr.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
        prev2_close = float(day_closes[-2])
        prev1_close = float(day_closes[-1])
        rt_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d&includePrePost=true"
        rr = s.get(rt_url, timeout=8)
        meta = rr.json()["chart"]["result"][0]["meta"]
        realtime = meta.get("postMarketPrice") or meta.get("preMarketPrice") or meta.get("regularMarketPrice") or prev1_close
        return prev2_close, prev1_close, float(realtime)
    except:
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="10d")
            return float(hist["Close"].iloc[-2]), float(hist["Close"].iloc[-1]), float(hist["Close"].iloc[-1])
        except:
            return None, None, None


@st.cache_data(ttl=15)
def get_asia_prices(symbol: str):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="10d")
        if len(hist) < 3:
            return None, None, None
        return float(hist["Close"].iloc[-3]), float(hist["Close"].iloc[-2]), float(hist["Close"].iloc[-1])
    except:
        return None, None, None


@st.cache_data(ttl=15)
def get_hk_prices(symbol: str):
    """稳定 gtimg：实时正常，close 也使用同一数据源"""
    try:
        code = "hk" + str(symbol).zfill(5)
        r = requests.get(f"https://qt.gtimg.cn/q={code}", timeout=5)
        r.encoding = "gbk"
        arr = r.text.split('"')[1].split("~")
        realtime = float(arr[3]) if arr[3] else 0
        prev_close = float(arr[4]) if arr[4] else 0
        if prev_close <= 0 or realtime <= 0:
            return None, None, None
        return prev_close, prev_close, realtime
    except:
        return None, None, None


def get_prices(ticker: str, market: str):
    if market == "A":
        return get_a_prices(ticker)
    elif market == "US":
        return get_us_prices(ticker)
    elif market == "KR":
        return get_asia_prices(f"{ticker}.KS")
    elif market == "JP":
        return get_asia_prices(f"{ticker}.T")
    elif market == "HK":
        return get_hk_prices(ticker)
    return None, None, None


def get_us_market_session():
    try:
        et_tz = ZoneInfo("America/New_York")
        now_et = datetime.now(et_tz)
        pre_start = now_et.replace(hour=4, minute=0, second=0, microsecond=0)
        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        post_end = now_et.replace(hour=20, minute=0, second=0, microsecond=0)

        if pre_start <= now_et < market_open:
            return "盘前"
        elif market_open <= now_et < market_close:
            return "盘中"
        elif market_close <= now_et < post_end:
            return "盘后"
        else:
            return "休市"
    except:
        return "盘中"


# ==================== 估值计算（归一化 + 0.8 现金缓冲） ====================
def calculate_fund_estimates(holdings):
    close_rows, rt_rows = [], []
    close_sum = rt_sum = 0.0
    sum_w = sum(h["weight"] for h in holdings)

    for h in holdings:
        prev2, prev1, realtime = get_prices(h["ticker"], h["market"])
        w = h["weight"]

        chg_close = 0.0
        if prev2 and prev1 and prev2 > 0:
            chg_close = (prev1 / prev2 - 1) * 100

        chg_rt = 0.0
        if prev1 and realtime and prev1 > 0:
            chg_rt = (realtime / prev1 - 1) * 100

        # 港股杠杆ETF：close 和 rt 使用同一数据源的涨跌幅
        if h.get("market") == "HK":
            chg_close = chg_rt

        close_sum += w * chg_close / 100
        rt_sum += w * chg_rt / 100

        close_rows.append({"名称": h["name"], "权重": f"{w:.2f}%", "涨跌": f"{chg_close:+.2f}%"})
        rt_rows.append({"名称": h["name"], "权重": f"{w:.2f}%", "涨跌": f"{chg_rt:+.2f}%"})

    # 归一化 + 乘以 0.8（现金缓冲）
    if sum_w > 0:
        close_val = (close_sum / (sum_w / 100.0)) * 0.8
        rt_val = (rt_sum / (sum_w / 100.0)) * 0.8
    else:
        close_val = rt_val = 0.0

    return close_val, rt_val, close_rows, rt_rows


def render_top10_table(rows):
    sorted_rows = sorted(rows, key=lambda x: float(x["权重"].replace("%", "")) if "%" in x["权重"] else 0, reverse=True)[:10]
    html = '<table style="width:100%;font-size:0.82rem;border-collapse:collapse;">'
    html += '<tr style="border-bottom:1px solid #444;"><th style="text-align:left;">名称</th><th style="text-align:center;">权重</th><th style="text-align:center;">涨跌</th></tr>'
    for r in sorted_rows:
        color = "#E03030" if r["涨跌"].startswith("+") else ("#16A34A" if r["涨跌"].startswith("-") else "#888")
        html += f'<tr><td>{r["名称"]}</td><td style="text-align:center;color:#aaa;">{r["权重"]}</td><td style="text-align:center;color:{color};">{r["涨跌"]}</td></tr>'
    html += '</table><div style="font-size:0.75rem;color:#888;margin-top:4px;">※ 仅显示前10，其余持仓已纳入估值计算</div>'
    return html


# ==================== 界面 ====================
st.set_page_config(page_title="估值助手", layout="wide")
st.title("📈 估值助手")

st.markdown("<div style='text-align:center;color:#888;'>估值使用全部持仓计算，界面仅显示前10</div>", unsafe_allow_html=True)

current_session = get_us_market_session()
st.markdown(f"<div style='text-align:center;color:#4a9eff;margin:8px 0;font-weight:500;'>当前美股市场阶段：{current_session}</div>", unsafe_allow_html=True)

if st.button("🔄 立即刷新", type="primary"):
    st.cache_data.clear()
    st.rerun()

cols = st.columns(2)
for i, (name, fund) in enumerate(FUND_HOLDINGS.items()):
    with cols[i % 2]:
        with st.container(border=True):
            st.markdown(f"<h3 style='text-align:center;'>{fund['short_name']}</h3>", unsafe_allow_html=True)
            close_val, rt_val, close_rows, rt_rows = calculate_fund_estimates(fund["holdings"])

            c1, c2 = st.columns(2)
            with c1:
                st.metric("📅 收盘估值", f"{close_val:+.2f}%")
                with st.expander("持仓详情（前10）"):
                    st.markdown(render_top10_table(close_rows), unsafe_allow_html=True)
            with c2:
                st.metric(f"⚡ 实时估值（{current_session}）", f"{rt_val:+.2f}%")
                with st.expander("持仓详情（前10）"):
                    st.markdown(render_top10_table(rt_rows), unsafe_allow_html=True)

st.caption(f"最后更新：{datetime.now().strftime('%H:%M:%S')}")