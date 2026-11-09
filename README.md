# Local Tech Lab :: HTTP Verbs

Laboratorio práctico de **Local Tech Lab** para comprender los **métodos de petición HTTP (verbos HTTP)** y sus implicaciones en la seguridad de aplicaciones web. A través de nueve misiones conectadas, permite trabajar con `curl` desde la terminal de Linux, interpretar cabeceras y códigos de estado, y analizar fallos de autenticación y control de acceso.

El entorno combina nginx como proxy de entrada y un backend en Python sin dependencias externas. Cada misión incorpora un objetivo técnico y una flag `LTL{...}`; el sistema de puntuación permite seguir el progreso en un entorno local y controlado.

> ⚠️ **Objetivo intencionalmente vulnerable.** Solo escucha en `127.0.0.1`. No lo expongas a una red ni lo despliegues en un servidor público.

## Misiones

| #  | Verbo | Dificultad | Pts | Misión | Concepto |
|----|-------|-----------|-----|--------|----------|
| M1 | `GET` | Easy | 10 | Intern's Notes | Lectura de recursos, enumeración de IDs (IDOR) |
| M2 | `HEAD` | Easy | 10 | Silent Vault | Cabeceras sin cuerpo, fuga de información en headers |
| M3 | `OPTIONS` | Easy | 20 | Gatekeeper | Cabecera `Allow`, verbos personalizados |
| M4 | `POST` | Easy | 20 | Operator Login | Envío de JSON, `Content-Type`, autenticación |
| M5 | `PUT` | Medium | 20 | Compliance Upload | Crear/reemplazar en URI exacta, idempotencia (201 vs 200) |
| M6 | `PATCH` | Medium | 30 | Partial Promotion | Actualización parcial, *mass assignment* |
| M7 | `DELETE` | Medium | 30 | Ghost Session | Borrado de recursos, control de sesiones |
| M8 | `TRACE` | Hard | 40 | Proxy Whispers | Cross-Site Tracing (XST), listener expuesto que evade el proxy |
| M9 | `POST` + override | Hard | 50 | Edge Bypass | *Verb tampering* con `X-HTTP-Method-Override` |

Total: **230 puntos**. Las misiones están encadenadas: lo que encuentras en una sirve en otra.

## Requisitos

- Linux (probado en Ubuntu 24.04 / Debian) con `nginx`, `python3` (3.8+) y `curl`.
- No necesita root ni modifica `/etc/nginx`: todo corre desde la carpeta del repo.
- Clónalo en una ruta corta (p. ej. `~/local-tech-lab`): Linux limita la ruta del socket UNIX a 107 caracteres.

```bash
sudo apt install -y nginx-light python3 curl   # o "nginx" si prefieres el paquete completo
```

## Inicio rápido

```bash
git clone https://github.com/BEMC-GTRX/local-tech-lab.git
cd local-tech-lab
./lab.sh start
curl -s http://127.0.0.1:8080/api/missions
```

Enviar una flag y ver el marcador:

```bash
curl -s -X POST http://127.0.0.1:8080/api/submit \
     -H "Content-Type: application/json" -d '{"flag":"LTL{...}"}'
curl -s http://127.0.0.1:8080/api/scoreboard
```

## Gestión del lab

| Comando | Qué hace |
|---------|----------|
| `./lab.sh start` | Genera secreto, renderiza nginx y arranca todo |
| `./lab.sh status` | Estado de procesos y marcador |
| `./lab.sh stop` / `restart` | Detener / reiniciar (el estado en memoria se pierde) |
| `./lab.sh reset` | Borra secreto y estado: **flags nuevas** en el próximo `start` |
| `./lab.sh logs` | Sigue los logs de nginx y del backend |
| `./lab.sh flags` | Muestra las flags de tu instancia (spoiler) |
| `./walkthrough.sh` | Resolución guiada paso a paso (spoiler, ideal para video) |

Variables opcionales: `LTL_PORT` (8080), `LTL_DEBUG_PORT` (9000), `LTL_BIND` (127.0.0.1).

## Arquitectura

```
 curl ──► nginx 127.0.0.1:8080 ──► unix:.run/backend.sock ──► app/server.py (API principal)
             │  limit_except en /api/m9/
             │  TRACE → 405 siempre
 curl ──────────────────────────► 127.0.0.1:9000  (listener de diagnóstico "olvidado", solo /api/m8/*)
```

- Las flags se derivan con `HMAC(secreto, misión)`: no están en el repo y cambian con `./lab.sh reset`.
- Todo el estado vive en memoria: no escribe archivos subidos a disco ni ejecuta comandos.

## Estructura

```
local-tech-lab/
├── app/server.py            # backend vulnerable (stdlib)
├── nginx/nginx.conf.tpl     # plantilla del proxy de borde
├── lab.sh                   # start | stop | status | reset | flags | logs
├── walkthrough.sh           # solución guiada (SPOILERS)
├── docs/WALKTHROUGH.md      # write-up (SPOILERS)
├── docs/DEFENSE.md          # cómo se corrige cada fallo (blue team)
└── .github/workflows/smoke.yml
```

## Cheat sheet de curl

| Opción | Uso |
|--------|-----|
| `-X VERBO` | Fuerza el método (incluso inventado: `-X LTLSCAN`) |
| `-I` | Petición HEAD, muestra solo cabeceras |
| `-i` | Incluye cabeceras de respuesta |
| `-v` | Verbose: petición y respuesta completas |
| `-H "K: V"` | Añade cabecera |
| `-d` / `--data-binary` | Cuerpo (POST por defecto; con `-X PUT/PATCH` cambia el verbo) |
| `-w "%{http_code}\n" -o /dev/null` | Solo el código de estado |

## Aviso legal

Proyecto educativo. Úsalo únicamente en tu propia máquina o en entornos donde tengas autorización explícita.

Licencia MIT · **Local Tech Lab**
