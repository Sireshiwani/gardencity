#!/usr/bin/env bash
# Deploy Garden City Fine Cuts on the VPS (pull, backup, migrate, restart, verify).
#
# Usage (from a git clone):
#   cd /var/www/gardencity && bash deploy/deploy.sh
#
# Environment (optional):
#   GIT_BRANCH=main              Branch to deploy (default: main)
#   GIT_REMOTE=origin            Remote name (default: origin)
#   DJANGO_SERVICE=finecuts          systemd unit to restart (default: finecuts)
#   DEPLOY_BACKUP_DB=1           1 = pg_dump before migrate (default: 1)
#   DEPLOY_BACKUP_DIR=/var/backups/gardencity
#   HEALTH_URL=http://127.0.0.1:8000/login/
#   HEALTH_RETRIES=5
#
# First-time server setup (clone, .env, nginx): see deploy/DEPLOY-DIGITALOCEAN.md

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

GIT_BRANCH="${GIT_BRANCH:-main}"
GIT_REMOTE="${GIT_REMOTE:-origin}"
SERVICE_NAME="${DJANGO_SERVICE:-finecuts}"
VENV="${APP_DIR}/.venv/bin/activate"
DEPLOY_BACKUP_DB="${DEPLOY_BACKUP_DB:-1}"
DEPLOY_BACKUP_DIR="${DEPLOY_BACKUP_DIR:-/var/backups/gardencity}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/login/}"
HEALTH_RETRIES="${HEALTH_RETRIES:-5}"
LOG_FILE="${DEPLOY_LOG:-/var/log/finecuts-deploy.log}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

sudo mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
exec > >(tee -a "$LOG_FILE") 2>&1
log "==> Deploy started (branch=${GIT_BRANCH}, dir=${APP_DIR})"

require_git_repo() {
  if [[ ! -d .git ]]; then
    log "ERROR: Not a git repository. First-time install:"
    log "  See deploy/DEPLOY-DIGITALOCEAN.md (clone, .env, venv, gunicorn)."
    log "  Quick clone:"
    log "    cd /var/www && git clone https://github.com/Sireshiwani/finecuts2.git gardencity"
    exit 1
  fi
}

require_clean_tree() {
  local dirty
  dirty="$(git status --porcelain | grep -v '^?? deploy\.log$' || true)"
  if [[ -n "$dirty" ]]; then
    log "ERROR: Working tree is not clean. Commit, stash, or discard local changes first:"
    git status --short
    exit 1
  fi
}

pull_latest() {
  log "==> Fetch ${GIT_REMOTE}/${GIT_BRANCH}"
  git fetch "${GIT_REMOTE}" "${GIT_BRANCH}"

  log "==> Checkout ${GIT_BRANCH}"
  git checkout "${GIT_BRANCH}"

  local old_rev
  old_rev="$(git rev-parse HEAD)"

  log "==> Pull (ff-only) ${GIT_REMOTE}/${GIT_BRANCH}"
  if ! git pull --ff-only "${GIT_REMOTE}" "${GIT_BRANCH}"; then
    log "ERROR: git pull failed (non-fast-forward or merge conflict)."
    log "       Fix on the server or reset to match GitHub, then retry."
    exit 1
  fi

  local new_rev
  new_rev="$(git rev-parse HEAD)"
  log "==> Git: ${old_rev:0:12} -> ${new_rev:0:12}"
  git log -1 --oneline
}

require_env_file() {
  if [[ ! -f .env ]]; then
    log "ERROR: Missing .env in ${APP_DIR}"
    log "       Copy from .env.example and configure (see deploy/DEPLOY-DIGITALOCEAN.md)."
    exit 1
  fi
}

ensure_venv() {
  if [[ ! -f "$VENV" ]]; then
    log "==> Creating virtualenv (.venv)"
    python3 -m venv .venv
  fi
  # shellcheck source=/dev/null
  source "$VENV"
}

backup_database() {
  if [[ "${DEPLOY_BACKUP_DB}" != "1" ]]; then
    log "==> DB backup skipped (DEPLOY_BACKUP_DB=${DEPLOY_BACKUP_DB})"
    return 0
  fi

  log "==> Database backup (if Postgres)"
  mkdir -p "${DEPLOY_BACKUP_DIR}"

  python <<'PY' || exit 1
import gzip
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.conf import settings

db = settings.DATABASES["default"]
engine = db.get("ENGINE", "")

if "postgresql" not in engine:
    print("SQLite or non-Postgres — skipping pg_dump.")
    sys.exit(0)

backup_dir = Path(os.environ.get("DEPLOY_BACKUP_DIR", "/var/backups/gardencity"))
backup_dir.mkdir(parents=True, exist_ok=True)
stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
out_path = backup_dir / f"db_{stamp}.sql.gz"

host = db.get("HOST") or "localhost"
port = str(db.get("PORT") or "5432")
name = db["NAME"]
user = db.get("USER") or ""
password = db.get("PASSWORD") or ""

if not name:
    print("ERROR: DATABASE NAME missing", file=sys.stderr)
    sys.exit(1)

env = os.environ.copy()
if password:
    env["PGPASSWORD"] = password

cmd = [
    "pg_dump",
    "-h", host,
    "-p", port,
    "-U", user,
    "-d", name,
    "--no-owner",
    "--no-acl",
]

print(f"Running pg_dump -> {out_path}")
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
assert proc.stdout is not None
with gzip.open(out_path, "wb") as gz:
    gz.writelines(proc.stdout)
stderr = proc.stderr.read().decode() if proc.stderr else ""
rc = proc.wait()
if rc != 0:
    print(stderr, file=sys.stderr)
    print(f"ERROR: pg_dump failed with code {rc}", file=sys.stderr)
    sys.exit(rc)

print(f"Backup saved: {out_path} ({out_path.stat().st_size} bytes)")
PY
}

run_migrations() {
  log "==> Migration plan"
  python manage.py showmigrations --plan | tail -20 || true
  log "==> migrate"
  python manage.py migrate --noinput
}

collect_static() {
  log "==> collectstatic"
  python manage.py collectstatic --noinput
}

restart_service() {
  log "==> restart ${SERVICE_NAME}"
  sudo systemctl restart "${SERVICE_NAME}"
}

wait_for_service() {
  log "==> systemd status"
  if ! sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
    log "ERROR: ${SERVICE_NAME} is not active"
    sudo systemctl --no-pager status "${SERVICE_NAME}" || true
    exit 1
  fi
  sudo systemctl --no-pager status "${SERVICE_NAME}" || true
}

health_check() {
  log "==> Health check: ${HEALTH_URL}"
  local i
  for ((i = 1; i <= HEALTH_RETRIES; i++)); do
    if curl -sf --max-time 10 "${HEALTH_URL}" >/dev/null; then
      log "Health check OK (attempt ${i}/${HEALTH_RETRIES})"
      return 0
    fi
    log "Health check attempt ${i}/${HEALTH_RETRIES} failed; retrying in 2s..."
    sleep 2
  done
  log "ERROR: Health check failed after ${HEALTH_RETRIES} attempts"
  log "       Check: sudo journalctl -u ${SERVICE_NAME} -n 50 --no-pager"
  exit 1
}

main() {
  require_git_repo
  require_env_file
  require_clean_tree
  pull_latest
  ensure_venv
  log "==> pip install"
  pip install -r requirements.txt
  export DEPLOY_BACKUP_DIR
  backup_database
  run_migrations
  collect_static
  restart_service
  wait_for_service
  health_check
  log "==> Deploy finished successfully"
}

main "$@"
