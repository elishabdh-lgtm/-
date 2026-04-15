"""
analyze.py — סוכן תיק השקעות — נועם
ניתוח מלא: טכני (שיטת מיכה סטוקס + ATR) + פונדמנטלי + חדשות + המלצה
"""

import yfinance as yf
import pandas_ta as ta
import json, sys, requests, numpy as np
import xml.etree.ElementTree as ET
from datetime import datetime

# ── encoding + JSON ──
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

class _Enc(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, np.bool_):    return bool(o)
        if isinstance(o, np.integer):  return int(o)
        if isinstance(o, np.floating): return float(o)
        return super().default(o)

# ══════════════════════════════════════════════
#  תיק + עלויות ידועות מהסקרינשוטים
# ══════════════════════════════════════════════
PORTFOLIO = {
    "capital": 73000, "monthly_addition": 2500, "target_etf_pct": 60,
    "etfs":   ["IVV","QQQ","ARKK","BOTZ","ICLN","IBIT","ETHA","QTEC","BLOK"],
    "stocks": [
        "AFRM","AGIG","AMZN","ANET","ASTS","AXP","BMNR","C","CAT","CRM",
        "GOOG","GPN","HD","HOOD","INTC","IRM","KD","META","MOD","MSFT",
        "NBIS","NFLX","NIO","NOW","NVDA","OKLO","ON","OPEN","OPENL","OPENW",
        "OPENZ","PLTR","PONY","PSNL","PYPL","QCOM","QTUM","QUBT","SOLZ",
        "SOUN","SUPN","TEM","TSLA","VST","WGS","ZG","ZIM",
    ],
}

# ETFs לטווח ארוך — לפי מיכה: אין סטופ מכני, רק רמת מעקב
LONG_TERM_ETFS = {"IVV", "QQQ", "BOTZ", "ICLN", "QTEC", "IBIT", "ETHA", "BLOK", "ARKK"}

