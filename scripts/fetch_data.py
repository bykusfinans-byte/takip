"""
BIST 4 saatlik panel - veri toplama betiği
-------------------------------------------
Yahoo Finance'ten (.IS uzantılı semboller) 1 saatlik mum verisi çeker,
BIST seans saatlerine göre (10:00-18:00, İstanbul) 4 saatlik mumlara
indirger ve EMA9, EMA21, SMA50, MACD, ADX, RSI göstergelerini hesaplayıp
docs/data.json dosyasına yazar.

GitHub Actions workflow'u bu betiği periyodik olarak çalıştırır.
Yerelde denemek için:  pip install -r requirements.txt && python scripts/fetch_data.py
"""

import json
import os
import random
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

# --- Takip edilecek hisseler (Yahoo Finance sembolü: KOD.IS) -------------
SYMBOLS = [
    "THYAO.IS", "ASELS.IS", "GARAN.IS", "AKBNK.IS", "EREGL.IS",
    "KCHOL.IS", "SISE.IS", "BIMAS.IS", "TUPRS.IS", "SASA.IS",
    "FROTO.IS", "TCELL.IS", "PGSUS.IS", "ISCTR.IS", "YKBNK.IS",
]

TIMEFRAME_HOURS = 4
SESSION_START = "10:00"   # BIST açılış (Europe/Istanbul)
LOOKBACK = "60d"          # 1 saatlik veri için geriye dönük aralık
INTERVAL = "60m"

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "data.json")


def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def sma(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window).mean()


def rsi(s: pd.Series, period: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(s: pd.Series, fast=12, slow=26, signal=9):
    macd_line = ema(s, fast) - ema(s, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / atr

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def resample_4h(df: pd.DataFrame) -> pd.DataFrame:
    """1 saatlik mumları BIST seansına (10:00 başlangıç) göre 4 saatlik mumlara indirger."""
    # NOT: pandas 2.2+ sürümlerinde büyük harfli "4H" kısaltması kullanımdan
    # kaldırılıyor / bazı sürümlerde artık hata veriyor -> küçük harf "4h" kullan.
    agg = {
        "Open": df["Open"].resample("4h", origin="start_day", offset="10h").first(),
        "High": df["High"].resample("4h", origin="start_day", offset="10h").max(),
        "Low": df["Low"].resample("4h", origin="start_day", offset="10h").min(),
        "Close": df["Close"].resample("4h", origin="start_day", offset="10h").last(),
        "Volume": df["Volume"].resample("4h", origin="start_day", offset="10h").sum(),
    }
    out = pd.DataFrame(agg).dropna(subset=["Open", "High", "Low", "Close"])
    return out


def _download_with_retry(symbol: str, attempts: int = 3) -> pd.DataFrame:
    """Yahoo Finance zaman zaman (özellikle GitHub Actions gibi bulut IP'lerinden)
    boş sonuç / rate-limit döndürebiliyor; birkaç kez, aralarda bekleyerek dener."""
    last_err = None
    for i in range(attempts):
        try:
            raw = yf.download(symbol, period=LOOKBACK, interval=INTERVAL,
                               progress=False, auto_adjust=False, threads=False)
            if raw is not None and not raw.empty:
                return raw
            last_err = "boş veri döndü"
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
        time.sleep(2 + random.random() * 3)
    raise RuntimeError(f"indirilemedi ({last_err})")


def fetch_symbol(symbol: str):
    raw = _download_with_retry(symbol)
    if raw.empty:
        return None

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    if raw.index.tz is None:
        raw.index = raw.index.tz_localize("UTC")
    raw.index = raw.index.tz_convert("Europe/Istanbul")

    df4h = resample_4h(raw)
    if len(df4h) < 55:  # SMA50 için yeterli veri yoksa atla
        return None

    close = df4h["Close"]
    df4h["EMA9"] = ema(close, 9)
    df4h["EMA21"] = ema(close, 21)
    df4h["SMA50"] = sma(close, 50)
    macd_line, signal_line, hist = macd(close)
    df4h["MACD"] = macd_line
    df4h["MACD_SIGNAL"] = signal_line
    df4h["ADX"] = adx(df4h)
    df4h["RSI"] = rsi(close)

    df4h = df4h.dropna()
    if len(df4h) < 2:
        return None

    def bar_to_dict(row: pd.Series, idx: pd.Timestamp):
        price, e9, e21, s50 = row["Close"], row["EMA9"], row["EMA21"], row["SMA50"]
        cond = (price > e9 > e21 > s50) and (row["ADX"] > 25) and (row["MACD"] > 0)
        return {
            "time": idx.isoformat(),
            "price": round(float(price), 2),
            "ema9": round(float(e9), 2),
            "ema21": round(float(e21), 2),
            "sma50": round(float(s50), 2),
            "macd": round(float(row["MACD"]), 4),
            "adx": round(float(row["ADX"]), 2),
            "rsi": round(float(row["RSI"]), 2),
            "highlight": bool(cond),
        }

    current_idx, prev_idx = df4h.index[-1], df4h.index[-2]
    return {
        "symbol": symbol.replace(".IS", ""),
        "current": bar_to_dict(df4h.loc[current_idx], current_idx),
        "previous": bar_to_dict(df4h.loc[prev_idx], prev_idx),
    }


def main():
    results = []
    errors = []
    for sym in SYMBOLS:
        try:
            r = fetch_symbol(sym)
            if r:
                results.append(r)
            else:
                errors.append(f"{sym}: yetersiz veri")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{sym}: {exc}")
        time.sleep(1.5)  # istekler arasına küçük bekleme -> rate-limit riskini azaltır

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timeframe": f"{TIMEFRAME_HOURS}h",
        "stocks": results,
        "errors": errors,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"{len(results)} hisse yazıldı -> {OUT_PATH}")
    if errors:
        print("Uyarılar:", *errors, sep="\n  - ")


if __name__ == "__main__":
    sys.exit(main())
