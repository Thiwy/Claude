"""Morning opening-range breakout, Paris time, for gold, forex and crypto.

The opening range is the first --minutes after --start (Paris time). The signal
is the first completed bar that CLOSES above the range high (achat / long) or
below the range low (vente / short). Stop at the range midpoint, never more than
--max-stop % from the entry; target at 2R. The same rule is replayed on the last
60 days to show how often the target came before the stop.
A signal is a chart that matched a rule, not a trade to take.

    py morning_scan.py                    # default list, range 09:00-09:15 Paris
    py morning_scan.py --start 08:00 --at 09:30 --max-stop 0.5
    py morning_scan.py --selftest
"""
import argparse, datetime as dt, json, sys, urllib.request

# Yahoo symbol -> (name, bar size in minutes)
SYMBOLS = {"GC=F": ("Or", 15), "EURUSD=X": ("EUR/USD", 5), "EURJPY=X": ("EUR/JPY", 5), "ETH-USD": ("ETH/USD", 5)}
END = dt.time(17, 30)  # a trade still open at 17:30 Paris counts as "ni l'un ni l'autre"
UTC = dt.timezone.utc


def last_sunday(year, month):
    d = dt.date(year, month, 31)
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)


def paris(t_utc):
    # EU rule: summer time from 01:00 UTC on the last Sunday of March to the last Sunday of October
    y = t_utc.year
    start = dt.datetime.combine(last_sunday(y, 3), dt.time(1), UTC)
    end = dt.datetime.combine(last_sunday(y, 10), dt.time(1), UTC)
    return (t_utc + dt.timedelta(hours=2 if start <= t_utc < end else 1)).replace(tzinfo=None)


def fetch(sym, step):
    """60 days of bars as [(Paris time, high, low, close)]."""
    path = "/v8/finance/chart/%s?range=60d&interval=%dm" % (sym, step)
    err = None
    for host in ("query2", "query1"):
        try:
            req = urllib.request.Request("https://%s.finance.yahoo.com%s" % (host, path), headers={"User-Agent": "Mozilla/5.0"})
            res = json.load(urllib.request.urlopen(req, timeout=30))["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            return [(paris(dt.datetime.fromtimestamp(t, UTC)), h, l, c)
                    for t, h, l, c in zip(res.get("timestamp") or [], q["high"], q["low"], q["close"]) if None not in (h, l, c)]
        except Exception as e:  # try the other host, then give up
            err = e
    raise RuntimeError("%s: no data from Yahoo (%s)" % (sym, err))


def day_grid(bars, step, day):
    # drops the live tick (off the bar grid) and other days
    return [b for b in bars if b[0].date() == day and b[0].second == 0 and b[0].minute % step == 0]