# פוזיציות ידועות מסקרינשוטים
POSITIONS = {
    "NBIS":  {"shares": 14,  "value": 2174.20, "pnl": 907.20,   "pnl_pct": 71.60},
    "NFLX":  {"shares": 20,  "value": 2064.40, "pnl": 743.73,   "pnl_pct": 56.31},
    "NIO":   {"shares": 41,  "value": 265.68,  "pnl": 51.01,    "pnl_pct": 23.76},
    "NOW":   {"shares": 5,   "value": 445.55,  "pnl": -371.94,  "pnl_pct": -45.50},
    "NVDA":  {"shares": 3,   "value": 567.78,  "pnl": 161.65,   "pnl_pct": 39.80},
    "OKLO":  {"shares": 15,  "value": 814.50,  "pnl": 473.40,   "pnl_pct": 138.79},
    "ON":    {"shares": 2,   "value": 142.00,  "pnl": -10.11,   "pnl_pct": -6.65},
    "OPEN":  {"shares": 130, "value": 566.80,  "pnl": 18.20,    "pnl_pct": 3.32},
    "OPENL": {"shares": 4.33,"value": 1.12,    "pnl": -3.00,    "pnl_pct": -72.89},
    "OPENW": {"shares": 4.33,"value": 2.17,    "pnl": -2.03,    "pnl_pct": -48.33},
    "OPENZ": {"shares": 4.33,"value": 1.00,    "pnl": -3.11,    "pnl_pct": -75.75},
    "PLTR":  {"shares": 13,  "value": 1724.06, "pnl": -85.87,   "pnl_pct": -4.74},
    "PONY":  {"shares": 40,  "value": 401.20,  "pnl": -90.00,   "pnl_pct": -18.32},
    "PSNL":  {"shares": 75,  "value": 473.25,  "pnl": -33.74,   "pnl_pct": -6.66},
    "PYPL":  {"shares": 4,   "value": 190.04,  "pnl": -50.03,   "pnl_pct": -20.84},
    "QCOM":  {"shares": 2,   "value": 263.02,  "pnl": 28.93,    "pnl_pct": 12.36},
    "QQQ":   {"shares": 4,   "value": 2471.80, "pnl": 751.04,   "pnl_pct": 43.65},
    "QTEC":  {"shares": 1,   "value": 233.21,  "pnl": 91.48,    "pnl_pct": 64.54},
    "QTUM":  {"shares": 3,   "value": 358.11,  "pnl": 98.95,    "pnl_pct": 38.18},
    "QUBT":  {"shares": 35,  "value": 254.45,  "pnl": -345.80,  "pnl_pct": -57.61},
    "SOLZ":  {"shares": 40,  "value": 340.00,  "pnl": -647.40,  "pnl_pct": -65.55},
    "SOUN":  {"shares": 90,  "value": 611.10,  "pnl": -245.70,  "pnl_pct": -28.68},
    "SUPN":  {"shares": 22,  "value": 1098.24, "pnl": 113.52,   "pnl_pct": 11.53},
    "TEM":   {"shares": 18,  "value": 829.80,  "pnl": -347.40,  "pnl_pct": -29.51},
    "TSLA":  {"shares": 3,   "value": 1057.08, "pnl": -105.63,  "pnl_pct": -9.08},
    "VST":   {"shares": 8,   "value": 1267.28, "pnl": 348.29,   "pnl_pct": 37.90},
    "WGS":   {"shares": 5,   "value": 303.35,  "pnl": -152.90,  "pnl_pct": -33.51},
    "ZG":    {"shares": 7,   "value": 284.48,  "pnl": -307.86,  "pnl_pct": -51.97},
    "ZIM":   {"shares": 100, "value": 2652.00, "pnl": 1218.01,  "pnl_pct": 84.94},
    "BOTZ":  {"shares": 8,   "value": 287.84,  "pnl": 33.68,    "pnl_pct": 13.25},
    "C":     {"shares": 5,   "value": 633.75,  "pnl": 159.30,   "pnl_pct": 33.58},
    "CAT":   {"shares": 1,   "value": 791.73,  "pnl": 357.90,   "pnl_pct": 82.50},
    "CRM":   {"shares": 4,   "value": 691.56,  "pnl": -302.24,  "pnl_pct": -30.41},
    "ETHA":  {"shares": 308, "value": 5254.48, "pnl": -1616.56, "pnl_pct": -23.53},
    "GOOG":  {"shares": 2,   "value": 638.62,  "pnl": 451.20,   "pnl_pct": 240.74},
    "GPN":   {"shares": 1,   "value": 68.16,   "pnl": -29.88,   "pnl_pct": -30.48},
    "HD":    {"shares": 1,   "value": 340.98,  "pnl": -81.49,   "pnl_pct": -19.29},
    "HOOD":  {"shares": 14,  "value": 1005.48, "pnl": -41.86,   "pnl_pct": -4.00},
}

# ══════════════════════════════════════════════
#  חדשות גוגל
# ══════════════════════════════════════════════
def get_google_news(query: str, n: int = 3) -> list:
    try:
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-US&gl=US&ceid=US:en"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        root = ET.fromstring(r.content)
        return [i.findtext("title","").strip() for i in root.findall(".//item")[:n] if i.findtext("title")]
    except Exception:
        return []

# ══════════════════════════════════════════════
#  VIX — מדד הפחד (שיטת מיכה)
# ══════════════════════════════════════════════
def get_vix() -> dict:
    try:
        v = yf.Ticker("^VIX")
        df = v.history(period="5d")
        if df.empty: return {"vix": None, "vix_signal": "unknown"}
        vix = round(float(df["Close"].iloc[-1]), 1)
        if vix < 15:   signal = "קל מאוד — שוק רגוע"
        elif vix < 20: signal = "תקין — אין פחד"
        elif vix < 25: signal = "עלייה בחשש — זהירות"
        elif vix < 30: signal = "פחד — מומנטום מוחלש"
        else:          signal = "פחד קיצוני — הזדמנות או סכנה"
        return {"vix": vix, "vix_signal": signal}
    except:
        return {"vix": None, "vix_signal": "unknown"}

# ══════════════════════════════════════════════
#  ניתוח טרנד — שיטת Edwards & Magee (מיכה)
# ══════════════════════════════════════════════
def classify_trend(price, sma50, sma150, ret_1m, ret_3m) -> str:
    """סיווג טרנד לפי שיטת מיכה סטוקס"""
    above50  = price > sma50
    above150 = price > sma150
    sma_aligned = sma50 > sma150  # ממוצעים מסודרים = טרנד עולה

    if above50 and above150 and sma_aligned:
        if (ret_1m or 0) > 5 and (ret_3m or 0) > 10:
            return "STRONG_UPTREND"   # מגמה עולה חזקה
        return "UPTREND"              # מגמה עולה
    elif above50 and not above150:
        return "RECOVERY"             # התאוששות — מעל 50 אבל לא 150
    elif not above50 and above150:
        return "PULLBACK"             # תיקון — מתחת 50 אבל מעל 150
    elif not above50 and not above150 and not sma_aligned:
        if (ret_1m or 0) < -10 or (ret_3m or 0) < -20:
            return "STRONG_DOWNTREND" # מגמה יורדת חזקה
        return "DOWNTREND"            # מגמה יורדת
    else:
        return "SIDEWAYS"             # ניטרלי

