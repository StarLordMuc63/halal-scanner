"""
Halal Dip Scanner - checks the watchlist for the dip-bounce signal.
Signal (rule S4, chosen after the backtest of Sept 25, 2026):
  RSI(14) daily < 35 AND 1-week change <= -4% AND price above its 200-day average.
Plus signal N1 (added Sept 30, 2026): Tier A + HiBeta stocks with RSI(2) < 10 and above 200-day line.
Exit plan: sell limit at +5%; if not reached within 20 trading days (~4 weeks), sell.

Run:  double-click run_scanner.bat   (or:  py halal_scanner.py)
Data: Yahoo Finance daily closes (free, not official, can occasionally be wrong or missing).
      Always confirm a signal in TradingView / Trade Republic before buying.
"""
import os, sys, datetime as dt

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    import subprocess, site, importlib
    print("First run: installing the helper packages (yfinance, pandas). This takes 1-2 minutes...\n")
    cmd = [sys.executable, "-m", "pip", "install", "--user", "yfinance", "pandas"]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        subprocess.run([sys.executable, "-m", "ensurepip", "--user"])
        subprocess.run(cmd)
    try:
        user_site = site.getusersitepackages()
        if user_site not in sys.path:
            sys.path.append(user_site)
        importlib.invalidate_caches()
        import yfinance as yf
        import pandas as pd
        print("\nInstallation done.\n")
    except ImportError:
        print("\nInstallation finished - please close this window and start the scanner again.")
        print("If you see this message again, send a screenshot to Claude.")
        print("Python used:", sys.executable)
        input("\nPress Enter to close...")
        sys.exit(0)

RSI_SIGNAL = 35      # RSI below this = oversold (rule S4)
RSI_NEAR = 40        # RSI below this = "near signal"
WEEK_DROP = -4.0     # 1-week change at or below this (%) (rule S4)
RSI2_SIGNAL = 10     # N1 quick-dip signal (Tier A + HiBeta only): RSI(2) below this
SELLOFF_COUNT = 10  # this many signals at once = broad market sell-off
SETUP_MAX_DIST = 8.0 # "setup": price at most this % above its 200-day line
SETUP_MAX_RSI = 45   # "setup": RSI at or below this

