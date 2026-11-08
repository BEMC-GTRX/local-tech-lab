# Local Tech Lab :: HTTP Verbs -- edge proxy (nginx)
# Template rendered by ./lab.sh into .run/nginx.conf. Do not edit the rendered copy.
@USER@
worker_processes 1;
pid @RUN@/nginx.pid;
error_log @RUN@/error.log warn;

events { worker_connections 256; }

http {
    access_log @RUN@/access.log;
    client_body_temp_path @RUN@/tmp/body;
    proxy_temp_path       @RUN@/tmp/proxy;
    fastcgi_temp_path     @RUN@/tmp/fastcgi;
    uwsgi_temp_path       @RUN@/tmp/uwsgi;
    scgi_temp_path        @RUN@/tmp/scgi;

    server_tokens off;
    client_max_body_size 64k;
    keepalive_timeout 15s;

    limit_req_zone $binary_remote_addr zone=ltl_rl:1m rate=50r/s;

    upstream ltl_backend {
        server unix:@RUN@/backend.sock;
        keepalive 8;
    }

    server {
        # Loopback only: this target is intentionally vulnerable.
        listen @BIND@:@PORT@;
        server_name local-tech-lab.local localhost;

        limit_req zone=ltl_rl burst=100 nodelay;
        add_header X-Lab "Local Tech Lab" always;
        add_header X-Content-Type-Options nosniff always;

        # Common upstream settings (inherited by every location below).
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        # Note: nginx hard-rejects TRACE with 405 (not configurable). Good default.

        location / {
            proxy_pass http://ltl_backend;
        }

        # Mission m9: edge policy -- only GET/HEAD/POST may reach the legacy API.
        location /api/m9/ {
            limit_except GET POST { deny all; }
            error_page 403 = /__ltl_forbidden;
            proxy_pass http://ltl_backend;
        }

        location = /__ltl_forbidden {
            internal;
            default_type application/json;
            return 403 '{\n  "error": "forbidden by edge policy",\n  "edge": "nginx limit_except GET POST"\n}\n';
        }
    }
}