# ══════════════════════════════════════════════
#  זיהוי תמיכה/התנגדות — שיטת מיכה
# ══════════════════════════════════════════════
def find_sr_levels(df) -> dict:
    """
    זיהוי רמות תמיכה והתנגדות לפי swing highs/lows
    Edwards & Magee: נקודות מחיר שהשוק 'זוכר'
    """
    try:
        closes  = df["Close"]
        highs   = df["High"]
        lows    = df["Low"]
        price   = float(closes.iloc[-1])

        # התנגדות = שיא 52 שבועות + שיא 20 יום אחרון
        resist_52  = round(float(highs.max()), 2)
        resist_20  = round(float(highs.iloc[-20:].max()), 2)

        # תמיכה = שפל 52 שבועות + שפל 20 יום אחרון
        support_52 = round(float(lows.min()), 2)
        support_20 = round(float(lows.iloc[-20:].min()), 2)

        # ברייקאאוט — פרץ מעל התנגדות 20 יום ב-5 ימים אחרונים
        recent_high = float(highs.iloc[-6:-1].max()) if len(highs) > 6 else 0
        breakout = price > recent_high * 1.02  # 2% מעל שיא הקודם

        # קרבה לרמות (%)
        dist_resist = round((resist_20 - price) / price * 100, 1)
        dist_support = round((price - support_20) / price * 100, 1)

        # האם קרוב לתמיכה (הזדמנות קנייה לפי מיכה)
        near_support = dist_support < 5   # תוך 5% מהתמיכה
        # האם קרוב להתנגדות (סיכון לדחייה)
        near_resist  = dist_resist < 3    # תוך 3% מההתנגדות

        return {
            "resist_52":    resist_52,
            "resist_20":    resist_20,
            "support_52":   support_52,
            "support_20":   support_20,
            "breakout":     breakout,
            "dist_to_resist": dist_resist,
            "dist_to_support": dist_support,
            "near_support": near_support,
            "near_resist":  near_resist,
        }
    except:
        return {}

# ══════════════════════════════════════════════
#  ציון מיכה סטוקס (0-100)
# ══════════════════════════════════════════════
def calc_micha_score(price, sma50, sma150, trend, sr, vol, avg_vol, vix=None) -> int:
    """
    ציון לפי עקרונות מיכה סטוקס / Edwards & Magee:
    ממוצעים נעים + תמיכה/התנגדות + נפח + VIX
    """
    score = 40  # בסיס

    # 1. ממוצעים נעים — הכי חשוב לפי מיכה
    if price > sma50:               score += 15  # מעל SMA50
    if price > sma150:              score += 15  # מעל SMA150
    if sma50 > sma150:              score += 10  # ממוצעים מסודרים (bullish alignment)

    # 2. עוצמת הטרנד
    if trend == "STRONG_UPTREND":   score += 10
    elif trend == "UPTREND":        score += 7
    elif trend == "RECOVERY":       score += 3
    elif trend == "PULLBACK":       score -= 3
    elif trend == "DOWNTREND":      score -= 10
    elif trend == "STRONG_DOWNTREND": score -= 15

    # 3. תמיכה/התנגדות
    if sr.get("breakout"):          score += 10  # פרץ = כניסה אידיאלית
    if sr.get("near_support"):      score += 5   # ליד תמיכה = הזדמנות
    if sr.get("near_resist"):       score -= 8   # ליד התנגדות = סיכון

    # 4. נפח — אישור הטרנד
    if avg_vol and vol > 0:
        vol_ratio = vol / avg_vol
        if vol_ratio > 1.5 and price > sma50: score += 5   # נפח גבוה בעלייה
        elif vol_ratio > 2.0:                 score -= 5   # נפח חריג = לא ברור

    # 5. VIX — מצב השוק הכללי
    if vix:
        if vix < 15:   score += 5
        elif vix < 20: score += 3
        elif vix > 30: score -= 8
        elif vix > 25: score -= 4

    return max(0, min(100, score))

