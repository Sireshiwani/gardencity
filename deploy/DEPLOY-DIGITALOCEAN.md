# Deploy on DigitalOcean VPS

One domain serves the **Next.js** marketing site at `/` and **Django** for staff, API, and admin on selected paths (see `nginx-finecuts.conf`).

## Layout on the droplet

| Path | App |
|------|-----|
| `/var/www/gardencity` | Django (`finecuts2` GitHub repo or your `gardencity` clone) |
| `/var/www/finecuts2` | Next.js marketing site |

## 1. Server setup (Ubuntu)

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip nginx git curl

# Node 20 LTS (example)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

## 2. Clone projects

```bash
sudo mkdir -p /var/www
sudo chown $USER:$USER /var/www

git clone https://github.com/Sireshiwani/finecuts2.git /var/www/gardencity
git clone <YOUR_FINEcuts2_NEXT_REPO_OR_SCP> /var/www/finecuts2
# If Next lives only on the server, copy C:\Users\Eshiwani\finecuts2 to /var/www/finecuts2
```

## 3. Django (Gunicorn)

```bash
cd /var/www/gardencity
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — see "Environment variables" below
python manage.py migrate
python manage.py collectstatic --noinput
```

```bash
sudo cp deploy/gunicorn.service /etc/systemd/system/finecuts-django.service
sudo systemctl daemon-reload
sudo systemctl enable --now finecuts-django
```

## 4. Next.js

```bash
cd /var/www/finecuts2
npm ci
cp .env.production.example .env.production
# Edit .env.production
npm run build
```

```bash
sudo cp /var/www/gardencity/deploy/finecuts-next.service /etc/systemd/system/
# Fix WorkingDirectory in the unit if needed
sudo systemctl daemon-reload
sudo systemctl enable --now finecuts-next
```

## 5. Nginx

```bash
sudo cp /var/www/gardencity/deploy/nginx-finecuts.conf /etc/nginx/sites-available/finecuts
sudo sed -i 's/YOUR_DOMAIN/yourdomain.com/g' /etc/nginx/sites-available/finecuts
sudo ln -sf /etc/nginx/sites-available/finecuts /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

HTTPS:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

## 6. Environment variables

### `/var/www/gardencity/.env` (Django)

```env
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<long-random-secret>
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Official public site — GET / on Django redirects here
PUBLIC_SITE_URL=https://yourdomain.com

# Postgres (DigitalOcean managed DB or droplet)
DATABASE_URL=postgres://user:pass@host:25060/dbname?sslmode=require

CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### `/var/www/finecuts2/.env.production` (Next)

```env
# Server-side proxy to Gunicorn (same machine)
DJANGO_API_URL=http://127.0.0.1:8000

# Browser links to staff login, rewards, etc. (same domain — nginx routes paths)
NEXT_PUBLIC_DJANGO_API_URL=https://yourdomain.com

PORT=3000
```

## 7. DNS (DigitalOcean)

- **A** record `@` → droplet IP  
- **A** record `www` → droplet IP  

## 8. Verify

| URL | Expected |
|-----|----------|
| `https://yourdomain.com/` | Next marketing home |
| `https://yourdomain.com/booking` | Next booking page |
| `https://yourdomain.com/login/` | Django staff login |
| `https://yourdomain.com/dashboard/` | Django staff dashboard |
| `http://127.0.0.1:8000/` on server | Redirects to `PUBLIC_SITE_URL` |

## Updates (after pushing to GitHub)

**One command** — from a **git clone** of the repo (folder must contain `.git`):

```bash
cd /var/www/gardencity
bash deploy/deploy.sh
```

`deploy/deploy.sh` will:

1. Require a **clean** git working tree (no uncommitted server edits)
2. **Fetch and fast-forward** `main` (override with `GIT_BRANCH=develop`)
3. Install Python dependencies
4. **Backup Postgres** to `/var/backups/gardencity/` (skip with `DEPLOY_BACKUP_DB=0`; skipped automatically for SQLite)
5. Run **migrations** and **collectstatic**
6. Restart **finecuts-django**
7. **Health-check** `http://127.0.0.1:8000/login/`

Logs append to `deploy.log` in the project directory.

Optional environment:

```bash
GIT_BRANCH=main DEPLOY_BACKUP_DB=1 HEALTH_URL=http://127.0.0.1:8000/login/ bash deploy/deploy.sh
```

Requires `curl` and `pg_dump` (postgresql-client) on the server for health checks and DB backups.

If you see `fatal: not a git repository`, the app was copied without `git clone`. Fix once:

```bash
cd /var/www
sudo mv gardencity gardencity.backup    # keep old .env / media if any
git clone https://github.com/Sireshiwani/finecuts2.git gardencity
cd gardencity
cp ../gardencity.backup/.env .env       # restore your server .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart finecuts-django
```

Then use `bash deploy/deploy.sh` for all future updates.

**Manual commands** (same as the script):

```bash
cd /var/www/gardencity && git pull && source .venv/bin/activate && pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput && sudo systemctl restart finecuts-django
```

**Optional — separate Next.js site** (only if you still use `/var/www/finecuts2`):

```bash
cd /var/www/finecuts2 && git pull && npm ci && npm run build && sudo systemctl restart finecuts-next
```

## Local development (unchanged)

- Next: `http://localhost:3000` — leave `PUBLIC_SITE_URL` **unset** on Django to keep the old Django home for debugging, or set `PUBLIC_SITE_URL=http://localhost:3000` to mirror production redirects.
