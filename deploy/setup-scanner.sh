#!/usr/bin/env bash
# EXPERIMENT: lets the website's own "paste a Lazada link" scan run on this server, with a headless Chrome.
# Needs about 4 GB of memory (a scan's Chrome takes ~0.5 GB on top of the app) and a Lazada login (cookies, see below).
# Run after setup-server.sh:   bash deploy/setup-scanner.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY="$(pwd)/backend/.venv/bin/python"

if [ "$(free -m | awk '/^Mem:/{print $2}')" -lt 3000 ]; then
    echo "This server has under 3 GB of memory; Chrome plus the app will not fit. Resize it first." && exit 1
fi

echo "== Google Chrome =="
if ! command -v google-chrome >/dev/null; then
    curl -fsSL -o /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo apt-get install -y /tmp/chrome.deb
fi
google-chrome --version

echo "== Scanner packages (selenium, undetected-chromedriver) =="
"$PY" -m pip install --disable-pip-version-check -q -r scripts/requirements-lock.txt setuptools

echo "== Login cookies =="
if [ ! -s backend/cookies_lazada_ph.dat ]; then
    echo "Missing backend/cookies_lazada_ph.dat. From your PC (where Lazada is logged in), run:"
    echo "  scp -i ~/.ssh/DeFaketive_key.pem backend/cookies_lazada_ph.dat azureuser@<server ip>:~/defaketive/backend/"
    echo "Then run this script again."
    exit 1
fi
chmod 600 backend/cookies_lazada_ph.dat

sudo systemctl restart defaketive
echo "Done. Try a Lazada link on the Analyze page. Log: sudo journalctl -u defaketive -f"