# ══════════════════════════════════════════════
#  סטופ לוס — שיטת מיכה + ATR משולבת
# ══════════════════════════════════════════════
def calc_stop(ticker, price, sma50, sma150, atr_v, rsi, sup20, trend, sr, is_etf) -> dict:
    """
    סטופ לפי שיטה משולבת:
    - מיכה: ETF לטווח ארוך = אין סטופ מכני (רק רמת מעקב)
    - מיכה: מניות = לפי תמיכה
    - ATR: buffer מדויק מעל/מתחת לרמה
    """
    if is_etf and ticker in LONG_TERM_ETFS:
        # שיטת מיכה לקרנות סל — רמת מעקב בלבד, לא סטופ מכני
        watch_level = round(sma150, 2)  # אם עובר מתחת SMA150 — שקול מכירה
        return {
            "stop": None,
            "stop_type": "ללא_סטופ_מכני",
            "watch_level": watch_level,
            "stop_note": f"ETF ארוך טווח — מיכה: אל תשים סטופ. עקוב אם מחיר יורד מתחת SMA150 ${watch_level}"
        }

    if not atr_v:
        return {"stop": None, "stop_type": None, "watch_level": None, "stop_note": None}

    # שיטת מיכה: סטופ מתחת לתמיכה האחרונה
    micha_stop = None
    stop_type  = None

    if trend in ("STRONG_UPTREND", "UPTREND"):
        # מיכה: סטופ מתחת ל-SMA50 + buffer ATR
        micha_stop = round(sma50 - 1.0 * atr_v, 2)
        stop_type  = "SMA50 - 1xATR"
    elif trend == "RECOVERY":
        # מעל SMA50 אבל לא SMA150 — סטופ הדוק יותר
        micha_stop = round(sma50 - 1.5 * atr_v, 2)
        stop_type  = "SMA50 - 1.5xATR"
    elif trend == "PULLBACK":
        # מתחת SMA50 — סטופ על תמיכת 20 יום
        micha_stop = round(sup20 - 1.0 * atr_v, 2)
        stop_type  = "Support20 - 1xATR"
    elif trend in ("DOWNTREND", "STRONG_DOWNTREND"):
        # ירידה — סטופ צמוד
        micha_stop = round(sup20 - 0.5 * atr_v, 2)
        stop_type  = "Support20 - 0.5xATR"

    # תיקון RSI: אם RSI > 72 = קנוי-יתר, סטופ צמוד יותר
    if rsi > 72 and micha_stop:
        rsi_stop   = round(price - 2.0 * atr_v, 2)
        if rsi_stop > micha_stop:
            micha_stop = rsi_stop
            stop_type  = "Price - 2xATR (RSI>72)"

    return {
        "stop": micha_stop,
        "stop_type": stop_type,
        "watch_level": None,
        "stop_note": None,
    }

