#!/usr/bin/env python3
"""
Local Tech Lab :: HTTP Verbs Lab -- backend
-------------------------------------------
Intentionally vulnerable training target. Educational use only.
- Python stdlib only (no pip install).
- Binds to loopback by default. Do NOT expose it to a network.
- No filesystem writes, no command execution: all state lives in memory.

Flags are derived with HMAC(LTL_SECRET, mission_id), so they are not stored
in the repository and change whenever the secret changes (./lab.sh reset).
"""
import hashlib
import hmac
import json
import os
import re
import socketserver
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

SECRET = os.environ.get("LTL_SECRET", "local-tech-lab-dev-secret").encode()
SOCKET = os.environ.get("LTL_SOCKET", "/tmp/ltl-backend.sock")      # main API (behind nginx)
DEBUG_BIND = os.environ.get("LTL_DEBUG_BIND", "127.0.0.1")
DEBUG_PORT = int(os.environ.get("LTL_DEBUG_PORT", "9000"))          # forgotten debug listener
MAX_BODY = 64 * 1024
MAX_FILES = 32

# --------------------------------------------------------------------------
# Missions / flags
# --------------------------------------------------------------------------
MISSIONS = [
    {"id": "m1", "verb": "GET", "difficulty": "Easy", "points": 10,
     "title": "Intern's Notes", "endpoint": "/api/m1/notes",
     "objective": "The intern left notes on the server. One of them was never listed."},
    {"id": "m2", "verb": "HEAD", "difficulty": "Easy", "points": 10,
     "title": "Silent Vault", "endpoint": "/api/m2/vault",
     "objective": "The vault claims to be empty. Read what it does not say out loud."},
    {"id": "m3", "verb": "OPTIONS", "difficulty": "Easy", "points": 20,
     "title": "Gatekeeper", "endpoint": "/api/m3/gate",
     "objective": "Ask the gate what it understands. It speaks a dialect you may not know."},
    {"id": "m4", "verb": "POST", "difficulty": "Easy", "points": 20,
     "title": "Operator Login", "endpoint": "/api/m4/login",
     "objective": "Find the operator credentials somewhere in the lab, then authenticate."},
    {"id": "m5", "verb": "PUT", "difficulty": "Medium", "points": 20,
     "title": "Compliance Upload", "endpoint": "/api/m5/files",
     "objective": "Upload ltl-check.txt stating LOCAL TECH LAB. Idempotently."},
    {"id": "m6", "verb": "PATCH", "difficulty": "Medium", "points": 30,
     "title": "Partial Promotion", "endpoint": "/api/m6/profile",
     "objective": "You are a guest. Fix that -- partially. (requires token)"},
    {"id": "m7", "verb": "DELETE", "difficulty": "Medium", "points": 30,
     "title": "Ghost Session", "endpoint": "/api/m7/sessions",
     "objective": "Someone else is logged in as you. Remove the ghost. (requires token)"},
    {"id": "m8", "verb": "TRACE", "difficulty": "Hard", "points": 40,
     "title": "Proxy Whispers", "endpoint": "/api/m8/echo",
     "objective": "nginx kills TRACE at the edge. Somewhere, diagnostics are still listening."},
    {"id": "m9", "verb": "POST + override", "difficulty": "Hard", "points": 50,
     "title": "Edge Bypass", "endpoint": "/api/m9/records/42",
     "objective": "DELETE is forbidden at the edge. Record 42 must go anyway."},
]
SLUGS = {
    "m1": "get_recon", "m2": "head_hunter", "m3": "options_scout",
    "m4": "post_auth", "m5": "put_upload", "m6": "patch_privesc",
    "m7": "delete_ghost", "m8": "trace_leak", "m9": "verb_tampering",
}
POINTS = {m["id"]: m["points"] for m in MISSIONS}


def _h(label: str) -> str:
    return hmac.new(SECRET, label.encode(), hashlib.sha256).hexdigest()


def flag(mid: str) -> str:
    return "LTL{%s_%s}" % (SLUGS[mid], _h(mid)[:12])


FLAGS = {mid: flag(mid) for mid in SLUGS}
TOKEN = "ltl-" + _h("operator-token")[:24]
OPERATOR_USER = "operator"
OPERATOR_PASS = "L0cal-T3ch!2026"

# --------------------------------------------------------------------------
# In-memory state
# --------------------------------------------------------------------------
LOCK = threading.Lock()
SOLVED = set()
FILES = {}
PROFILE = {"user": OPERATOR_USER, "display_name": "Operator", "role": "guest"}

