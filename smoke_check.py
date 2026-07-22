"""Automated smoke check: MyHrms Android app vs AttendanceSystem Flask backend.

Checks, in order:
  1. Every endpoint the app calls (ApiService.kt) is registered in Flask.
  2. Every GET endpoint responds without a 500 on the live server (localhost:5051).
  3. /menus contains every menu_key the dashboard expects (MENUS.md), and a
     superadmin user sees them all via /menu-permissions.

Read-only: GETs are executed; POST/PUT/DELETE are only checked for registration.
Run:  .venv\\Scripts\\python smoke_check.py
"""
import datetime
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "http://localhost:5051"
TODAY = datetime.date.today().isoformat()
APISERVICE = r"E:\sjm\MyHrms\app\src\main\java\com\example\myhrms\api\ApiService.kt"
APIROUTES = r"E:\sjm\MyHrms\app\src\main\java\com\example\myhrms\api\ApiRoutes.kt"

# Leaf menu keys + dashboard cards from MyHrms MENUS.md
EXPECTED_MENU_KEYS = [
    "card_present", "card_jute", "card_spg", "card_winding", "card_others", "card_bales",
    "grp_attendance", "menu_attendance_dashboard", "menu_onboarding", "menu_attendance_entry",
    "menu_attendance_reports", "grp_other_entries", "menu_leave_entries",
    "grp_production", "grp_jute", "menu_jute_received", "menu_assorting_entry",
    "menu_jute_mukam_received", "grp_spreader_entry", "menu_production_entry",
    "menu_issue_entry", "menu_drawing_meter_entry", "menu_spinning_doff_entry",
    "grp_doff_entry", "menu_spellwise_frame_entry", "menu_spg_doff_entry",
    "menu_spg_doff_entry1", "menu_spg_running_hours", "grp_winding_entry",
    "menu_winding_entry", "menu_cont_winding_entry", "grp_others_entry",
    "menu_mechine_entry", "menu_newmechine_entry", "menu_weaving_entry",
    "grp_finishing_entry", "menu_other_entries", "menu_bales_production_entry",
    "menu_bales_issue_entry", "grp_stocks", "menu_roll_stock", "menu_weight_entry",
]

# Generic query params appended to every GET; handlers ignore what they don't read.
DEFAULT_QUERY = {
    "date": TODAY, "from_date": TODAY, "to_date": TODAY, "from": TODAY, "to": TODAY,
    "start_date": TODAY, "end_date": TODAY, "entry_date": TODAY, "report_date": TODAY,
    "tran_date": TODAY, "doff_date": TODAY,
    "spell_id": "1", "shift": "A", "spell": "1",
    "mc_code": "1", "machine_code": "1", "mechine_code": "1", "machine_id": "1",
    "quality_id": "1", "shed_id": "1", "dept_id": "1", "sub_dept_id": "1",
    "trolly_no": "1", "selector_id": "1", "customer_id": "1", "spool_type_id": "1",
    "q": "a", "search": "a", "page": "1", "limit": "5", "role_id": "15",
}

# Per-path extra/override params, filled in as 400s surface.
PATH_QUERY_OVERRIDES = {}

# Declared in ApiService.kt but dead code: never called from any activity
# (getAttendanceById, getDoffLastEmp) or last-resort legacy fallbacks behind
# working masters/get_company + get_branch (companies, branches).
KNOWN_DEAD_APP_ENDPOINTS = {
    ("GET", "/attendance/{attendance_id}"),
    ("GET", "/branches"),
    ("GET", "/companies"),
    ("GET", "/doff/last-emp"),
}


def norm(path):
    """Normalize path params so /x/<int:id> and /x/{id} compare equal."""
    return re.sub(r"[<{][^>}]*[>}]", "<*>", path)


def flask_route_map():
    from src import create_app
    routes = {}
    for rule in create_app().url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        methods = {m for m in rule.methods if m not in ("HEAD", "OPTIONS")}
        routes.setdefault(norm(str(rule)), [set(), str(rule)])[0].update(methods)
    return routes  # norm_path -> [methods, raw_rule]