# ══════════════════════════════════════════════
#  משיכת נתונים מלאה לנייר ערך
# ══════════════════════════════════════════════
def get_full_data(ticker: str, with_news: bool = True, vix_val: float = None) -> dict:
    try:
        is_etf = ticker in PORTFOLIO["etfs"]
        s   = yf.Ticker(ticker)
        df  = s.history(period="1y")
        if df.empty:
            return {"ticker": ticker, "error": "no data"}

        # ── אינדיקטורים טכניים ──
        df["RSI"]    = ta.rsi(df["Close"], length=14)
        df["SMA20"]  = ta.sma(df["Close"], length=20)
        df["SMA50"]  = ta.sma(df["Close"], length=50)
        df["SMA150"] = ta.sma(df["Close"], length=150)
        atr = ta.atr(df["High"], df["Low"], df["Close"], length=14)
        if atr is not None: df["ATR"] = atr
        macd_df = ta.macd(df["Close"])
        if macd_df is not None:
            df["MACD"], df["MACD_s"] = macd_df.iloc[:,0], macd_df.iloc[:,2]

        price    = float(df["Close"].iloc[-1])
        sma20    = float(df["SMA20"].iloc[-1])
        sma50    = float(df["SMA50"].iloc[-1])
        sma150   = float(df["SMA150"].iloc[-1])
        rsi      = float(df["RSI"].iloc[-1])
        atr_v    = float(df["ATR"].iloc[-1]) if "ATR" in df.columns else None
        high52   = float(df["High"].max())
        low52    = float(df["Low"].min())
        vol      = float(df["Volume"].iloc[-1])
        avg_vol  = float(df["Volume"].mean())
        sup20    = float(df["Low"].rolling(20).min().iloc[-1])

        ret_1m = round((price - float(df["Close"].iloc[-21])) / float(df["Close"].iloc[-21]) * 100, 1) if len(df)>21 else None
        ret_3m = round((price - float(df["Close"].iloc[-63])) / float(df["Close"].iloc[-63]) * 100, 1) if len(df)>63 else None
        ret_1y = round((price - float(df["Close"].iloc[0]))   / float(df["Close"].iloc[0])   * 100, 1)

        macd_bull = False
        if "MACD" in df.columns and len(df) >= 2:
            macd_bull = bool(df["MACD"].iloc[-1] > df["MACD_s"].iloc[-1] and
                            df["MACD"].iloc[-2] <= df["MACD_s"].iloc[-2])

        # ── שיטת מיכה: טרנד + תמיכה/התנגדות ──
        trend = classify_trend(price, sma50, sma150, ret_1m, ret_3m)
        sr    = find_sr_levels(df)

        # ── ציון בריאות קלאסי (RSI + SMA) ──
        tech_score = 50
        if price > sma150:            tech_score += 15
        if price > sma50:             tech_score += 10
        if 40 <= rsi <= 65:           tech_score += 15
        elif rsi > 75:                tech_score -= 10
        elif rsi < 30:                tech_score -= 5
        if ret_3m and ret_3m > 0:     tech_score += 10
        if ret_1y > 10:               tech_score += 10
        if macd_bull:                 tech_score += 5
        if vol > avg_vol * 2:         tech_score -= 5
        tech_score = max(0, min(100, tech_score))

        # ── ציון מיכה (ממוצעים + תמיכה/התנגדות + נפח + VIX) ──
        micha_score = calc_micha_score(price, sma50, sma150, trend, sr, vol, avg_vol, vix_val)

        # ── סטופ לוס משולב ──
        stop_data = calc_stop(ticker, price, sma50, sma150, atr_v, rsi, sup20, trend, sr, is_etf)

        # ── פרי-מארקט ──
        raw = {}
        try:    raw = s.info or {}
        except: pass
        pre       = raw.get("preMarketPrice") or raw.get("postMarketPrice")
        pre_chg   = round((pre - price) / price * 100, 2) if pre else None

        # ── פונדמנטלי מלא ──
        def g(k): return raw.get(k)
        fund = {
            "pe": g("trailingPE"), "fpe": g("forwardPE"), "peg": g("pegRatio"),
            "pb": g("priceToBook"), "ps": g("priceToSalesTrailingTwelveMonths"),
            "ev_ebitda": g("enterpriseToEbitda"), "ev_revenue": g("enterpriseToRevenue"),
            "gross_mg": g("grossMargins"), "op_mg": g("operatingMargins"),
            "profit_mg": g("profitMargins"), "roe": g("returnOnEquity"),
            "roa": g("returnOnAssets"), "eps_ttm": g("trailingEps"),
            "eps_fwd": g("forwardEps"), "eps_growth_q": g("earningsQuarterlyGrowth"),
            "eps_growth_y": g("earningsGrowth"), "rev_growth": g("revenueGrowth"),
            "de_ratio": g("debtToEquity"), "current_ratio": g("currentRatio"),
            "quick_ratio": g("quickRatio"), "fcf": g("freeCashflow"),
            "op_cf": g("operatingCashflow"), "cash": g("totalCash"),
            "debt": g("totalDebt"),
            "target_mean": g("targetMeanPrice"), "target_high": g("targetHighPrice"),
            "target_low": g("targetLowPrice"), "analyst_n": g("numberOfAnalystOpinions"),
            "rec": g("recommendationKey"), "rec_score": g("recommendationMean"),
            "inst_pct": g("heldPercentInstitutions"), "insider_pct": g("heldPercentInsiders"),
            "short_pct": g("shortPercentOfFloat"), "short_ratio": g("shortRatio"),
            "sector": g("sector"), "industry": g("industry"),
            "market_cap": g("marketCap"), "beta": g("beta"),
            "div_yield": g("dividendYield"),
        }

        upside = None
        if fund["target_mean"] and price:
            upside = round((fund["target_mean"] - price) / price * 100, 1)

        # ── חדשות ──
        news_yf = []
        try:
            for n in s.news[:3]:
                t = n.get("content", {}).get("title") or n.get("title","")
                if t: news_yf.append(t)
        except: pass
        news_google = get_google_news(f"{ticker} stock", 3) if with_news else []

        # ── פוזיציה ידועה ──
        pos = POSITIONS.get(ticker, {})

        return {
            "ticker": ticker,
            "sector": fund.pop("sector"), "industry": fund.pop("industry"),
            "market_cap": fund.pop("market_cap"),
            # מחיר
            "price": round(price, 2), "pre": pre, "pre_chg": pre_chg,
            # טכני — קלאסי
            "sma20": round(sma20,2), "sma50": round(sma50,2), "sma150": round(sma150,2),
            "rsi": round(rsi,1), "atr": round(atr_v,2) if atr_v else None,
            "macd_bull": macd_bull, "support20": round(sup20,2),
            "above_sma50": price > sma50, "above_sma150": price > sma150,
            # ── שיטת מיכה ──
            "trend": trend,
            "micha_score": micha_score,
            "resist_20": sr.get("resist_20"),
            "support_20_sr": sr.get("support_20"),
            "breakout": sr.get("breakout", False),
            "near_support": sr.get("near_support", False),
            "near_resist": sr.get("near_resist", False),
            "dist_to_resist": sr.get("dist_to_resist"),
            "dist_to_support": sr.get("dist_to_support"),
            # ── סטופ ──
            "stop": stop_data["stop"],
            "stop_type": stop_data["stop_type"],
            "watch_level": stop_data["watch_level"],
            "stop_note": stop_data["stop_note"],
            # ── ציון בריאות קלאסי ──
            "tech_score": tech_score,
            # ביצועים
            "high52": round(high52,2), "low52": round(low52,2),
            "dist_high": round((high52-price)/high52*100,1),
            "ret_1m": ret_1m, "ret_3m": ret_3m, "ret_1y": ret_1y,
            "vol_ratio": round(vol/avg_vol,2) if avg_vol else None,
            # פונדמנטלי
            **fund,
            "upside_to_target": upside,
            # פוזיציה
            "shares": pos.get("shares"), "pos_value": pos.get("value"),
            "pos_pnl": pos.get("pnl"), "pos_pnl_pct": pos.get("pnl_pct"),
            # חדשות
            "news": (news_google + news_yf)[:4],
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}

