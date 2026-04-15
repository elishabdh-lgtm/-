"""
telegram_news.py — ניוזלטר בוקר יומי כתמונה
מתרגם לעברית, מעצב תמונה יפה, שולח לטלגרם
"""

import sys, json, requests, os, yfinance as yf, textwrap, time
import xml.etree.ElementTree as ET
from deep_translator import GoogleTranslator
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from bidi.algorithm import get_display

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "telegram_config.json")
OUTPUT_IMG  = os.path.join(os.path.dirname(__file__), "morning_brief.png")

PORTFOLIO_TICKERS = [
    "IVV","QQQ","ARKK","BOTZ","ICLN","IBIT","ETHA","QTEC","BLOK",
    "AFRM","AGIG","AMZN","ANET","ASTS","AXP","BMNR","C","CAT","CRM",
    "GOOG","GPN","HD","HOOD","INTC","IRM","KD","META","MOD","MSFT",
    "NBIS","NFLX","NIO","NOW","NVDA","OKLO","ON","OPEN","PLTR","PONY",
    "PSNL","PYPL","QCOM","QTUM","QUBT","SOLZ","SOUN","SUPN","TEM",
    "TSLA","VST","WGS","ZG","ZIM",
]

IMPORTANT_KEYWORDS = [
    "earnings","revenue","profit","loss","beat","miss","guidance","outlook",
    "upgrade","downgrade","target","analyst","raises","cuts","initiated",
    "deal","contract","acquisition","merger","buyout","partnership",
    "fda","approval","approved","rejected","recall",
    "ceo","cfo","resign","appoint","investigation","lawsuit","fine","sec",
    "launch","announce","agreement","dividend","buyback","offering",
    "record","surge","soar","plunge","crash","rally","tumble",
    "quarter","q1","q2","q3","q4","forecast","guidance","beat","miss",
]

# ═══════════════════════════════════════
#  עזרים
# ═══════════════════════════════════════
def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def is_important(headline):
    return any(kw in headline.lower() for kw in IMPORTANT_KEYWORDS)

def get_google_news(query, n=5):
    try:
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-US&gl=US&ceid=US:en"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        root = ET.fromstring(r.content)
        return [i.findtext("title","").strip() for i in root.findall(".//item")[:n] if i.findtext("title")]
    except:
        return []

def get_vix():
    try:
        df = yf.Ticker("^VIX").history(period="5d")
        if df.empty: return None, "?"
        vix = round(float(df["Close"].iloc[-1]), 1)
        sig = "רגוע" if vix < 15 else ("תקין" if vix < 20 else ("זהירות" if vix < 25 else ("פחד" if vix < 30 else "פחד קיצוני")))
        return vix, sig
    except:
        return None, "?"

def get_market_snapshot():
    tickers = {"S&P 500": "^GSPC", "Nasdaq": "^IXIC", "Dow": "^DJI", "Bitcoin": "BTC-USD"}
    out = {}
    for name, sym in tickers.items():
        try:
            df = yf.Ticker(sym).history(period="2d")
            if len(df) >= 2:
                prev, curr = df["Close"].iloc[-2], df["Close"].iloc[-1]
                out[name] = {"price": curr, "chg": (curr - prev) / prev * 100}
        except:
            pass
    return out

def get_stock_news_raw():
    news = {}
    for t in PORTFOLIO_TICKERS:
        try:
            items = yf.Ticker(t).news or []
            headlines = []
            for n in items[:8]:
                title = n.get("content", {}).get("title") or n.get("title", "")
                if title and is_important(title):
                    headlines.append(title)
            if headlines:
                news[t] = headlines[:2]
        except:
            pass
    return news

# ═══════════════════════════════════════
#  תרגום לעברית עם Claude
# ═══════════════════════════════════════
def _tr(text: str) -> str:
    """מתרגם טקסט אחד לעברית עם retry"""
    if not text or not text.strip():
        return text
    for attempt in range(3):
        try:
            result = GoogleTranslator(source="en", target="iw").translate(text[:499])
            return result or text
        except Exception:
            time.sleep(1)
    return text

def translate_to_hebrew(stock_news: dict, market_news: list, macro_news: list) -> dict:
    """מתרגם את כל הכותרות לעברית"""
    translated_stocks = {}
    for ticker, headlines in stock_news.items():
        translated_stocks[ticker] = [_tr(h) for h in headlines]

    translated_market = [_tr(h) for h in market_news]
    translated_macro  = [_tr(h) for h in macro_news]

    return {
        "stock_news":  translated_stocks,
        "market_news": translated_market,
        "macro_news":  translated_macro,
    }

