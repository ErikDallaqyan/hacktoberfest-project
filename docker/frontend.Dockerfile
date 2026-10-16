FROM nginxinc/nginx-unprivileged:1.27-alpine

# Static UI; /api/* is proxied to the backend named by BACKEND_URL.
COPY docker/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY frontend /usr/share/nginx/html

ENV BACKEND_URL=http://backend:8000
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
