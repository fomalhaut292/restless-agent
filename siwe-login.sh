#!/usr/bin/env bash
# SIWE login to Agent Games with the Muse-operated 0x59 wallet (API route).
# Mirrors the site's own frontend flow (from its JS bundle):
#   GET /api/auth/csrf -> GET /api/auth/wallet/siwe/nonce -> sign SIWE message
#   -> POST /api/auth/callback/wallet (next-auth credentials provider "wallet")
#   -> GET /api/auth/session to verify.
# The key never leaves the vault: signing goes through zerovault-sign.mjs
# (personal_sign only). The signed message is a login statement only
# (domain agentgames.zkverify.io, no transfers/approvals/permissions).
set -euo pipefail
cd ~/workspace/zkverify-agent-games
BASE="https://agentgames.zkverify.io"
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
JAR="./cookies.txt"
: > "$JAR"

echo "== csrf =="
CSRF_JSON=$(curl -s --http1.1 -c "$JAR" -b "$JAR" -A "$UA" -H "Origin: $BASE" -H "Referer: $BASE/register" "$BASE/api/auth/csrf")
CSRF=$(printf '%s' "$CSRF_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['csrfToken'])")
echo "csrfToken: ${CSRF:0:8}... (len ${#CSRF})"

echo "== nonce =="
NONCE_JSON=$(curl -s --http1.1 -c "$JAR" -b "$JAR" -A "$UA" -H "Origin: $BASE" -H "Referer: $BASE/register" "$BASE/api/auth/wallet/siwe/nonce")
NONCE=$(printf '%s' "$NONCE_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['nonce'])")
echo "nonce: $NONCE"

echo "== build SIWE message =="
python3 - "$NONCE" <<'EOF'
import sys
from datetime import datetime, timedelta, timezone
nonce = sys.argv[1]
now = datetime.now(timezone.utc)
exp = now + timedelta(milliseconds=300000)
def iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S.') + f"{dt.microsecond//1000:03d}Z"
addr = "0x59d4c043115503273aE869D750B11126Da83452f"
msg = (
    "agentgames.zkverify.io wants you to sign in with your Ethereum account:\n"
    f"{addr}\n\n"
    "Sign in to Agent Games with your wallet.\n"
    "\n"
    "URI: https://agentgames.zkverify.io\n"
    "Version: 1\n"
    "Chain ID: 1\n"
    f"Nonce: {nonce}\n"
    f"Issued At: {iso(now)}\n"
    f"Expiration Time: {iso(exp)}"
)
open('siwe-message.txt', 'w').write(msg)
print("message bytes:", len(msg))
EOF

echo "== sign (vault, 0x59) =="
SIGN_JSON=$(node ~/workspace/tools/elysium-wallet/zerovault-sign.mjs --message-file ./siwe-message.txt)
SIG=$(printf '%s' "$SIGN_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['signature'])")
ADDR=$(printf '%s' "$SIGN_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['address'])")
echo "signed by: $ADDR (sig len ${#SIG})"

echo "== callback =="
curl -s --http1.1 -c "$JAR" -b "$JAR" -A "$UA" -H "Origin: $BASE" -H "Referer: $BASE/register" \
  --data-urlencode "csrfToken=$CSRF" \
  --data-urlencode "callbackUrl=$BASE/register" \
  --data-urlencode "json=true" \
  --data-urlencode "message@./siwe-message.txt" \
  --data-urlencode "signature=$SIG" \
  "$BASE/api/auth/callback/wallet" | head -c 600
echo
echo "== session =="
curl -s --http1.1 -b "$JAR" -A "$UA" -H "Origin: $BASE" -H "Referer: $BASE/" "$BASE/api/auth/session" | head -c 1200
echo