# ═══════════════════════════════════════
#  עיצוב תמונה
# ═══════════════════════════════════════
# צבעים
BG_TOP      = (10, 20, 40)       # כחול כהה
BG_BOTTOM   = (5, 10, 25)        # כחול עמוק
GOLD        = (212, 175, 55)      # זהב
WHITE       = (240, 240, 240)
LIGHT_GRAY  = (180, 190, 200)
GREEN       = (80, 200, 120)
RED         = (240, 80, 80)
CYAN        = (100, 200, 220)
DIVIDER     = (40, 60, 90)

def _find_font(*candidates):
    """מחפש פונט מרשימת מועמדים — Windows ו-Linux"""
    search_dirs = [
        r"C:\Windows\Fonts",           # Windows
        "/usr/share/fonts/truetype",   # Linux
        "/usr/share/fonts",
        "/usr/local/share/fonts",
    ]
    for name in candidates:
        # נתיב מלא ישיר
        if os.path.isfile(name):
            return name
        # חיפוש בתיקיות
        for d in search_dirs:
            for root, _, files in os.walk(d):
                for f in files:
                    if f.lower() == name.lower() or f.lower().startswith(name.lower().replace(".ttf","")):
                        return os.path.join(root, f)
    return None

F_BOLD   = _find_font("davidbd.ttf", "LiberationSans-Bold.ttf",   "DejaVuSans-Bold.ttf")
F_REG    = _find_font("david.ttf",   "LiberationSans-Regular.ttf", "DejaVuSans.ttf")
F_LATIN_B = _find_font("arialbd.ttf","LiberationSans-Bold.ttf",   "DejaVuSans-Bold.ttf")
F_LATIN   = _find_font("arial.ttf",  "LiberationSans-Regular.ttf", "DejaVuSans.ttf")

W, H = 900, 1500

def he(text):
    """עברית RTL"""
    return get_display(str(text))

def draw_gradient(img):
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

def load_fonts():
    sizes = {}
    for name, path, sz in [
        ("title",    F_BOLD,    52),
        ("subtitle", F_BOLD,    28),
        ("section",  F_BOLD,    24),
        ("body",     F_REG,     22),
        ("small",    F_REG,     18),
        ("ticker",   F_LATIN_B, 22),
        ("num_big",  F_LATIN_B, 36),
        ("num_med",  F_LATIN_B, 24),
    ]:
        try:
            sizes[name] = ImageFont.truetype(path, sz)
        except:
            sizes[name] = ImageFont.load_default()
    return sizes

def wrap_hebrew(text, font, draw, max_width):
    """עוטף טקסט עברי לפי רוחב"""
    words = text.split()
    lines, current = [], []
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), he(test), font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines

def draw_rounded_rect(draw, x1, y1, x2, y2, radius, fill, outline=None, outline_width=1):
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill,
                            outline=outline, width=outline_width)

