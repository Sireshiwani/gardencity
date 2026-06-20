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
sudo ln -sf /etc/nginx/sites-available/finecuts /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

HTTPS:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d gardencityfinecuts.co.ke -d www.gardencityfinecuts.co.ke
```

## 6. Environment variables

Use **only** `/var/www/gardencity/.env` with **`finecuts-django.service`**.  
Disable the legacy `finecuts.service` if it exists (it reads `/var/www/finecuts/.env`).

```bash
sudo systemctl stop finecuts 2>/dev/null; sudo systemctl disable finecuts 2>/dev/null
sudo systemctl enable --now finecuts-django
```

### `/var/www/gardencity/.env` (Django) — before SSL (HTTP)

```env
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<long-random-secret>
DJANGO_ALLOWED_HOSTS=gardencityfinecuts.co.ke,www.gardencityfinecuts.co.ke,127.0.0.1,127.0.0.1:8000,localhost,localhost:8000,165.22.30.29
DJANGO_CSRF_TRUSTED_ORIGINS=http://gardencityfinecuts.co.ke,http://www.gardencityfinecuts.co.ke,http://165.22.30.29
DJANGO_SECURE_SSL_REDIRECT=false
DJANGO_SESSION_COOKIE_SECURE=false
DJANGO_CSRF_COOKIE_SECURE=false
PUBLIC_SITE_URL=http://gardencityfinecuts.co.ke
CORS_ALLOWED_ORIGINS=http://gardencityfinecuts.co.ke,http://www.gardencityfinecuts.co.ke
```

### After `certbot` (HTTPS)

```env
DJANGO_CSRF_TRUSTED_ORIGINS=https://gardencityfinecuts.co.ke,https://www.gardencityfinecuts.co.ke
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
PUBLIC_SITE_URL=https://gardencityfinecuts.co.ke
CORS_ALLOWED_ORIGINS=https://gardencityfinecuts.co.ke,https://www.gardencityfinecuts.co.ke
```

Optional Postgres:

```env
DATABASE_URL=postgres://user:pass@host:25060/dbname?sslmode=require
```

### Email (required for password reset)

Password reset emails staff at the address on their account. Without SMTP, reset links are not delivered.

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-address@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
DEFAULT_FROM_EMAIL=Garden City Fine Cuts <your-address@gmail.com>
```

Gmail: use an [App Password](https://myaccount.google.com/apppasswords), not your normal login password.

Test from the server:

```bash
cd /var/www/gardencity && source .venv/bin/activate
python manage.py shell -c "
from django.core.mail import send_mail
send_mail('Test', 'Password reset email works.', None, ['you@example.com'])
print('sent')
"
```

### `/var/www/finecuts2/.env.production` (Next)

```env
DJANGO_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_DJANGO_API_URL=https://gardencityfinecuts.co.ke
PORT=3000
```

## 7. DNS (Host Africa)

In **Host Africa → Domains → Manage DNS** for `gardencityfinecuts.co.ke`:

| Type | Host | Value |
|------|------|--------|
| A | `@` | Your DigitalOcean droplet IPv4 |
| A | `www` | Same droplet IPv4 |

Nameservers (if using Host Africa DNS): `ns1.host-ww.net`, `ns2.host-ww.net`.

Check propagation: [dnschecker.org](https://dnschecker.org/#A/gardencityfinecuts.co.ke)

## 8. Finish deployment (run on the VPS)

### A) Services (one Gunicorn, one Next)

```bash
sudo systemctl stop finecuts 2>/dev/null; sudo systemctl disable finecuts 2>/dev/null
sudo systemctl enable --now finecuts-django finecuts-next
sudo ss -tlnp | grep -E '3000|8000'
```

### B) Next build (required once per deploy)

```bash
sudo rm -f /var/www/package-lock.json
cd /var/www/finecuts2
npm install && npm run build
ls -la .next/BUILD_ID
sudo chown -R www-data:www-data /var/www/finecuts2
sudo systemctl restart finecuts-next
```

### C) Nginx (Next at `/`, Django on API/staff paths)

```bash
sudo cp /var/www/gardencity/deploy/nginx-finecuts.conf /etc/nginx/sites-available/finecuts
sudo ln -sf /etc/nginx/sites-available/finecuts /etc/nginx/sites-enabled/finecuts
sudo nginx -t && sudo systemctl reload nginx
```

### D) Smoke tests (use GET for API — `curl -I` sends HEAD and returns 405)

```bash
curl -s -o /dev/null -w "next / → %{http_code}\n" -H "Host: gardencityfinecuts.co.ke" http://127.0.0.1/
curl -s http://127.0.0.1:8000/api/public/home/ | head -c 120
curl -s -o /dev/null -w "api via nginx → %{http_code}\n" -H "Host: gardencityfinecuts.co.ke" http://127.0.0.1/api/public/home/
PID=$(pgrep -f 'gunicorn config.wsgi' | head -1)
sudo tr '\0' '\n' < /proc/$PID/environ | grep DJANGO_ALLOWED
```

Expect: `200` for home and API, JSON from Django, `gardencityfinecuts.co.ke` in `DJANGO_ALLOWED_HOSTS`.

### E) DNS (Host Africa)

| Type | Host | Value |
|------|------|--------|
| A | `@` | `165.22.30.29` |
| A | `www` | `165.22.30.29` |

Wait for propagation, then open `http://gardencityfinecuts.co.ke/` in a browser.

### F) SSL (after DNS works)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d gardencityfinecuts.co.ke -d www.gardencityfinecuts.co.ke
```

Update `/var/www/gardencity/.env` to the **HTTPS** block in section 6, then:

```bash
sudo systemctl restart finecuts-django
```

Update Next public URL:

```bash
nano /var/www/finecuts2/.env.production
# NEXT_PUBLIC_DJANGO_API_URL=https://gardencityfinecuts.co.ke
cd /var/www/finecuts2 && npm run build && sudo systemctl restart finecuts-next
```

## 9. Verify in browser

| URL | Expected |
|-----|----------|
| `https://gardencityfinecuts.co.ke/` | Next marketing home (services/team load) |
| `https://gardencityfinecuts.co.ke/booking` | Next booking wizard |
| `https://gardencityfinecuts.co.ke/login/` | Django staff login |
| `https://gardencityfinecuts.co.ke/dashboard/` | Django dashboard |

## Troubleshooting

### 400 on `/` or `/api/…` (DisallowedHost)

Gunicorn is using the wrong `.env`. Find it:

```bash
sudo grep -r "DJANGO_ALLOWED_HOSTS" /var/www/*/.env 2>/dev/null
pgrep -af gunicorn
sudo tr '\0' '\n' < /proc/$(pgrep -f 'gunicorn config.wsgi' | head -1)/environ | grep DJANGO_ALLOWED
```

Use **`/var/www/gardencity/.env`** and **`finecuts-django`**, not `/var/www/finecuts/.env` + `finecuts.service`.

### 301 to HTTPS but port 443 not open

Set `DJANGO_SECURE_SSL_REDIRECT=false` until certbot completes (see section 6 HTTP block).

### Next crash: “Could not find a production build”

Run `npm run build` in `/var/www/finecuts2` and restart `finecuts-next`.

### Login 403 CSRF (after HTTPS)

1. `DJANGO_CSRF_TRUSTED_ORIGINS` must use `https://` for your domain.
2. nginx must send `proxy_set_header X-Forwarded-Proto $scheme;` (in `nginx-finecuts.conf`).
3. `sudo systemctl restart finecuts-django` and clear site cookies in the browser.

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
