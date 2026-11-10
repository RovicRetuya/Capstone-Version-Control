# Deploying DeFaketive on an Azure VM (runs 24/7, no PC needed)

The live site is https://defaketive.duckdns.org on an Azure VM. You do steps 1-3 and 5 (they need your accounts);
steps 4 and 6 are copy-paste. Any Ubuntu 24.04 VPS works the same way.

## 1. Azure account
https://azure.microsoft.com/free/ -> Start free. A card is used to verify you. Watch the credit: a VM that stays on keeps spending it.

## 2. Make the server
Virtual machines -> Create:
- Image: **Ubuntu Server 24.04 LTS**. Size: at least **4 GB of memory** if the paste-a-link scan (step "What works")
  will run here; the site alone needs less.
- Administrator account: `azureuser`, authenticated with an **SSH public key** (download the .pem Azure offers).
- Note the VM's **public IP**, and make it **static** (Public IP address -> Configuration -> Assignment: Static), or
  it changes when the VM is stopped and the address below stops working. The live VM's is static.

## 3. Open web ports
VM -> Networking -> Network security group -> Add inbound port rule: TCP, ports **80** and **443**, source Any
(port 22 for SSH is already there). Ubuntu on Azure has no firewall of its own to change.

## 4. Install the app (on the server, over SSH)
    git clone <your repo url> defaketive && cd defaketive
    git checkout deployment      # the branch the live site runs
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
- Not set up by default: the website's own "scan this link" box for NEW products. It needs Chrome and a Lazada
  login (cookies). `bash deploy/setup-scanner.sh` adds them (an experiment, about 4 GB of memory). Without it,
  shoppers use the extension for new products (Lazada and Shopee).

## Running it
    sudo systemctl status defaketive      # is it up
    sudo journalctl -u defaketive -f      # its log
    git pull && bash deploy/setup-server.sh    # update (rebuilds the site and restarts the service)
Databases: backend/defaketive.db and backend/instance/accounts.db. serve.py copies both to backups/daily/ every
day (7 days kept). Copy that folder off the server now and then (scp), in case the VM is ever lost.
Azure keeps charging while the VM is allocated; stopping it from inside Ubuntu does not stop the charges (deallocate it
in the portal when it is not needed).