def app_endpoints():
    consts = dict(re.findall(r'const val (\w+)\s*=\s*"([^"]*)"',
                             open(APIROUTES, encoding="utf-8").read()))
    for _ in range(3):  # resolve $NAME refs between constants
        consts = {k: re.sub(r"\$\{?(\w+)\}?", lambda m: consts.get(m.group(1), m.group(0)), v)
                  for k, v in consts.items()}
    eps = set()
    for meth, arg in re.findall(r'@(GET|POST|PUT|DELETE)\(\s*([^)\n]+?)\s*\)',
                                open(APISERVICE, encoding="utf-8").read()):
        arg = arg.strip()
        if arg.startswith('"'):
            path = arg.strip('"')
            path = re.sub(r"\$\{?ApiRoutes\.(\w+)\}?",
                          lambda m: consts.get(m.group(1), "?UNRESOLVED?"), path)
        elif arg.startswith("ApiRoutes."):
            path = consts.get(arg.split(".", 1)[1], "?UNRESOLVED?")
        else:
            path = "?UNRESOLVED?" + arg
        eps.add((meth, "/" + path.lstrip("/")))
    return sorted(eps)


def http_get(path_qs, timeout=60):
    try:
        with urllib.request.urlopen(BASE + path_qs, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return None, str(e).encode()


def get_json(path_qs):
    code, body = http_get(path_qs)
    try:
        return code, json.loads(body)
    except Exception:
        return code, None


def main():
    print(f"Smoke check @ {BASE}  date={TODAY}\n")
    code, _ = http_get("/", timeout=10)
    if code != 200:
        sys.exit(f"FATAL: server not reachable at {BASE} (got {code})")

    flask_routes = flask_route_map()
    app_eps = app_endpoints()

    # ── 1. app endpoint → flask route cross-check ──────────────────────────
    missing = []
    for meth, path in app_eps:
        if (meth, path) in KNOWN_DEAD_APP_ENDPOINTS:
            continue
        entry = flask_routes.get(norm(path))
        if not entry or meth not in entry[0]:
            missing.append((meth, path))
    print(f"[1] App calls {len(app_eps)} endpoints; "
          f"{len(app_eps) - len(missing)} registered in Flask, {len(missing)} MISSING")
    for meth, path in missing:
        print(f"    MISSING  {meth:6s} {path}")

    # sample emp_code for path substitution
    _, emp_json = get_json("/employees?limit=1&page=1")
    emp_code = "1"
    if isinstance(emp_json, dict):
        rows = emp_json.get("employees") or emp_json.get("data") or []
        if rows and isinstance(rows, list) and rows[0].get("emp_code"):
            emp_code = str(rows[0]["emp_code"])

    # bootstrap real ids from the live masters so param-guarded routes execute
    def first_id(path_qs, *keys):
        _, j = get_json(path_qs)
        for k in keys:
            v = j.get(k) if isinstance(j, dict) else None
            if isinstance(v, list) and v:
                item = v[0]
                if isinstance(item, dict):
                    for idk in ("id", "co_id", "branch_id", "spell_id"):
                        if item.get(idk) is not None:
                            return str(item[idk])
                else:
                    return str(item)
        return "1"

    co_id = first_id("/masters/get_company", "companies", "data", "company")
    branch_id = first_id(f"/masters/get_branch?co_id={co_id}", "branches", "data")
    spell_id = first_id(f"/spells?branch_id={branch_id}", "spells", "data")
    shed_type = first_id("/drawing/sheds", "sheds")
    DEFAULT_QUERY.update({
        "branch_id": branch_id, "co_id": co_id, "company_id": co_id,
        "spell_id": spell_id, "shed_type": shed_type, "metric": "hands",
        "mc_id": "1", "mc_no": "1", "eb_no": emp_code, "eb_id": "1",
        "designation_id": "1", "fng_quality_id": "1", "emp_code": emp_code,
    })
    print(f"    bootstrap: co_id={co_id} branch_id={branch_id} "
          f"spell_id={spell_id} shed_type={shed_type} emp_code={emp_code}")

    # ── 2. live GET smoke test of every flask GET route ────────────────────
    def probe(item):
        norm_path, (methods, raw_rule) = item
        path = re.sub(r"<(?:\w+:)?(\w*emp_code\w*)>", emp_code, raw_rule)
        path = re.sub(r"<[^>]+>", "1", path)
        q = dict(DEFAULT_QUERY)
        q.update(PATH_QUERY_OVERRIDES.get(norm_path, {}))
        code, body = http_get(path + "?" + urllib.parse.urlencode(q))
        snippet = body[:120].decode("utf-8", "replace").replace("\n", " ")
        print(f"    probed {code}  {raw_rule}", flush=True)
        return raw_rule, code, snippet

    gets = [it for it in sorted(flask_routes.items()) if "GET" in it[1][0]]
    results = {"PASS": [], "PARAM": [], "EMPTY": [], "FAIL": [], "DOWN": []}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for raw_rule, code, snippet in pool.map(probe, gets):
            if code is None:
                results["DOWN"].append((raw_rule, snippet))
            elif code == 500:
                results["FAIL"].append((raw_rule, snippet))
            elif code == 400:
                results["PARAM"].append((raw_rule, snippet))
            elif code == 404:
                results["EMPTY"].append((raw_rule, snippet))
            else:
                results["PASS"].append((raw_rule, f"HTTP {code}"))
    total = sum(len(v) for v in results.values())
    print(f"\n[2] Live GET smoke test: {total} routes  "
          f"PASS={len(results['PASS'])} PARAM(400)={len(results['PARAM'])} "
          f"EMPTY(404)={len(results['EMPTY'])} FAIL(500)={len(results['FAIL'])} "
          f"UNREACHABLE={len(results['DOWN'])}")
    for tag in ("FAIL", "DOWN", "PARAM", "EMPTY"):
        for rule, snippet in results[tag]:
            print(f"    {tag:6s} {rule}\n           {snippet}")

    # ── 3. menus + permissions ─────────────────────────────────────────────
    _, menus_json = get_json("/menus")
    db_keys = {m["menu_key"] for m in (menus_json or {}).get("menus", [])}
    absent = [k for k in EXPECTED_MENU_KEYS if k not in db_keys]
    print(f"\n[3] /menus: {len(db_keys)} active menus in DB; "
          f"expected {len(EXPECTED_MENU_KEYS)}; missing {len(absent)}")

    sa_user = None
    try:
        from db import get_db
        dbconn = get_db()
        cur = dbconn.cursor()
        if absent:
            ph = ",".join(["%s"] * len(absent))
            cur.execute(f"SELECT menu_key, is_active FROM menus WHERE menu_key IN ({ph})",
                        absent)
            found = dict(cur.fetchall())
            for k in absent:
                state = ("INACTIVE (is_active=0)" if k in found and not found[k]
                         else "ACTIVE?" if k in found else "NOT IN DB AT ALL")
                print(f"    MISSING MENU  {k}  [{state}]")
        cur.execute("SELECT user_id FROM user_role_map WHERE role_id=15 LIMIT 1")
        row = cur.fetchone()
        sa_user = row and row[0]
        cur.close()
        dbconn.close()
    except Exception as e:
        print(f"    (DB lookup failed: {e})")
        for k in absent:
            print(f"    MISSING MENU  {k}")
    if sa_user:
        _, perm_json = get_json(f"/menu-permissions?user_id={sa_user}")
        visible = {m["menu_key"] for m in (perm_json or {}).get("menus", [])}
        hidden = [k for k in EXPECTED_MENU_KEYS if k in db_keys and k not in visible]
        print(f"    superadmin user_id={sa_user} sees {len(visible)} menus; "
              f"{len(hidden)} expected-but-hidden")
        for k in hidden:
            print(f"    HIDDEN FOR SUPERADMIN  {k}")

    bad = len(missing) + len(results["FAIL"]) + len(results["DOWN"]) + len(absent)
    print(f"\n{'ALL OK' if bad == 0 else f'{bad} PROBLEM(S) FOUND'} "
          f"(POST/PUT/DELETE verified as registered only — not executed)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