def build_image(translated: dict, snapshot: dict, vix: float, vix_sig: str) -> str:
    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    draw_gradient(img)
    fonts = load_fonts()

    today     = datetime.now()
    date_str  = today.strftime("%d/%m/%Y")
    time_str  = today.strftime("%H:%M")
    day_names = ["שני","שלישי","רביעי","חמישי","שישי","שבת","ראשון"]
    day_he    = day_names[today.weekday()]

    y = 30

    # ── כותרת ראשית ──
    draw.text((W//2, y + 30), "📊", font=fonts["title"], fill=WHITE, anchor="mm")
    y += 60
    draw.text((W//2, y), he("דוח בוקר"), font=fonts["title"], fill=GOLD, anchor="mm")
    y += 55
    draw.text((W//2, y), he(f"יום {day_he} | {date_str} | {time_str}"),
              font=fonts["small"], fill=LIGHT_GRAY, anchor="mm")
    y += 40

    # קו הפרדה
    draw.line([(60, y), (W - 60, y)], fill=GOLD, width=2)
    y += 25

    # ── מדדים ──
    draw.text((W//2, y), he("מדדים"), font=fonts["subtitle"], fill=CYAN, anchor="mm")
    y += 40

    # 4 מדדים בשורה אחת
    market_items = list(snapshot.items())
    cell_w = (W - 80) // max(len(market_items), 1)
    for i, (name, data) in enumerate(market_items):
        cx = 40 + cell_w * i + cell_w // 2
        chg = data["chg"]
        price = data["price"]
        color = GREEN if chg >= 0 else RED
        sign  = "▲" if chg >= 0 else "▼"

        # כרטיס מדד
        draw_rounded_rect(draw, 40 + cell_w * i + 4, y - 5,
                          40 + cell_w * (i + 1) - 4, y + 80,
                          8, (20, 35, 60), outline=DIVIDER)

        draw.text((cx, y + 10), name, font=fonts["small"], fill=LIGHT_GRAY, anchor="mm")
        if name == "Bitcoin":
            price_str = f"${price:,.0f}"
        else:
            price_str = f"{price:,.0f}"
        draw.text((cx, y + 38), price_str, font=fonts["ticker"], fill=WHITE, anchor="mm")
        draw.text((cx, y + 62), f"{sign} {abs(chg):.1f}%",
                  font=fonts["small"], fill=color, anchor="mm")

    y += 100

    # VIX
    vix_color = GREEN if vix and vix < 20 else (GOLD if vix and vix < 25 else RED)
    vix_str = f"VIX: {vix:.1f} — {vix_sig}" if vix else "VIX: —"
    draw.text((W//2, y), he(vix_str), font=fonts["small"], fill=vix_color, anchor="mm")
    y += 35

    # קו
    draw.line([(60, y), (W - 60, y)], fill=DIVIDER, width=1)
    y += 22

    # ── חדשות שוק ──
    draw.text((W//2, y), he("חדשות שוק"), font=fonts["subtitle"], fill=CYAN, anchor="mm")
    y += 38

    all_market = (translated.get("market_news", []) + translated.get("macro_news", []))[:5]
    for news_item in all_market:
        lines = wrap_hebrew(news_item, fonts["body"], draw, W - 120)
        for line in lines[:2]:
            draw.text((W - 60, y), he("• " + line), font=fonts["body"],
                      fill=WHITE, anchor="ra")
            y += 30
        y += 4

    y += 10
    draw.line([(60, y), (W - 60, y)], fill=GOLD, width=2)
    y += 22

    # ── חדשות תיק ──
    draw.text((W//2, y), he("חדשות מניות התיק"), font=fonts["subtitle"], fill=GOLD, anchor="mm")
    y += 42

    stock_news = translated.get("stock_news", {})
    if not stock_news:
        draw.text((W//2, y), he("אין חדשות חשובות היום"), font=fonts["body"],
                  fill=LIGHT_GRAY, anchor="mm")
        y += 40
    else:
        for ticker, headlines in list(stock_news.items())[:12]:
            if y > H - 120:
                break

            # שם המניה
            draw_rounded_rect(draw, 60, y - 2, 60 + 90, y + 28,
                               6, (30, 50, 80))
            draw.text((105, y + 12), ticker, font=fonts["ticker"],
                      fill=CYAN, anchor="mm")

            # כותרת ראשונה
            if headlines:
                h = headlines[0]
                lines = wrap_hebrew(h, fonts["body"], draw, W - 200)
                for line in lines[:2]:
                    draw.text((W - 60, y + 5), he(line), font=fonts["body"],
                              fill=WHITE, anchor="ra")
                    y += 30
            y += 14

            # קו דק
            draw.line([(60, y), (W - 60, y)], fill=DIVIDER, width=1)
            y += 12

    # ── פוטר ──
    y = H - 55
    draw.line([(60, y - 15), (W - 60, y - 15)], fill=DIVIDER, width=1)
    draw.text((W//2, y + 5), he("הדוח נוצר אוטומטית | Claude Code × Elisha Stock Bot"),
              font=fonts["small"], fill=LIGHT_GRAY, anchor="mm")

    img.save(OUTPUT_IMG, "PNG", quality=95)
    return OUTPUT_IMG

# ═══════════════════════════════════════
#  שליחת תמונה לטלגרם
# ═══════════════════════════════════════
def send_photo(token, chat_id, image_path, caption=""):
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    with open(image_path, "rb") as f:
        resp = requests.post(url, data={
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "HTML"
        }, files={"photo": f})
    return resp.ok

def send_message(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text,
                              "parse_mode": "HTML", "disable_web_page_preview": True})

# ═══════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════
def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] מתחיל ניוזלטר בוקר...")
    config  = load_config()
    token   = config["bot_token"]
    chat_id = config["chat_id"]

    print(f"[{datetime.now().strftime('%H:%M:%S')}] מושך נתוני שוק...")
    vix, vix_sig = get_vix()
    snapshot     = get_market_snapshot()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] מושך חדשות מניות...")
    stock_news_raw = get_stock_news_raw()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] מושך חדשות שוק...")
    market_news = get_google_news("US stock market today", 4)
    macro_news  = get_google_news("Federal Reserve economy inflation 2026", 3)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] מתרגם לעברית עם Claude...")
    try:
        translated = translate_to_hebrew(stock_news_raw, market_news, macro_news)
    except Exception as e:
        print(f"  ⚠️ שגיאת תרגום: {e} — ממשיך עם אנגלית")
        translated = {
            "stock_news": stock_news_raw,
            "market_news": market_news,
            "macro_news": macro_news,
        }

    print(f"[{datetime.now().strftime('%H:%M:%S')}] בונה תמונה...")
    img_path = build_image(translated, snapshot, vix, vix_sig)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] שולח לטלגרם...")
    today_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    ok = send_photo(token, chat_id, img_path,
                    caption=f"📊 <b>דוח בוקר — {today_str}</b>")
    if ok:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ הדוח נשלח בהצלחה!")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ שגיאה בשליחה")

if __name__ == "__main__":
    main()