STOCKS = [
    ("AMD", "Advanced Micro Devices"),
    ("AVGO", "Broadcom"),
    ("TSM", "Taiwan Semiconductor (TSMC)"),
    ("ASML", "ASML Holding"),
    ("MRVL", "Marvell Technology"),
    ("IFX.DE", "Infineon Technologies"),
    ("MU", "Micron Technology"),
    ("LRCX", "Lam Research"),
    ("AMAT", "Applied Materials"),
    ("TXN", "Texas Instruments"),
    ("SNDK", "SanDisk"),
    ("CSCO", "Cisco Systems"),
    ("ANET", "Arista Networks"),
    ("COHR", "Coherent"),
    ("AAOI", "Applied Optoelectronics"),
    ("SMCI", "Super Micro Computer"),
    ("AMBA", "Ambarella"),
    ("XFAB.PA", "X-FAB Silicon Foundries"),
    ("8035.T", "Tokyo Electron"),
    ("6857.T", "Advantest"),
    ("6723.T", "Renesas Electronics"),
    ("005930.KS", "Samsung Electronics"),
    ("000660.KS", "SK hynix"),
    ("UMC", "United Microelectronics"),
    ("ASX", "ASE Technology"),
    ("AAPL", "Apple"),
    ("META", "Meta Platforms"),
    ("NBIS", "Nebius Group"),
    ("6701.T", "NEC"),
    ("6702.T", "Fujitsu"),
    ("SAP", "SAP SE"),
    ("ADBE", "Adobe"),
    ("ADSK", "Autodesk"),
    ("FTNT", "Fortinet"),
    ("TYL", "Tyler Technologies"),
    ("BSY", "Bentley Systems"),
    ("APP", "AppLovin"),
    ("CSU.TO", "Constellation Software"),
    ("SHOP", "Shopify"),
    ("TWLO", "Twilio"),
    ("TEAM", "Atlassian"),
    ("DOCU", "DocuSign"),
    ("AME", "AMETEK"),
    ("6861.T", "Keyence"),
    ("6471.T", "NSK"),
    ("002050.SZ", "Zhejiang Sanhua Intelligent Controls"),
    ("6324.T", "Harmonic Drive Systems"),
    ("6954.T", "Fanuc"),
    ("6301.T", "Komatsu"),
    ("6367.T", "Daikin Industries"),
    ("6752.T", "Panasonic Holdings"),
    ("7751.T", "Canon"),
    ("6762.T", "TDK"),
    ("6981.T", "Murata Manufacturing"),
    ("5803.T", "Fujikura"),
    ("5108.T", "Bridgestone"),
    ("6501.T", "Hitachi"),
    ("ABBN.SW", "ABB"),
    ("SU.PA", "Schneider Electric"),
    ("2308.TW", "Delta Electronics"),
    ("ZBRA", "Zebra Technologies"),
    ("CLS", "Celestica"),
    ("CGNX", "Cognex"),
    ("SYM", "Symbotic"),
    ("MOD", "Modine Manufacturing"),
    ("VLTO", "Veralto"),
    ("WCN", "Waste Connections"),
    ("LLY", "Eli Lilly"),
    ("JNJ", "Johnson & Johnson"),
    ("MRK", "Merck & Co."),
    ("TMO", "Thermo Fisher Scientific"),
    ("ISRG", "Intuitive Surgical"),
    ("EW", "Edwards Lifesciences"),
    ("NBIX", "Neurocrine Biosciences"),
    ("COR", "Cencora"),
    ("RHHBY", "Roche Holding (ADR)"),
    ("NOVN.SW", "Novartis"),
    ("AZN", "AstraZeneca"),
    ("NVO", "Novo Nordisk"),
    ("4568.T", "Daiichi Sankyo"),
    ("4503.T", "Astellas Pharma"),
    ("4578.T", "Otsuka Holdings"),
    ("4901.T", "FUJIFILM Holdings"),
    ("4543.T", "Terumo"),
    ("AI.PA", "Air Liquide"),
    ("4063.T", "Shin-Etsu Chemical"),
    ("6988.T", "Nitto Denko"),
    ("BHP", "BHP Group"),
    ("AEM", "Agnico Eagle Mines"),
    ("LYC.AX", "Lynas Rare Earths"),
    ("IPX", "IperionX"),
    ("GEV", "GE Vernova"),
    ("ENR.DE", "Siemens Energy"),
    ("CEG", "Constellation Energy"),
    ("XOM", "Exxon Mobil"),
    ("SLB", "SLB (Schlumberger)"),
    ("DVN", "Devon Energy"),
    ("SU", "Suncor Energy"),
    ("5020.T", "ENEOS Holdings"),
    ("TSLA", "Tesla"),
    ("LULU", "Lululemon"),
    ("1810.HK", "Xiaomi"),
    ("1211.HK", "BYD"),
    ("ULVR.L", "Unilever"),
    ("NESN.SW", "Nestlé"),
    ("KO", "Coca-Cola"),
    ("PG", "Procter & Gamble"),
    ("7936.T", "ASICS"),
    ("ONON", "On Holding"),
    ("8058.T", "Mitsubishi Corporation"),
    ("8031.T", "Mitsui & Co."),
    ("6098.T", "Recruit Holdings"),
]

TIER_A = ['TSM', 'ASML', 'AVGO', 'AAPL', 'META', 'LLY', 'SAP', 'ISRG', 'AMAT', 'LRCX', 'AMD', 'TMO', 'ADBE']
TIER_HB = ['MU', 'MRVL', 'ANET', 'COHR', 'IFX.DE', '6857.T', 'GEV', 'ENR.DE', 'FTNT', 'ADSK', 'MOD']
TIER_B = ['SMCI', 'AAOI', 'APP', 'NBIS', 'IPX', 'LYC.AX', 'TSLA', 'AMBA', 'SYM', 'SHOP', 'SNDK', 'CLS', 'ONON']


def tier(t):
    if t in TIER_A: return "A (1500)"
    if t in TIER_HB: return "HiBeta (1000)"
    if t in TIER_B: return "B (750)"
    return "-"


