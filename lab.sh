#!/usr/bin/env bash
# Local Tech Lab :: HTTP Verbs -- lifecycle manager
# Usage: ./lab.sh start|stop|restart|status|reset|flags|logs
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="$ROOT/.run"
PORT="${LTL_PORT:-8080}"
DPORT="${LTL_DEBUG_PORT:-9000}"
BIND="${LTL_BIND:-127.0.0.1}"
BASE="http://127.0.0.1:$PORT"

G=$'\e[1;32m'; R=$'\e[1;31m'; C=$'\e[1;36m'; N=$'\e[0m'
ok()   { printf '%s[+]%s %s\n' "$G" "$N" "$*"; }
err()  { printf '%s[-]%s %s\n' "$R" "$N" "$*" >&2; }
info() { printf '%s[*]%s %s\n' "$C" "$N" "$*"; }

banner() {
cat <<'EOF'
  _                    _   _____         _       _          _
 | |    ___   ___ __ _| | |_   _|__  ___| |__   | |    __ _| |__
 | |   / _ \ / __/ _` | |   | |/ _ \/ __| '_ \  | |   / _` | '_ \
 | |__| (_) | (_| (_| | |   | |  __/ (__| | | | | |__| (_| | |_) |
 |_____\___/ \___\__,_|_|   |_|\___|\___|_| |_| |_____\__,_|_.__/
                     :: HTTP Verbs Lab ::
EOF
}

find_nginx() {
  NGINX="$(command -v nginx 2>/dev/null || true)"
  if [ -z "$NGINX" ] && [ -x /usr/sbin/nginx ]; then NGINX=/usr/sbin/nginx; fi
  if [ -z "$NGINX" ]; then
    err "nginx no encontrado. Instala con: sudo apt install -y nginx-light  (o nginx)"; exit 1
  fi
}

need() { command -v "$1" >/dev/null 2>&1 || { err "falta '$1' (sudo apt install -y $2)"; exit 1; }; }

alive() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }

load_secret() {
  mkdir -p "$RUN/tmp"
  if [ ! -s "$RUN/secret" ]; then
    (umask 077; python3 -c 'import secrets; print(secrets.token_hex(16))' > "$RUN/secret")
  fi
  LTL_SECRET="$(cat "$RUN/secret")"
  export LTL_SECRET LTL_SOCKET="$RUN/backend.sock" LTL_DEBUG_PORT="$DPORT"
}

render() {
  local userline=""
  [ "$(id -u)" -eq 0 ] && userline="user root;"
  sed -e "s|@RUN@|$RUN|g" -e "s|@PORT@|$PORT|g" \
      -e "s|@BIND@|$BIND|g" -e "s|@USER@|$userline|g" \
      "$ROOT/nginx/nginx.conf.tpl" > "$RUN/nginx.conf"
  "$NGINX" -t -q -p "$RUN" -e "$RUN/error.log" -c "$RUN/nginx.conf"
}

start() {
  banner
  need python3 python3; need curl curl; find_nginx
  if alive "$RUN/backend.pid" || alive "$RUN/nginx.pid"; then
    info "el lab ya está corriendo ($BASE)"; return 0
  fi
  load_secret
  render
  nohup python3 "$ROOT/app/server.py" >"$RUN/backend.log" 2>&1 &
  echo $! > "$RUN/backend.pid"
  "$NGINX" -p "$RUN" -e "$RUN/error.log" -c "$RUN/nginx.conf"
  for _ in $(seq 1 30); do
    if curl -fs -o /dev/null "$BASE/api/missions"; then
      ok "Local Tech Lab arriba en $BASE"
      info "empieza con:  curl -s $BASE/api/missions"
      return 0
    fi
    sleep 0.2
  done
  err "el lab no respondió. Revisa .run/backend.log y .run/error.log"; stop; exit 1
}

stop() {
  if alive "$RUN/nginx.pid"; then kill "$(cat "$RUN/nginx.pid")" && ok "nginx detenido"; fi
  if alive "$RUN/backend.pid"; then kill "$(cat "$RUN/backend.pid")" && ok "backend detenido"; fi
  rm -f "$RUN/backend.pid" "$RUN/backend.sock"
}

status() {
  alive "$RUN/nginx.pid"   && ok "nginx   pid $(cat "$RUN/nginx.pid")   -> $BIND:$PORT" || err "nginx   detenido"
  alive "$RUN/backend.pid" && ok "backend pid $(cat "$RUN/backend.pid") -> unix:.run/backend.sock + diag 127.0.0.1:$DPORT" || err "backend detenido"
  curl -fs "$BASE/api/scoreboard" 2>/dev/null || true
}

case "${1:-}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; sleep 0.5; start ;;
  status)  status ;;
  reset)   stop; rm -rf "$RUN"; ok "secreto y estado borrados: flags nuevas en el próximo start" ;;
  flags)   load_secret; info "SPOILER - flags de esta instancia:"; python3 "$ROOT/app/server.py" --flags ;;
  logs)    tail -n 50 -f "$RUN/access.log" "$RUN/backend.log" ;;
  *) echo "uso: $0 {start|stop|restart|status|reset|flags|logs}"; exit 1 ;;
esac
