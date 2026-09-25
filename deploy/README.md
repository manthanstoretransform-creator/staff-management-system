# Deploying Monitra to Google Cloud

Project `monitra-509314`, zone `asia-south1-c`.

| Role | VM | External IP | Internal IP | Serves |
|---|---|---|---|---|
| Frontend | `frontend` (e2-micro) | 8.234.122.232 | 10.160.0.3 | nginx: Vite build + `/api/` proxy to backend |
| Backend | `instance-20260921-144636` (e2-small) | 35.200.167.240 | 10.160.0.2 | nginx → uvicorn (`monitra-backend.service`) |
| Database | Cloud SQL `monitra-database` (PostgreSQL 18) | 35.200.162.243 | — | |

The web client is built with `VITE_API_BASE=/api/v1`, so browser requests are
same-origin and the frontend VM's nginx forwards `/api/` to the backend over
the VPC. No CORS entries are needed for the web client. The desktop app talks
to the backend host directly.

## One-time VM preparation

Base packages (already done on both VMs): `nginx git certbot python3-certbot-nginx`,
plus `python3-venv python3-pip libpq5` on the backend.

From a workstation with SSH access (`dell@<ip>`):

```bash
tar -czf deploy.tgz -C deploy .
for ip in 35.200.167.240 8.234.122.232; do scp deploy.tgz dell@$ip:/tmp/; done

# backend
ssh dell@35.200.167.240 'mkdir -p /tmp/deploy && tar -xzf /tmp/deploy.tgz -C /tmp/deploy && sudo bash /tmp/deploy/backend/setup_vm.sh'
# frontend
ssh dell@8.234.122.232 'mkdir -p /tmp/deploy && tar -xzf /tmp/deploy.tgz -C /tmp/deploy && sudo BACKEND_UPSTREAM=10.160.0.2:80 bash /tmp/deploy/frontend/setup_vm.sh'
```

`setup_vm.sh` creates the `monitra` system user, `/opt/monitra`, the venv, the
systemd unit, and the nginx site. It writes `/etc/monitra/backend.env` from
`backend.env.example` if none exists — **fill it in before the first deploy**
(`sudo nano /etc/monitra/backend.env`).

### Cloud SQL

The backend connects over the instance's public IP, so the backend VM's
external IP (`35.200.167.240/32`) must be listed under
Cloud SQL → `monitra-database` → Connections → Networking → Authorized networks.
Create an application user and database, and put them in `DATABASE_URL`.
The schema is created by `alembic upgrade head` on the first deploy.

## Deploying by hand

```bash
# backend
tar -czf backend.tgz -C backend --exclude=venv --exclude=__pycache__ --exclude='.env*' --exclude=tests .
scp backend.tgz dell@35.200.167.240:/tmp/
ssh dell@35.200.167.240 'sudo bash /tmp/deploy/backend/deploy.sh /tmp/backend.tgz'

# frontend
(cd frontend && npm ci && VITE_API_BASE=/api/v1 npm run build && tar -czf ../dist.tgz -C dist .)
scp dist.tgz dell@8.234.122.232:/tmp/
ssh dell@8.234.122.232 'sudo bash /tmp/deploy/frontend/deploy.sh /tmp/dist.tgz'
```

Each deploy is a new directory under `/opt/monitra/releases` (backend) or
`/var/www/monitra/releases` (frontend), with `current`/`backend` symlinks
pointing at the live one; the last three are kept.

**Rollback:** re-point the symlink and restart/reload.

```bash
sudo ln -sfn /opt/monitra/releases/<older> /opt/monitra/backend && sudo systemctl restart monitra-backend
sudo ln -sfn /var/www/monitra/releases/<older> /var/www/monitra/current && sudo systemctl reload nginx
```

## Continuous deployment (Cloud Build)

`cloudbuild-backend.yaml` and `cloudbuild-frontend.yaml` each build on a push
to `main` and deploy to the matching VM over SSH.

1. Connect the GitHub repository to Cloud Build (console → Cloud Build →
   Repositories → Connect).
2. Enable OS Login on both VMs and grant the Cloud Build service account
   (`<project-number>@cloudbuild.gserviceaccount.com`):
   `roles/compute.osAdminLogin`, `roles/compute.viewer`, and
   `roles/iam.serviceAccountUser` on the VMs' service account.
   ```bash
   gcloud compute instances add-metadata frontend --zone asia-south1-c --metadata enable-oslogin=TRUE
   gcloud compute instances add-metadata instance-20260921-144636 --zone asia-south1-c --metadata enable-oslogin=TRUE
   ```
3. Create the triggers:
   ```bash
   gcloud builds triggers create github --name=backend-main --repo-owner=<owner> --repo-name=staff-management-system \
     --branch-pattern='^main$' --build-config=cloudbuild-backend.yaml --included-files='backend/**,deploy/backend/**,cloudbuild-backend.yaml'
   gcloud builds triggers create github --name=frontend-main --repo-owner=<owner> --repo-name=staff-management-system \
     --branch-pattern='^main$' --build-config=cloudbuild-frontend.yaml --included-files='frontend/**,deploy/frontend/**,cloudbuild-frontend.yaml'
   ```

## TLS

Once DNS names point at the VMs, set `server_name` in the nginx site on each
VM and run `sudo certbot --nginx -d <name>`. certbot adds the 443 listener,
the redirect, and automatic renewal.

## Operations

```bash
sudo systemctl status monitra-backend
sudo journalctl -u monitra-backend -f
curl -s http://127.0.0.1:8000/health
```