# ══════════════════════════════════════════════
#  עזר: שם הטרנד בעברית
# ══════════════════════════════════════════════
def trend_he(trend: str) -> str:
    return {
        "STRONG_UPTREND":   "⬆⬆ עולה חזק",
        "UPTREND":          "⬆ עולה",
        "RECOVERY":         "↗ התאוששות",
        "PULLBACK":         "↘ תיקון",
        "SIDEWAYS":         "➡ ניטרלי",
        "DOWNTREND":        "⬇ יורד",
        "STRONG_DOWNTREND": "⬇⬇ יורד חזק",
    }.get(trend, trend)

# ══════════════════════════════════════════════
#  דוח יומי
# ══════════════════════════════════════════════
def daily_report():
    today       = datetime.now()
    all_tickers = PORTFOLIO["etfs"] + PORTFOLIO["stocks"]

    print(f"\n{'='*70}")
    print(f"📊 דוח תיק — {today.strftime('%d/%m/%Y %H:%M')} | שיטת מיכה סטוקס + ATR")
    print(f"{'='*70}")

    # VIX
    vix_data = get_vix()
    vix_val  = vix_data.get("vix")
    if vix_val:
        print(f"\n😰 VIX: {vix_val} — {vix_data['vix_signal']}")

    # חדשות שוק
    market_news = get_google_news("US stock market today", 3)
    print("\n🌐 חדשות שוק:")
    for n in market_news: print(f"  • {n}")

    # S&P
    spy = get_full_data("SPY", with_news=False, vix_val=vix_val)
    if spy and not spy.get("error"):
        flag = "✅" if spy["above_sma150"] else "⚠️"
        print(f"\n📈 S&P 500: ${spy['price']} | {flag} {trend_he(spy['trend'])} | "
              f"RSI {spy['rsi']} | ציון מיכה: {spy['micha_score']}/100")

    print(f"\n⏳ מושך נתונים ({len(all_tickers)} סימולים)...")
    results = {}
    for i, t in enumerate(all_tickers, 1):
        print(f"  [{i:2}/{len(all_tickers)}] {t}", end="\r")
        d = get_full_data(t, with_news=False, vix_val=vix_val)
        if d: results[t] = d
    print()

    etf_data   = {t: d for t, d in results.items() if t in PORTFOLIO["etfs"]}
    stock_data = {t: d for t, d in results.items() if t in PORTFOLIO["stocks"]}

    def row(t, d):
        pre    = f" פרי:{d['pre_chg']:+.1f}%"     if d.get("pre_chg")    else ""
        stop   = f" סטופ:${d['stop']}"             if d.get("stop")       else ""
        watch  = f" מעקב:${d['watch_level']}"      if d.get("watch_level") else ""
        tgt    = f" יעד:${d['target_mean']:.0f}({d['upside_to_target']:+.0f}%)" \
                 if d.get("target_mean") and d.get("upside_to_target") else ""
        flag   = "✅" if d.get("above_sma150") else ("🟡" if d.get("above_sma50") else "🔴")
        pos    = f" [{d['pos_pnl']:+.0f}$ {d['pos_pnl_pct']:+.1f}%]" \
                 if d.get("pos_pnl") is not None else ""
        bo     = " 🚀BREAKOUT"  if d.get("breakout")    else ""
        ns     = " 📍near-sup"  if d.get("near_support") else ""
        nr     = " 🚧near-res"  if d.get("near_resist")  else ""
        trend_s = trend_he(d.get("trend",""))
        print(f"  {flag} {t:6}|${d['price']:>8}|{trend_s:12}|"
              f"מיכה:{d.get('micha_score',0):>3}|RSI:{d['rsi']:>4.0f}|"
              f"1M:{d['ret_1m'] or 0:>+5.1f}%|3M:{d['ret_3m'] or 0:>+6.1f}%"
              f"{pos}{pre}{stop}{watch}{tgt}{bo}{ns}{nr}")

    print(f"\n{'='*70}")
    print("🏦 קרנות סל: (ETF ארוך טווח = ללא סטופ מכני לפי מיכה)")
    for t, d in sorted(etf_data.items(), key=lambda x: x[1].get("micha_score",0), reverse=True):
        if not d.get("error"): row(t, d)

    print(f"\n📈 מניות:")
    print("  🟢 UPTREND / STRONG_UPTREND:")
    for t,d in sorted(stock_data.items(), key=lambda x:x[1].get("micha_score",0), reverse=True):
        if not d.get("error") and d.get("trend","") in ("STRONG_UPTREND","UPTREND"): row(t,d)
    print("  🟡 RECOVERY / PULLBACK / SIDEWAYS:")
    for t,d in sorted(stock_data.items(), key=lambda x:x[1].get("micha_score",0), reverse=True):
        if not d.get("error") and d.get("trend","") in ("RECOVERY","PULLBACK","SIDEWAYS"): row(t,d)
    print("  🔴 DOWNTREND / STRONG_DOWNTREND:")
    for t,d in sorted(stock_data.items(), key=lambda x:x[1].get("micha_score",0), reverse=True):
        if not d.get("error") and d.get("trend","") in ("DOWNTREND","STRONG_DOWNTREND"): row(t,d)

    print(f"\n{'='*70}")
    print("📋 JSON מלא לניתוח:")
    print("```json")
    print(json.dumps({
        "date": today.strftime("%Y-%m-%d"),
        "vix": vix_data,
        "spy": spy,
        "etfs": etf_data,
        "stocks": stock_data,
    }, ensure_ascii=False, indent=2, cls=_Enc))
    print("```")
    print("✅ נתונים מוכנים לניתוח — כולל שיטת מיכה סטוקס.")

