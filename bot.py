import requests
import time
import datetime
import pytz
import schedule
import threading

# Config
TELEGRAM_TOKEN = "8940316357:AAH67eQjaMCeFICX76ek3x-i74PG_jQsXco"
CHAT_ID = "6601488025"
FINNHUB_KEY = "d8rmdhpr01qnkitoriqgd8rmdhpr01qnkitorir0"

TICKERS = ["MIR","AXTI","MSFT","TEM","SHOP","META","NOW","VEC","IBM","BABA",
           "CLBT","BBAI","SLDP","ERIC","INFO","NOK","PL","QUBT","HIMS","MP",
           "SOUN","APLD","ASTS"]

CONSEC_NEEDED = 3

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

def calc_ema(values, period):
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    emas = [ema]
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
        emas.append(ema)
    return emas

def fetch_and_analyze(ticker):
    try:
        now = int(time.time())
        from_ts = now - 60 * 60 * 8

        q = requests.get(f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}", timeout=10).json()
        c = requests.get(f"https://finnhub.io/api/v1/stock/candle?symbol={ticker}&resolution=5&from={from_ts}&to={now}&token={FINNHUB_KEY}", timeout=10).json()

        if c.get("s") == "no_data" or not c.get("c"):
            return None

        closes = c["c"]
        current_price = q["c"]
        open_price = q["o"]
        pct = ((current_price - open_price) / open_price * 100) if open_price else 0

        ema5 = calc_ema(closes, 5)
        ema8 = calc_ema(closes, 8)

        offset = 7 - 4  # ema8 starts at index 7, ema5 at 4
        a5 = ema5[offset:]
        a8 = ema8
        mn = min(len(a5), len(a8))

        # Find most recent EMA5 cross above EMA8
        cross_idx = -1
        for i in range(mn - 1, 0, -1):
            if a5[i] > a8[i] and a5[i-1] <= a8[i-1]:
                cross_idx = i
                break

        ema_crossed = cross_idx != -1
        ema_above = a5[mn-1] > a8[mn-1] if mn > 0 else False
        consec_ok = False
        rising_count = 0

        if ema_crossed:
            cross_candle = cross_idx + 7
            check = closes[cross_candle:]
            last = check[-(CONSEC_NEEDED + 2):]
            if len(last) >= CONSEC_NEEDED + 1:
                rising = sum(1 for i in range(1, len(last)) if last[i] > last[i-1])
                rising_count = rising
                consec_ok = rising >= CONSEC_NEEDED

        is_rallying = ema_crossed and ema_above and consec_ok

        return {
            "ticker": ticker,
            "price": current_price,
            "pct": pct,
            "ema_crossed": ema_crossed,
            "ema_above": ema_above,
            "rising_count": rising_count,
            "consec_ok": consec_ok,
            "rallying": is_rallying
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}

def run_scan(label):
    ny = pytz.timezone("America/New_York")
    now_str = datetime.datetime.now(ny).strftime("%I:%M %p ET")
    send_telegram(f"🔍 <b>Rally Scan — {label}</b>\nScanning {len(TICKERS)} tickers at {now_str}...")

    results = [fetch_and_analyze(t) for t in TICKERS]
    time.sleep(1)

    rallying = [r for r in results if r and r.get("rallying")]
    not_rallying = [r for r in results if r and not r.get("rallying") and not r.get("error")]
    errors = [r for r in results if r and r.get("error")]

    msg = f"📊 <b>{label} Results</b> — {now_str}\n"
    msg += f"{'='*28}\n"

    if rallying:
        msg += f"\n🟢 <b>RALLYING ({len(rallying)})</b>\n"
        for r in rallying:
            pct_str = f"+{r['pct']:.2f}%" if r['pct'] >= 0 else f"{r['pct']:.2f}%"
            msg += f"  ⬆ <b>{r['ticker']}</b>  ${r['price']:.2f}  {pct_str}\n"
            msg += f"     EMA cross ✓  EMA5>8 ✓  {r['rising_count']} rising closes ✓\n"
    else:
        msg += "\n🟢 RALLYING: None\n"

    msg += f"\n🔴 <b>NOT RALLYING ({len(not_rallying)})</b>\n"
    for r in not_rallying:
        pct_str = f"+{r['pct']:.2f}%" if r['pct'] >= 0 else f"{r['pct']:.2f}%"
        reasons = []
        if not r['ema_crossed']: reasons.append("no EMA cross")
        if not r['ema_above']: reasons.append("EMA5<8")
        if not r['consec_ok']: reasons.append(f"only {r['rising_count']} rising")
        msg += f"  ✗ {r['ticker']}  ${r['price']:.2f}  {pct_str}  ({', '.join(reasons)})\n"

    if errors:
        msg += f"\n⚠️ Errors: {', '.join(e['ticker'] for e in errors)}\n"

    send_telegram(msg)

def scan_10_00(): run_scan("10:00 AM")
def scan_10_30(): run_scan("10:30 AM")
def scan_10_40(): run_scan("10:40 AM")

def run_scheduler():
    ny = pytz.timezone("America/New_York")

    while True:
        now = datetime.datetime.now(ny)
        h, m, s = now.hour, now.minute, now.second

        if s == 0:
            if h == 10 and m == 0:  scan_10_00()
            if h == 10 and m == 30: scan_10_30()
            if h == 10 and m == 40: scan_10_40()

        time.sleep(1)

if __name__ == "__main__":
    send_telegram("✅ <b>Rally Scanner Bot is online!</b>\nWill scan at 10:00, 10:30 and 10:40 AM ET daily.\nTickers: " + ", ".join(TICKERS))
    print("Bot started. Waiting for scan times...")
    run_scheduler()