def evaluate(grid, step, day, start, minutes, now, max_stop=1.0):
    """grid: one day's bars [(Paris time, high, low, close)]. Returns a dict."""
    t0 = dt.datetime.combine(day, start)
    t1 = t0 + dt.timedelta(minutes=minutes)
    if now < t1:
        return {"status": "range pas fini", "until": t1}
    rng = [b for b in grid if t0 <= b[0] < t1]
    if len(rng) != minutes // step:
        return {"status": "range incomplet (%d bougies sur %d)" % (len(rng), minutes // step)}
    hi, lo = max(b[1] for b in rng), min(b[2] for b in rng)
    cut = min(now, dt.datetime.combine(day, END))
    out = {"status": "en attente", "high": hi, "low": lo, "nrange": len(rng), "last": rng[-1][3], "after": 0, "sig": None}
    for t, h, l, c in grid:
        if t < t1 or t + dt.timedelta(minutes=step) > cut:
            continue
        out["after"] += 1
        out["last"] = c
        s = out["sig"]
        if s is None:
            side = 1 if c > hi else -1 if c < lo else 0
            if side:
                risk = min(abs(c - (hi + lo) / 2), c * max_stop / 100)
                out["sig"] = {"side": side, "time": t + dt.timedelta(minutes=step), "entry": c, "after": out["after"],
                              "stop": c - side * risk, "target": c + 2 * side * risk, "capped": risk < abs(c - (hi + lo) / 2),
                              "bars": 0, "result": None}
                out["status"] = "signal"
        elif s["result"] is None:
            s["bars"] += 1
            # both in one bar: count the stop (we can't see which came first inside a bar)
            if (l <= s["stop"]) if s["side"] > 0 else (h >= s["stop"]):
                s["result"] = "stop"
            elif (h >= s["target"]) if s["side"] > 0 else (l <= s["target"]):
                s["result"] = "objectif"
    return out


def history(bars, step, start, minutes, today, max_stop):
    st = {"jours": 0, "signaux": 0, "objectif": 0, "stop": 0, "achat": 0, "vente": 0}
    for d in sorted({b[0].date() for b in bars} - {today}):
        if d.weekday() > 4:
            continue
        r = evaluate(day_grid(bars, step, d), step, d, start, minutes, dt.datetime.combine(d, END), max_stop)
        if "high" not in r:
            continue
        st["jours"] += 1
        s = r["sig"]
        if s:
            st["signaux"] += 1
            st["achat" if s["side"] > 0 else "vente"] += 1
            if s["result"]:
                st[s["result"]] += 1
    return st


def fmt(x):
    return "%.5f" % x if x < 10 else "%.3f" % x if x < 1000 else "%.1f" % x


def pct(a, b):
    return "%+.2f%%" % ((a - b) / b * 100)


def report(name, step, r, st):
    lines = ["  %s (bougies de %d min) : %s" % (name, step, r["status"])]
    if r.get("until"):
        lines[0] += " (jusqu'à %s)" % r["until"].strftime("%H:%M")
    if "high" in r:
        lines.append("     range %s - %s (%d bougie%s), dernier %s, %d bougie%s depuis le range"
                     % (fmt(r["low"]), fmt(r["high"]), r["nrange"], "s" if r["nrange"] > 1 else "", fmt(r["last"]),
                        r["after"], "s" if r["after"] > 1 else ""))
    s = r.get("sig")
    if s:
        side = "ACHAT (cassure haute)" if s["side"] > 0 else "VENTE (cassure basse)"
        lines.append("     règle remplie : %s à %s, %de bougie après le range, entrée %s"
                     % (side, s["time"].strftime("%H:%M"), s["after"], fmt(s["entry"])))
        lines.append("     stop %s (%s, %s)   objectif %s (%s, 2R)"
                     % (fmt(s["stop"]), pct(s["stop"], s["entry"]), "plafonné à 1 %" if s["capped"] else "milieu du range",
                        fmt(s["target"]), pct(s["target"], s["entry"])))
        lines.append("     aujourd'hui : " + ("%s touché après %d bougie%s" % (s["result"], s["bars"], "s" if s["bars"] > 1 else "")
                                            if s["result"] else "ni stop ni objectif après %d bougie%s" % (s["bars"], "s" if s["bars"] > 1 else "")))
    if st and st["jours"]:
        n = st["signaux"]
        lines.append("     même règle, %d derniers jours : %d signaux (%d achat, %d vente) ; objectif d'abord %d (%s), stop d'abord %d, ni l'un ni l'autre avant 17h30 %d"
                     % (st["jours"], n, st["achat"], st["vente"], st["objectif"], "%d %%" % round(100 * st["objectif"] / n) if n else "-",
                        st["stop"], n - st["objectif"] - st["stop"]))
    return "\n".join(lines)


def selftest():
    assert paris(dt.datetime(2026, 10, 27, 8, tzinfo=UTC)) == dt.datetime(2026, 10, 27, 9)  # winter: UTC+1
    assert paris(dt.datetime(2026, 7, 1, 8, tzinfo=UTC)) == dt.datetime(2026, 7, 1, 10)    # summer: UTC+2
    day, start = dt.date(2026, 10, 27), dt.time(9)
    p = lambda h, m: dt.datetime(2026, 10, 27, h, m)
    bars = [(p(9, 0), 1.10, 1.08, 1.09), (p(9, 5), 1.11, 1.09, 1.10), (p(9, 10), 1.10, 1.09, 1.095),
            (p(9, 15), 1.105, 1.09, 1.10), (p(9, 20), 1.12, 1.10, 1.115), (p(9, 25), 1.13, 1.11, 1.12),
            (p(9, 30), 1.14, 1.11, 1.13)]
    r = evaluate(bars, 5, day, start, 15, p(9, 40), max_stop=1.0)
    s = r["sig"]
    assert (r["high"], r["low"], r["nrange"], r["after"]) == (1.11, 1.08, 3, 4), r
    assert s["side"] == 1 and s["time"] == p(9, 25) and s["after"] == 2 and s["capped"], s
    assert round(s["stop"], 5) == 1.10385 and round(s["target"], 5) == 1.1373, s  # 1 % of 1.115, not the 0.02 to the midpoint
    assert s["result"] == "objectif" and s["bars"] == 2, s  # 9:30 high 1.14 >= 1.1373
    r = evaluate(bars, 5, day, start, 15, p(9, 40), max_stop=5.0)  # stop at the midpoint 1.095, target 1.155
    assert not r["sig"]["capped"] and round(r["sig"]["stop"], 5) == 1.095, r
    down = bars[:4] + [(p(9, 20), 1.09, 1.07, 1.075), (p(9, 25), 1.08, 1.04, 1.05)]
    s = evaluate(down, 5, day, start, 15, p(9, 30))["sig"]
    assert s["side"] == -1 and s["result"] == "objectif" and s["bars"] == 1, s  # short: risk 0.02, target 1.035
    assert evaluate(bars, 5, day, start, 15, p(9, 24))["sig"] is None  # the 9:20 bar is not complete yet
    assert evaluate(bars, 5, day, start, 15, p(9, 10))["status"] == "range pas fini"
    print("selftest ok")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="09:00", help="range start, Paris time (default 09:00)")
    p.add_argument("--minutes", type=int, default=15, help="range length (default 15)")
    p.add_argument("--max-stop", type=float, default=1.0, help="stop never further than this %% from the entry (default 1)")
    p.add_argument("--at", help="cut the clock at this Paris time today (HH:MM)")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    now = paris(dt.datetime.now(UTC))
    if a.at:
        now = min(now, dt.datetime.combine(now.date(), dt.time.fromisoformat(a.at)))
    start = dt.time.fromisoformat(a.start)
    print("Range d'ouverture %s + %d min (heure de Paris), stop max %.2g %%, objectif 2R. Données Yahoo gratuites (peuvent avoir du retard), à %s :"
          % (a.start, a.minutes, a.max_stop, now.strftime("%a %d/%m %H:%M")))
    found = 0
    for sym, (name, step) in SYMBOLS.items():
        if a.minutes % step:
            print("  %s : range de %d min impossible en bougies de %d min" % (name, a.minutes, step))
            continue
        try:
            bars = fetch(sym, step)
        except Exception as e:
            print("  %s : %s" % (name, e))
            continue
        r = evaluate(day_grid(bars, step, now.date()), step, now.date(), start, a.minutes, now, a.max_stop)
        found += bool(r.get("sig"))
        print(report(name, step, r, history(bars, step, start, a.minutes, now.date(), a.max_stop)))
    print("Un signal = un graphique qui a rempli une règle, pas un trade gagnant. Le passé ne garantit rien. Relancer avant d'agir.")
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