def rsi_wilder(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss
    return 100 - 100 / (1 + rs)


def analyse(ticker, name, close):
    close = close.dropna()
    if len(close) < 30:
        return {"ticker": ticker, "name": name, "error": "not enough data"}
    last = float(close.iloc[-1])
    rsi = float(rsi_wilder(close).iloc[-1])
    rsi2 = float(rsi_wilder(close, 2).iloc[-1])
    week = (last / float(close.iloc[-6]) - 1) * 100
    sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
    above200 = None if sma200 is None else last > sma200
    dist200 = None if sma200 is None else round((last / sma200 - 1) * 100, 1)
    last_date = close.index[-1].date()
    stale = (dt.date.today() - last_date).days > 5
    return {"ticker": ticker, "name": name, "price": round(last, 2), "rsi": round(rsi, 1), "rsi2": round(rsi2, 1),
            "week_%": round(week, 1), "above_200d": above200, "dist_200d_%": dist200, "last_date": str(last_date),
            "stale": stale, "tier": tier(ticker), "error": ""}


def main():
    tickers = [t for t, _ in STOCKS]
    names = dict(STOCKS)
    print(f"Downloading {len(tickers)} stocks from Yahoo Finance...\n")
    data = yf.download(tickers, period="1y", interval="1d", auto_adjust=True,
                       group_by="ticker", threads=True, progress=False)
    rows = []
    for t in tickers:
        try:
            close = data[t]["Close"] if len(tickers) > 1 else data["Close"]
            rows.append(analyse(t, names[t], close))
        except Exception as e:
            rows.append({"ticker": t, "name": names[t], "error": f"no data ({type(e).__name__})"})

    df = pd.DataFrame(rows)
    ok = df[df["error"] == ""].copy()
    bad = df[df["error"] != ""]

    def fmt(r):
        if r["above_200d"] is None or pd.isna(r["dist_200d_%"]):
            trend = "200d ?"
        else:
            trend = f"{r['dist_200d_%']:+.1f}% vs 200d"
        stale = "  (OLD DATA " + r["last_date"] + ")" if r["stale"] else ""
        return (f"  {r['ticker']:<10} {r['name'][:26]:<26} RSI {r['rsi']:>5}   week {r['week_%']:>6}%   "
                f"{trend:<14} Tier {r['tier']}{stale}")

    today = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
    print("=" * 100)
    print(f"HALAL DIP SCAN  {today}   ({len(ok)} of {len(tickers)} stocks with data)")
    print("=" * 100)

    oversold = ok[(ok["rsi"] < RSI_SIGNAL) & (ok["week_%"] <= WEEK_DROP)]
    sig = oversold[oversold["dist_200d_%"] >= 0].sort_values("rsi")
    below = oversold[~(oversold["dist_200d_%"] >= 0)].sort_values("rsi")
    print(f"\nSIGNALS  (RSI < {RSI_SIGNAL}, week <= {WEEK_DROP}%, ABOVE 200-day line)  -> send to Claude:")
    print("\n".join(fmt(r) for _, r in sig.iterrows()) if len(sig) else "  none today")
    if len(sig) >= SELLOFF_COUNT:
        print(f"\n  !!! {len(sig)} signals at once = broad market sell-off. Take max ONE position. !!!")

    quick = ok[(ok["tier"].str.startswith("A") | ok["tier"].str.startswith("HiBeta")) & (ok["rsi2"] < RSI2_SIGNAL) & (ok["dist_200d_%"] >= 0)
               & ~ok.index.isin(sig.index)].sort_values("rsi2")
    print(f"\nQUICK DIP SIGNALS (N1: Tier A + HiBeta only, RSI(2) < {RSI2_SIGNAL}, ABOVE 200-day line)  -> send to Claude:")
    print("\n".join(fmt(r) + f"   RSI(2) {r['rsi2']}" for _, r in quick.iterrows()) if len(quick) else "  none today")

    print(f"\nOVERSOLD BUT BELOW 200-day line (downtrend - NO BUY):")
    print("\n".join(fmt(r) for _, r in below.iterrows()) if len(below) else "  none")

    near = ok[~ok.index.isin(oversold.index) & (ok["dist_200d_%"] >= 0)
              & ((ok["rsi"] < RSI_NEAR) | (ok["week_%"] <= WEEK_DROP))].sort_values("rsi")
    print(f"\nWATCH  (uptrend, RSI < {RSI_NEAR} or week <= {WEEK_DROP}%, not a full signal yet):")
    print("\n".join(fmt(r) for _, r in near.iterrows()) if len(near) else "  none")

    setup = ok[(ok["dist_200d_%"] >= 0) & (ok["dist_200d_%"] <= SETUP_MAX_DIST) & (ok["rsi"] <= SETUP_MAX_RSI)
               & ~ok.index.isin(oversold.index)].sort_values("dist_200d_%")
    print(f"\nSETUPS  (uptrend, price 0-{SETUP_MAX_DIST}% above 200-day line, RSI <= {SETUP_MAX_RSI}):")
    print("\n".join(fmt(r) for _, r in setup.iterrows()) if len(setup) else "  none")

    if len(bad):
        print("\nNO DATA (check manually): " + ", ".join(bad["ticker"]))

    out = f"scan_{dt.date.today().isoformat()}.csv"
    if os.environ.get("CI"):                       # running on GitHub: save into scans/ + latest.csv
        os.makedirs("scans", exist_ok=True)
        out = os.path.join("scans", out)
        df.sort_values("rsi", na_position="last").to_csv(os.path.join("scans", "latest.csv"), index=False)
    df.sort_values("rsi", na_position="last").to_csv(out, index=False)
    print(f"\nFull table saved to {out}")
    print("\nReminder: confirm every signal in TradingView/Trade Republic and check the news before buying.")
    print("Exit plan: sell limit +5%. Not reached within 20 trading days (~4 weeks) -> sell.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        print("Check your internet connection. If it keeps failing, Yahoo may be blocking requests - try again later.")
        if os.environ.get("CI"):
            sys.exit(1)
    if not os.environ.get("CI"):
        input("\nPress Enter to close...")
