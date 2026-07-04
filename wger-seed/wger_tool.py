#!/usr/bin/env python3
"""Wger nutrition CLI for Hermes agents. Stdlib only (urllib).

Reads WGER_URL and WGER_TOKEN from the environment or from a config.env
file sitting next to this script (KEY=VALUE lines). All output is plain
text meant to be read back by the agent and relayed to the user.

Subcommands:
  search <term>                 list matching foods (id, name, per-100g macros)
  log <term> <grams>            log <grams> of the best-matching food for today
  log-id <ingredient_id> <g>    log an exact ingredient id
  today                         today's totals (kcal/protein/carb/fat) + items
  undo                          delete the most recent diary entry
  weight <kg>                   log a bodyweight entry for today
"""
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None


def _load_config():
    here = os.path.dirname(os.path.abspath(__file__))
    cfg = {}
    path = os.path.join(here, "config.env")
    if os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip()
    url = os.environ.get("WGER_URL", cfg.get("WGER_URL", "http://10.0.0.122"))
    token = os.environ.get("WGER_TOKEN", cfg.get("WGER_TOKEN", ""))
    tz = os.environ.get("WGER_TZ", cfg.get("WGER_TZ", "America/New_York"))
    if not token:
        sys.exit("ERROR: WGER_TOKEN not set (env or config.env).")
    return url.rstrip("/"), token, tz


URL, TOKEN, TZ = _load_config()
LANG_EN = 2


def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(URL + path, data=data, method=method)
    req.add_header("Authorization", "Token " + TOKEN)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        sys.exit("ERROR: %s %s -> HTTP %s: %s" % (method, path, e.code, e.read().decode()[:300]))
    except urllib.error.URLError as e:
        sys.exit("ERROR: cannot reach wger at %s (%s)" % (URL, e))


def _today():
    if ZoneInfo:
        try:
            return datetime.now(ZoneInfo(TZ)).date()
        except Exception:
            pass
    return datetime.now().date()


def ingredient_by_id(iid):
    return api("GET", "/api/v2/ingredient/%s/" % iid)


def find(term):
    """Server-side fulltext/trigram search (scales to the full OFF catalog).

    Re-ranks the server's results so a whole-food exact/startswith match floats
    above branded products of the same name."""
    t = term.strip()
    q = urllib.parse.quote(t)
    d = api("GET", "/api/v2/ingredient/?name__search=%s&language=%d&limit=15" % (q, LANG_EN))
    items = d.get("results", [])
    tl = t.lower()
    items.sort(key=lambda i: (
        i["name"].lower() != tl,                  # exact name first
        not i["name"].lower().startswith(tl),     # then startswith
        len(i["name"]),                           # then shortest (least branded)
    ))
    return items


def find_barcode(code):
    d = api("GET", "/api/v2/ingredient/?code=%s" % urllib.parse.quote(str(code)))
    return d.get("results", [])


def get_log_plan():
    """Return the user's logging plan id, creating one if needed."""
    d = api("GET", "/api/v2/nutritionplan/?limit=100")
    plans = d.get("results", [])
    for p in plans:
        if p.get("only_logging"):
            return p["id"]
    if plans:
        return plans[0]["id"]
    p = api("POST", "/api/v2/nutritionplan/", {"description": "Daily Log", "only_logging": True})
    return p["id"]


def macros_for(ing, grams):
    f = grams / 100.0
    return {
        "kcal": round(float(ing["energy"]) * f),
        "protein": round(float(ing["protein"]) * f, 1),
        "carbs": round(float(ing["carbohydrates"]) * f, 1),
        "fat": round(float(ing["fat"]) * f, 1),
    }


def cmd_search(args):
    if not args:
        sys.exit("usage: search <term>")
    hits = find(" ".join(args))
    if not hits:
        print("No match for '%s'. Try a simpler/whole-food term, or add it in the wger web UI." % " ".join(args))
        return
    print("Matches (per 100 g):")
    for i in hits[:10]:
        print("  [%d] %s -- %s kcal, P%s C%s F%s" % (
            i["id"], i["name"], i["energy"], i["protein"], i["carbohydrates"], i["fat"]))