NOTES = {
    1: {"id": 1, "title": "Welcome", "body": "Welcome to Local Tech Lab. Mission list: GET /api/missions"},
    2: {"id": 2, "title": "TODO", "body": "Rotate VPN keys. Disable the diagnostics listener on 127.0.0.1:9000 before going live."},
    3: {"id": 3, "title": "Lunch", "body": "Tacos on Friday."},
    1337: {"id": 1337, "title": "DO NOT SHARE",
           "body": "operator creds -> user: %s / pass: %s" % (OPERATOR_USER, OPERATOR_PASS),
           "flag": FLAGS["m1"]},
}

SESSIONS = [
    {"id": "s-1001", "user": OPERATOR_USER, "ip": "127.0.0.1", "current": True},
    {"id": "s-ghost", "user": OPERATOR_USER, "ip": "203.0.113.66", "current": False,
     "note": "unrecognized device"},
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def authed(h) -> bool:
    tok = h.headers.get("X-LTL-Token", "")
    auth = h.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        tok = tok or auth[7:].strip()
    return bool(tok) and hmac.compare_digest(tok.encode(), TOKEN.encode())


def need_auth(h) -> bool:
    if authed(h):
        return True
    h.reply(401, {"error": "missing or invalid token",
                  "hint": "send X-LTL-Token (you get one in mission m4)"})
    return False


def json_body(h, body):
    ctype = (h.headers.get("Content-Type") or "").lower()
    if "json" not in ctype:
        h.reply(415, {"error": "unsupported media type", "expected": "application/json"})
        return None
    try:
        data = json.loads(body or b"{}")
    except (ValueError, UnicodeDecodeError):
        h.reply(400, {"error": "malformed JSON"})
        return None
    if not isinstance(data, dict):
        h.reply(400, {"error": "JSON object expected"})
        return None
    return data


# --------------------------------------------------------------------------
# Route handlers: fn(h, method, match, query, body)
# --------------------------------------------------------------------------
def r_index(h, method, m, q, body):
    h.reply(200, {
        "lab": "Local Tech Lab :: HTTP Verbs",
        "flag_format": "LTL{...}",
        "submit": "POST /api/submit  {\"flag\": \"LTL{...}\"}",
        "scoreboard": "GET /api/scoreboard",
        "missions": MISSIONS,
    })


def r_m1(h, method, m, q, body):
    if "id" not in q:
        visible = [{"id": n["id"], "title": n["title"]} for k, n in NOTES.items() if k < 1000]
        return h.reply(200, {"notes": visible, "usage": "GET /api/m1/notes?id=<n>",
                             "hint": "not every note is listed"})
    try:
        nid = int(q["id"][0])
    except ValueError:
        return h.reply(400, {"error": "id must be an integer"})
    note = NOTES.get(nid)
    if not note:
        return h.reply(404, {"error": "note not found", "id": nid})
    h.reply(200, note)


def r_m2(h, method, m, q, body):
    hdrs = {"X-Vault-Status": "sealed"}
    if h.is_head:
        hdrs["X-LTL-Flag"] = FLAGS["m2"]
    h.reply(200, {"vault": "empty", "msg": "nothing to see in the body..."}, hdrs)


def r_m3(h, method, m, q, body):
    if method == "LTLSCAN":
        return h.reply(200, {"gate": "open", "flag": FLAGS["m3"]})
    h.reply(200, {"gate": "sealed", "msg": "the gate only opens with the right word"})


def r_m4(h, method, m, q, body):
    data = json_body(h, body)
    if data is None:
        return
    user, pwd = str(data.get("user", "")), str(data.get("pass", ""))
    ok = hmac.compare_digest(user.encode(), OPERATOR_USER.encode()) & \
        hmac.compare_digest(pwd.encode(), OPERATOR_PASS.encode())
    if not ok:
        return h.reply(401, {"error": "invalid credentials"})
    h.reply(200, {"auth": "ok", "token": TOKEN, "use_as": "X-LTL-Token header",
                  "flag": FLAGS["m4"]})


def r_m5(h, method, m, q, body):
    name = m.group(1)
    if method == "GET":
        with LOCK:
            if not name:
                return h.reply(200, {"files": sorted(FILES)})
            if name not in FILES:
                return h.reply(404, {"error": "file not found"})
            return h.reply(200, raw=FILES[name], ctype="text/plain; charset=utf-8")
    # PUT
    if not name:
        return h.reply(400, {"error": "PUT needs a full resource URI: /api/m5/files/<name>"})
    with LOCK:
        created = name not in FILES
        if created and len(FILES) >= MAX_FILES:
            return h.reply(507, {"error": "lab storage full, restart the lab"})
        FILES[name] = body
    resp = {"resource": "/api/m5/files/" + name, "bytes": len(body),
            "result": "created" if created else "replaced"}
    if name == "ltl-check.txt" and b"LOCAL TECH LAB" in body:
        resp["compliance"] = "accepted"
        resp["flag"] = FLAGS["m5"]
    h.reply(201 if created else 200, resp, {"Location": "/api/m5/files/" + name})


def r_m6(h, method, m, q, body):
    if not need_auth(h):
        return
    if method == "GET":
        with LOCK:
            return h.reply(200, dict(PROFILE))
    data = json_body(h, body)
    if data is None:
        return
    with LOCK:
        # VULN (mass assignment): "role" should never be client-writable.
        for key in ("display_name", "role"):
            if key in data:
                PROFILE[key] = str(data[key])[:64]
        resp = {"profile": dict(PROFILE)}
    if resp["profile"]["role"] == "admin":
        resp["flag"] = FLAGS["m6"]
    h.reply(200, resp)


def r_m7(h, method, m, q, body):
    if not need_auth(h):
        return
    sid = m.group(1)
    if method == "GET":
        if sid:
            s = next((s for s in SESSIONS if s["id"] == sid), None)
            return h.reply(200, s) if s else h.reply(404, {"error": "session not found"})
        return h.reply(200, {"sessions": SESSIONS})
    if not sid:
        return h.reply(400, {"error": "DELETE needs a session id: /api/m7/sessions/<id>"})
    if sid == "s-ghost":
        return h.reply(200, {"deleted": sid, "msg": "ghost session revoked", "flag": FLAGS["m7"]})
    if sid == "s-1001":
        return h.reply(409, {"error": "refusing to delete your current session"})
    h.reply(404, {"error": "session not found"})


def r_m8(h, method, m, q, body):
    if method == "TRACE":
        # VULN (XST): dumps the request object *after* internal middleware
        # enriched it with a service credential.
        lines = [h.requestline] + ["%s: %s" % (k, v) for k, v in h.headers.items()]
        lines += ["%s: %s" % kv for kv in h.internal.items()]
        return h.reply(200, raw=("\r\n".join(lines) + "\r\n").encode(), ctype="message/http")
    h.reply(200, {"service": "echo", "listener": h.listener,
                  "msg": "request diagnostics are enabled for some verbs on the diagnostics listener"})


def r_m9(h, method, m, q, body):
    rid = int(m.group(1))
    if rid != 42:
        return h.reply(404, {"error": "record not found"})
    if method == "GET":
        return h.reply(200, {"id": 42, "status": "active", "owner": "legacy-app"})
    if method == "POST":
        return h.reply(400, {"error": "nothing to create here"})
    # DELETE (only reachable through X-HTTP-Method-Override behind nginx)
    h.reply(200, {"deleted": 42, "msg": "edge policy bypassed", "flag": FLAGS["m9"]})


def r_submit(h, method, m, q, body):
    data = json_body(h, body)
    if data is None:
        return
    sub = str(data.get("flag", "")).strip()
    for mid, f in FLAGS.items():
        if hmac.compare_digest(sub.encode(), f.encode()):
            with LOCK:
                new = mid not in SOLVED
                SOLVED.add(mid)
            return h.reply(200, {"correct": True, "mission": mid, "points": POINTS[mid],
                                 "first_blood": new})
    h.reply(200, {"correct": False})


def r_scoreboard(h, method, m, q, body):
    with LOCK:
        solved = sorted(SOLVED)
    h.reply(200, {"solved": len(solved), "total_missions": len(MISSIONS),
                  "points": sum(POINTS[s] for s in solved),
                  "max_points": sum(POINTS.values()), "missions_solved": solved,
                  "status": "PWNED" if len(solved) == len(MISSIONS) else "in progress"})


ROUTES = [
    (re.compile(r"/|/api|/api/missions"), ("GET", "OPTIONS"), r_index),
    (re.compile(r"/api/m1/notes"), ("GET", "OPTIONS"), r_m1),
    (re.compile(r"/api/m2/vault"), ("GET", "HEAD", "OPTIONS"), r_m2),
    (re.compile(r"/api/m3/gate"), ("GET", "OPTIONS", "LTLSCAN"), r_m3),
    (re.compile(r"/api/m4/login"), ("POST", "OPTIONS"), r_m4),
    (re.compile(r"/api/m5/files(?:/([A-Za-z0-9._-]{1,64}))?"), ("GET", "PUT", "OPTIONS"), r_m5),
    (re.compile(r"/api/m6/profile"), ("GET", "PATCH", "OPTIONS"), r_m6),
    (re.compile(r"/api/m7/sessions(?:/([A-Za-z0-9-]{1,32}))?"), ("GET", "DELETE", "OPTIONS"), r_m7),
    (re.compile(r"/api/m8/echo"), ("GET", "TRACE", "OPTIONS"), r_m8),
    (re.compile(r"/api/m9/records/(\d{1,6})"), ("GET", "POST", "DELETE", "OPTIONS"), r_m9),
    (re.compile(r"/api/submit"), ("POST", "OPTIONS"), r_submit),
    (re.compile(r"/api/scoreboard"), ("GET", "OPTIONS"), r_scoreboard),
]


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "LTL-Backend/1.0"
    sys_version = ""
    is_head = False
    listener = "main"
    internal = {}

    def version_string(self):
        return self.server_version

    def address_string(self):
        return self.listener

    def log_message(self, fmt, *args):
        sys.stderr.write("[ltl] %s\n" % (fmt % args))

    # Every verb (standard or custom, e.g. LTLSCAN) lands in route().
    def __getattr__(self, name):
        if name.startswith("do_"):
            return lambda: self.route(name[3:])
        raise AttributeError(name)

    def reply(self, status, obj=None, headers=None, raw=None, ctype="application/json"):
        if raw is None and obj is not None:
            raw = (json.dumps(obj, indent=2) + "\n").encode()
        raw = raw or b""
        self.send_response(status)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Cache-Control", "no-store")
        if status != 204:
            if raw:
                self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if raw and status != 204 and not self.is_head:
            self.wfile.write(raw)

    def route(self, method):
        method = method.upper()
        self.is_head = method == "HEAD"
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self.close_connection = True
            return self.reply(400, {"error": "bad Content-Length"})
        if length < 0 or length > MAX_BODY:
            self.close_connection = True
            return self.reply(413, {"error": "payload too large"})
        body = self.rfile.read(length) if length else b""

        url = urlsplit(self.path)
        path = url.path.rstrip("/") or "/"
        query = parse_qs(url.query)

        if self.listener == "debug":
            # "Internal auth middleware": enriches every request with a service token.
            self.internal = {"X-LTL-Internal-Auth": FLAGS["m8"]}
            if path == "/":
                return self.reply(200, {"service": "ltl-diagnostics", "endpoints": ["/api/m8/echo"]})
            if not path.startswith("/api/m8/"):
                return self.reply(404, {"error": "diagnostics listener: only /api/m8/*"})

        # VULN (verb tampering): the legacy API trusts X-HTTP-Method-Override.
        if method == "POST" and path.startswith("/api/m9/"):
            override = self.headers.get("X-HTTP-Method-Override", "").strip().upper()
            if override:
                method = override

        for rx, allowed, fn in ROUTES:
            match = rx.fullmatch(path)
            if not match:
                continue
            allow = list(allowed)
            if "GET" in allow and "HEAD" not in allow:
                allow.insert(allow.index("GET") + 1, "HEAD")
            if method == "OPTIONS":
                return self.reply(204, headers={"Allow": ", ".join(allow)})
            if method not in allow:
                return self.reply(405, {"error": "method not allowed", "method": method,
                                        "allowed": allow}, {"Allow": ", ".join(allow)})
            if method == "HEAD":
                method = "GET"
            return fn(self, method, match, query, body)
        self.reply(404, {"error": "not found", "path": path})


class DebugHandler(Handler):
    listener = "debug"


class UnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--flag":
        print(FLAGS[sys.argv[2]])
        return
    if len(sys.argv) == 2 and sys.argv[1] == "--flags":
        for mid, f in FLAGS.items():
            print(mid, f)
        return
    if os.path.exists(SOCKET):
        os.unlink(SOCKET)
    main_srv = UnixHTTPServer(SOCKET, Handler)
    os.chmod(SOCKET, 0o660)
    dbg_srv = ThreadingHTTPServer((DEBUG_BIND, DEBUG_PORT), DebugHandler)
    dbg_srv.daemon_threads = True
    threading.Thread(target=dbg_srv.serve_forever, daemon=True).start()
    print("[ltl] main API on unix:%s | diagnostics on %s:%d" % (SOCKET, DEBUG_BIND, DEBUG_PORT), flush=True)
    try:
        main_srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if os.path.exists(SOCKET):
            os.unlink(SOCKET)


if __name__ == "__main__":
    main()