# ══════════════════════════════════════════════
#  ניתוח מניה בודדת
# ══════════════════════════════════════════════
def single_ticker(ticker: str):
    vix_data = get_vix()
    print(f"\n{'='*70}")
    print(f"🔍 {ticker} — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"VIX: {vix_data.get('vix')} | {vix_data.get('vix_signal')}")
    print(f"{'='*70}")
    d = get_full_data(ticker, with_news=True, vix_val=vix_data.get("vix"))
    if not d or d.get("error"):
        print(f"❌ {d.get('error') if d else 'no data'}")
        return
    print(json.dumps(d, ensure_ascii=False, indent=2, cls=_Enc))
    print(f"{'='*70}")
    print(f"✅ Claude — נתח את {ticker} לעומק: טכני (שיטת מיכה: trend={d.get('trend')}, "
          f"micha_score={d.get('micha_score')}, breakout={d.get('breakout')}, "
          f"near_support={d.get('near_support')}) + פונדמנטלי + חדשות + המלצה + סטופ.")

# ══════════════════════════════════════════════
#  השוואה
# ══════════════════════════════════════════════
def compare_tickers(tickers: list):
    vix_data = get_vix()
    print(f"\n{'='*70}")
    print(f"⚖️  {' vs '.join(tickers)}")
    print(f"VIX: {vix_data.get('vix')} | {vix_data.get('vix_signal')}")
    print(f"{'='*70}")
    results = {t: get_full_data(t, with_news=True, vix_val=vix_data.get("vix")) for t in tickers}
    print(json.dumps(results, ensure_ascii=False, indent=2, cls=_Enc))
    print(f"{'='*70}")
    print("✅ Claude — השווה והמלץ בבירור. כלול: trend (שיטת מיכה), micha_score, breakout, near_support, stop.")

# ══════════════════════════════════════════════
#  ניתוח תיק מלא
# ══════════════════════════════════════════════
def full_portfolio_analysis():
    today       = datetime.now()
    all_tickers = PORTFOLIO["etfs"] + PORTFOLIO["stocks"]

    vix_data = get_vix()
    vix_val  = vix_data.get("vix")

    print(f"\n{'='*70}")
    print(f"🔬 ניתוח תיק מלא — {today.strftime('%d/%m/%Y %H:%M')}")
    print(f"VIX: {vix_val} | {vix_data.get('vix_signal')}")
    print(f"{'='*70}")

    market_news = get_google_news("US stock market today", 3)
    print("\n🌐 חדשות שוק:")
    for n in market_news: print(f"  • {n}")

    spy = get_full_data("SPY", with_news=False, vix_val=vix_val)
    if spy and not spy.get("error"):
        flag = "✅ בשוק שור" if spy["above_sma150"] else "⚠️ מתחת SMA150"
        print(f"\n📈 S&P 500: ${spy['price']} | {flag} | {trend_he(spy['trend'])} | "
              f"RSI {spy['rsi']} | ציון מיכה {spy['micha_score']}/100")

    print(f"\n⏳ מושך נתונים מלאים ({len(all_tickers)} סימולים)...")
    results = {}
    for i, t in enumerate(all_tickers, 1):
        print(f"  [{i:2}/{len(all_tickers)}] {t}", end="\r")
        results[t] = get_full_data(t, with_news=True, vix_val=vix_val)
    print()

    print(f"\n{'='*70}")
    print("📋 נתונים מלאים לניתוח עמוק:")
    print("```json")
    print(json.dumps({
        "date": today.strftime("%Y-%m-%d"),
        "vix": vix_data,
        "market": {"spy": spy, "news": market_news},
        "portfolio": results,
    }, ensure_ascii=False, indent=2, cls=_Enc))
    print("```")
    print(f"{'='*70}")
    print("✅ Claude — עבור על כל פוזיציה ותן: המלצה (קנה/מכור/החזק/הקטן), סטופ, סיבה קצרה.")
    print("   כלול: שיטת מיכה (trend, micha_score, breakout, near_support/resist) +")
    print("   טכני (RSI, SMA) + פונדמנטלי (צמיחה, FCF, אנליסטים) + חדשות.")

# ══════════════════════════════════════════════
#  נקודת כניסה
# ══════════════════════════════════════════════
if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or "--daily" in args:
        daily_report()
    elif "--full" in args:
        full_portfolio_analysis()
    elif "--ticker" in args:
        idx = args.index("--ticker")
        if idx + 1 < len(args): single_ticker(args[idx+1].upper())
    elif "--compare" in args:
        idx = args.index("--compare")
        tickers = [t.upper() for t in args[idx+1:]]
        if len(tickers) >= 2: compare_tickers(tickers)
    else:
        daily_report()
