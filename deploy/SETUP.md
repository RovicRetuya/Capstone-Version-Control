# Deploying DeFaketive on Oracle Cloud Always Free (₱0, runs 24/7, no PC needed)

You do steps 1-3 and 5 (they need your accounts); steps 4 and 6 are copy-paste.

## 1. Oracle account
https://www.oracle.com/cloud/free/ -> Start for free. A card is used only to verify you (a GCash/Maya virtual
card usually works). Choose the home region carefully: it cannot be changed. Stay on "Always Free" resources.

## 2. Make the server
Compute -> Instances -> Create instance:
- Image: **Ubuntu 24.04**. Shape: **Ampere (VM.Standard.A1.Flex)**, 2 OCPU, 12 GB (Always Free allows up to 4 / 24).
- Paste your SSH public key (or let Oracle make one and download it).
- "Out of capacity"? Try again later or in another availability domain; it is common.
- Note the instance's **public IP**.

## 3. Open web ports
Instance -> its subnet -> Security List -> Add ingress rules: source 0.0.0.0/0, TCP, ports **80** and **443**.
Also on the server (Oracle's Ubuntu images block them again inside the VM):
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
    sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
    sudo netfilter-persistent save

## 4. Install the app (on the server, over SSH)
    git clone <your repo url> defaketive && cd defaketive
    git checkout main            # or the branch you want live
    bash deploy/setup-server.sh  # 5-10 minutes

## 5. A free https address
1. https://www.duckdns.org -> sign in, make a name (e.g. `defaketive`), set its IP to the instance's public IP.
2. On the server: edit `deploy/Caddyfile` (your name instead of `your-name.duckdns.org`), then
       sudo cp deploy/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy
3. Open https://defaketive.duckdns.org . Caddy fetches the certificate on the first visit.

## 6. Admin password, then the extension
- Change the admin password first (README, "The admin side"): /admin is public.
- On your PC, make the extension for the live address:
      node scripts/build-extension.mjs --site https://defaketive.duckdns.org
  Load `dist-extension/` unpacked, or upload `dist-extension.zip` to the Chrome Web Store.

## What works and what does not on this server
- Works: every saved report, accounts, the admin side, and **checks sent by the extension** (the server only analyses).
- Does not work: the website's own "scan this link" box for NEW products. That needs Chrome and a Lazada login,
  which this server does not have. Shoppers use the extension for new products.

## Running it
    sudo systemctl status defaketive      # is it up
    sudo journalctl -u defaketive -f      # its log
    git pull && npm run build && sudo systemctl restart defaketive    # update
Databases: backend/defaketive.db and backend/instance/accounts.db. serve.py copies both to backups/daily/ every
day (7 days kept). Copy that folder off the server now and then (scp), in case the VM is ever lost.
Oracle reclaims Always Free VMs that sit idle for 7 days (almost no CPU, network or memory use); a live site is not idle.
