#!/usr/bin/env bash
# One-time preparation of the frontend VM. Idempotent; safe to re-run.
#   sudo BACKEND_UPSTREAM=10.160.0.2:80 bash setup_vm.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_UPSTREAM="${BACKEND_UPSTREAM:-10.160.0.2:80}"

install -d -o root -g root -m 755 /var/www/monitra /var/www/monitra/releases

sed "s|__BACKEND_UPSTREAM__|$BACKEND_UPSTREAM|" "$HERE/nginx-app.conf" \
  > /etc/nginx/sites-available/monitra-app
ln -sfn /etc/nginx/sites-available/monitra-app /etc/nginx/sites-enabled/monitra-app
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "Frontend VM prepared (API upstream: $BACKEND_UPSTREAM). Next: sudo bash deploy.sh /path/to/dist.tgz"