def _log_ingredient(ing, grams):
    plan = get_log_plan()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    api("POST", "/api/v2/nutritiondiary/", {
        "plan": plan, "ingredient": ing["id"], "amount": grams, "datetime": now})
    m = macros_for(ing, grams)
    print("Logged: %g g %s -> %d kcal (P%s C%s F%s)" % (
        grams, ing["name"], m["kcal"], m["protein"], m["carbs"], m["fat"]))
    _print_today(plan)


def cmd_log(args):
    if len(args) < 2:
        sys.exit("usage: log <term> <grams>")
    grams = float(args[-1])
    term = " ".join(args[:-1])
    hits = find(term)
    if not hits:
        sys.exit("No food matches '%s'. Use search, pick a closer whole-food term, or add it in the web UI." % term)
    ing = hits[0]
    if len(hits) > 1 and ing["name"].lower() != term.strip().lower():
        alts = ", ".join("%s[%d]" % (h["name"], h["id"]) for h in hits[1:4])
        print("(matched '%s'; other options: %s)" % (ing["name"], alts))
    _log_ingredient(ing, grams)


def cmd_log_id(args):
    if len(args) != 2:
        sys.exit("usage: log-id <ingredient_id> <grams>")
    ing = ingredient_by_id(args[0])
    _log_ingredient(ing, float(args[1]))


def cmd_barcode(args):
    if len(args) < 1:
        sys.exit("usage: barcode <code> [grams]")
    hits = find_barcode(args[0])
    if not hits:
        print("No product with barcode %s. (Only present if the OFF catalog is imported.)" % args[0])
        return
    ing = hits[0]
    if len(args) == 2:
        _log_ingredient(ing, float(args[1]))
    else:
        print("[%d] %s -- %s kcal/100g, P%s C%s F%s" % (
            ing["id"], ing["name"], ing["energy"], ing["protein"],
            ing["carbohydrates"], ing["fat"]))


def _entries_today(plan):
    d = api("GET", "/api/v2/nutritiondiary/?plan=%d&limit=500" % plan)
    today = _today().isoformat()
    return [e for e in d.get("results", []) if str(e["datetime"])[:10] == today]


def _print_today(plan=None):
    if plan is None:
        plan = get_log_plan()
    entries = _entries_today(plan)
    if not entries:
        print("Today: nothing logged yet.")
        return
    cache = {}
    tot = {"kcal": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
    lines = []
    for e in entries:
        iid = e["ingredient"]
        if iid not in cache:
            cache[iid] = ingredient_by_id(iid)
        ing = cache[iid]
        grams = float(e["amount"])
        m = macros_for(ing, grams)
        for k in tot:
            tot[k] += m[k]
        lines.append("  %g g %s -- %d kcal" % (grams, ing["name"], m["kcal"]))
    print("Today's total: %d kcal  |  P %.0f g  C %.0f g  F %.0f g  (%d items)" % (
        round(tot["kcal"]), tot["protein"], tot["carbs"], tot["fat"], len(entries)))
    for ln in lines:
        print(ln)


def cmd_today(args):
    _print_today()


def cmd_undo(args):
    plan = get_log_plan()
    d = api("GET", "/api/v2/nutritiondiary/?plan=%d&ordering=-datetime&limit=1" % plan)
    res = d.get("results", [])
    if not res:
        print("Nothing to undo.")
        return
    e = res[0]
    api("DELETE", "/api/v2/nutritiondiary/%d/" % e["id"])
    print("Removed last entry (id %d, %g g, %s)." % (e["id"], float(e["amount"]), str(e["datetime"])[:16]))
    _print_today(plan)


def cmd_weight(args):
    if len(args) != 1:
        sys.exit("usage: weight <kg>")
    today = _today().isoformat()
    api("POST", "/api/v2/weightentry/", {"date": today, "weight": float(args[0])})
    print("Logged bodyweight %s kg for %s." % (args[0], today))


CMDS = {
    "search": cmd_search, "log": cmd_log, "log-id": cmd_log_id,
    "barcode": cmd_barcode, "today": cmd_today, "undo": cmd_undo,
    "weight": cmd_weight,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        sys.exit("usage: wger_tool.py {%s} [args]" % "|".join(CMDS))
    CMDS[sys.argv[1]](sys.argv[2:])
