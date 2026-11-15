# Agent Games by zkVerify — run notes (Rest / Bubub)

Event: 400,000 $VFY, 4 tracks × 100,000 (50/30/20K top 3). Runs 21 Oct–21 Nov 2026,
judging 22–30 Nov. Site: https://agentgames.zkverify.io (Next.js, Auth.js v5, wagmi/RainbowKit).

## Registration — DONE 15 Nov 2026 ~08:05 WIB
- Identity: wallet **0x59d4c043115503273aE869D750B11126Da83452f** (EVM, Muse-operated).
- Handle: **@erysta28** (the form AUTO-FILLS handle from the X handle field — the
  "restless" I typed was overwritten when I filled twitter=erysta28).
  Changeable later in Settings if Rest prefers @restless.
- Email: restless.games15@gmail.com. Country: ID. Twitter (text only): erysta28.
- competitionUserId: b3e36bf2-3982-4b64-812b-bc65b5d445d3
- Session: Auth.js cookie `__Secure-authjs.session-token` in ./cookies.txt,
  expires 2026-12-15T01:28:49Z. Verify: GET /api/auth/session ->
  {"registrationComplete": true, ...}.
- Dashboard: "PARTICIPANT CONTROL ROOM / @erysta28", rank NOT RANKED, points 0.0.

## How the sign-in was done (modal is broken)
- The cloud browser's WalletConnect modal stalls (button highlights, no QR/link)
  and crashes the tab 3/3 — no WC URI ever appears, so no WC relay is possible.
- Workaround: direct SIWE via the site's own API (reverse-engineered from its JS
  bundle). Script: ./siwe-login.sh (needs --http1.1: the nonce endpoint HANGS
  on HTTP/2 through the egress proxy).
  Flow: GET /api/auth/csrf -> GET /api/auth/wallet/siwe/nonce -> build EIP-4361
  message (domain agentgames.zkverify.io, statement "Sign in to Agent Games
  with your wallet.", chainId 1, expiry +5min) -> sign with the 0x59 vault key
  via ~/workspace/tools/elysium-wallet/zerovault-sign.mjs (personal_sign, key
  never leaves the vault) -> POST /api/auth/callback/wallet (next-auth form:
  csrfToken, callbackUrl, json=true, message, signature).
- The profile form is a Next.js Server Action: POST /register with a JSON
  array body `[{handle, displayName, contactEmail, country, bio:"",
  twitter, referralCode:"$undefined"}]`. Driven from a real browser:
  ./complete-registration.py (Playwright + session cookie injected via CDP).
- Browser networking fix (VM egress proxy is a TLS-intercepting proxy,
  issuer "Hatch Sandbox Egress CA"; Chromium can't tunnel to it directly):
  the script runs a localhost CONNECT forwarder (preemptive Proxy-Authorization)
  and launches Chromium with --ignore-certificate-errors. Site identity was
  verified by matching page content against curl-fetched HTML.
- WalletConnect projectId seen in telemetry: b4698c5e5bd88b2e4b5a78998f04e635
  (the bundle's 21fef480... is a placeholder fallback — not the real one).

## Still to do
1. **GitHub connect (prize eligibility)** — rules require a connected GitHub
   account + connected wallet to claim prizes. Dashboard Settings -> Connect
   GitHub (OAuth). BLOCKED for now: it needs a GitHub login in a browser;
   the saved GitHub login lives in the Secure Vault (browser-task login agent
   only), and the cloud browser can't reach the agentgames session (httpOnly
   cookie). Options: Rest taps it herself when next on a browser, or try from
   Lemur's device browser. Only matters if we place top-3.
2. **Payout wallet (prizes)** — "You're in" screen: payout wallet is bound in
   Settings by signing with a **Substrate** wallet (VFY pays on zkVerify chain).
   Rest has no Substrate wallet; create one only if we win. EVM 0x59 is the
   login identity, not the payout address.
3. **Tracks** (close 21 Nov):
   - **Wildcard** — public repo + demo/write-up + public HTTPS endpoint (form
     asks for one). Package "Bubub", the verifiable on-chain ops agent.
     Endpoint candidate: Cloudflare Worker (Rest's account has
     quote-api.restless-games15.workers.dev already; deploy path TBD — no
     wrangler files in workspace, likely dashboard UI with saved login).
   - **Creator Track** — thread/video/article, submitted from the dashboard
     (/dashboard/submissions). Must include #AgentGames; if posted on X also
     tag @ZKVProtocol. No X posting (Rest's rule) — publish as a public
     article (GitHub repo README doubles as the article link).
   - **Proof Gatekeeper** — daily rounds 13–21 Nov 17:30–05:30 WIB, needs a
     public HTTPS endpoint that stays up + Groth16 proving with the platform
     circuit (vkHash 0x6b79c6..., wasm/zkey on the site) + Kurier API key or
     funded Volta account. NOT feasible reliably from this VM (frequent
     restarts, no stable public endpoint). Skip unless infra changes.
   - **Steal the VFY** — Swiss rounds 13–17 Nov already running; strategy
     commitment was due before Round 1. Likely closed to new entrants.
4. **Files**: ./siwe-login.sh, ./complete-registration.py, ./cookies.txt
   (session), ./network-log.jsonl (submit request captured), ./register.html,
   ./register-authed.html, ./chunk-*.js (site JS bundle).
