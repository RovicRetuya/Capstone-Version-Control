#!/usr/bin/env bash
# One-time setup of DeFaketive on a fresh Ubuntu 24.04 server (Oracle Cloud Always Free, or any VPS).
# Run from the repo folder as a normal user with sudo:   bash deploy/setup-server.sh
# Safe to run again: it only does what is still missing, and never touches an existing database.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
BACK="$REPO/backend"

echo "== Swap (a small server has little memory; this keeps a spike from killing the app) =="
if ! swapon --show | grep -q .; then
    sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "== System packages =="
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip git curl ca-certificates debian-keyring debian-archive-keyring apt-transport-https gpg
if ! command -v node >/dev/null || [ "$(node -v | cut -c2-3)" -lt 20 ]; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi
if ! command -v caddy >/dev/null; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
    sudo apt-get update -y && sudo apt-get install -y caddy
fi

echo "== Python environment (backend/.venv) =="
[ -x "$BACK/.venv/bin/python" ] || python3 -m venv "$BACK/.venv"
PY="$BACK/.venv/bin/python"
"$PY" -m pip install --disable-pip-version-check -q --upgrade pip
# The server needs no browser: the Chrome scanner is a separate program run only on a team PC. Leave it out here.
grep -v -i -E '^(selenium|undetected-chromedriver|trio|trio-websocket|outcome|websocket-client|pywin32|colorama)([=<>~ ]|$)' \
    scripts/requirements-lock.txt > /tmp/defaketive-requirements.txt
"$PY" -m pip install --disable-pip-version-check -q -r /tmp/defaketive-requirements.txt "waitress==3.0.2"
"$PY" -m nltk.downloader -q -d "$BACK/.venv/nltk_data" vader_lexicon

echo "== Starter reports =="
"$PY" scripts/load_starter_data.py

echo "== The site (npm run build) =="
sudo npm install -g npm@11 >/dev/null  # the lockfile was made with npm 11; the npm 10 that comes with Node 22 rejects it
npm ci --no-fund --no-audit
npm run build

echo "== Service =="
sed -e "s#__REPO__#$REPO#g" -e "s#__USER__#$(id -un)#g" deploy/defaketive.service | sudo tee /etc/systemd/system/defaketive.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable defaketive
sudo systemctl restart defaketive  # restart, not just start: a running service keeps the old code in memory
sleep 5
curl -fsS http://127.0.0.1:8080/ >/dev/null && echo "DeFaketive is answering on port 8080." || echo "Not answering yet: sudo journalctl -u defaketive -n 50"
echo "Next: set up the public address, see deploy/SETUP.md step 5."
