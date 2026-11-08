# Defensa (blue team) · Local Tech Lab :: HTTP Verbs

| Misión | Fallo | Corrección |
|--------|-------|------------|
| M1 | Recursos "ocultos" accesibles por ID | Autorización por recurso en cada petición; IDs no predecibles (UUID) como capa extra, nunca como control |
| M2 | Datos sensibles en cabeceras | No enviar secretos en headers; mismas cabeceras en GET y HEAD |
| M3 | Verbos no estándar habilitados | Lista blanca de métodos por ruta en el borde |
| M4 | Login sin límites | Rate limiting, bloqueo progresivo, `Content-Type` estricto, hashing (argon2/bcrypt) |
| M5 | PUT sin autenticación | Autenticación + validación de nombre/tamaño/tipo; nunca escribir en rutas servidas |
| M6 | *Mass assignment* | Lista blanca de campos editables por rol; `role` nunca viene del cliente |
| M7 | DELETE sin verificación fuerte | Re-autenticación para acciones sensibles, auditoría, verificación de pertenencia |
| M8 | TRACE + listener expuesto | Deshabilitar TRACE en la app; el backend solo en socket UNIX o red interna; firewall |
| M9 | Confiar en `X-HTTP-Method-Override` | Desactivar el override o eliminar la cabecera en el proxy |

## Snippets nginx

Lista blanca de métodos por ubicación:

```nginx
location /api/ {
    limit_except GET POST { deny all; }   # GET implica HEAD
    proxy_pass http://backend;
}
```

Eliminar cabeceras de override antes del upstream (corrige M9):

```nginx
proxy_set_header X-HTTP-Method-Override "";
proxy_set_header X-HTTP-Method "";
proxy_set_header X-Method-Override "";
```

Rechazar cualquier verbo fuera de la lista en todo el servidor:

```nginx
if ($request_method !~ ^(GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS)$) { return 405; }
```

Backend inaccesible salvo por el proxy (corrige M8):

```nginx
upstream backend { server unix:/run/app/app.sock; }
```
```bash
# si el backend debe usar TCP: solo loopback y bloquear lo demás
sudo iptables -A INPUT -p tcp --dport 9000 ! -i lo -j DROP
```

## Verificación rápida

```bash
for m in GET HEAD POST PUT PATCH DELETE OPTIONS TRACE CONNECT FOO; do
  printf "%-8s %s\n" $m "$(curl -s -o /dev/null -w '%{http_code}' -X $m https://tu-sitio/api/)"
done
```
