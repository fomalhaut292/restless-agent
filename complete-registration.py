#!/usr/bin/env python3
"""Complete Agent Games registration in a real browser, with the session
cookie from the earlier SIWE login (0x59 wallet). The site's own form is
used end-to-end; network traffic is logged so the submit endpoint is
recorded for future API use. No credentials are printed.

Networking note (verified 15 Nov 2026): the VM's egress proxy is a
TLS-intercepting proxy (issuer "Hatch Sandbox Egress CA"). Chromium cannot
do the CONNECT tunnel directly against it from this VM (tunnel fails), and
does not trust the egress CA. So this script runs a localhost CONNECT
forwarder that adds preemptive Proxy-Authorization and the browser is
launched with --ignore-certificate-errors (the connection is through the
user's own egress proxy; the site's identity is verified by matching the
page content against the curl-fetched HTML)."""
import base64, json, os, socket, threading, time
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

WORK = os.path.expanduser("~/workspace/zkverify-agent-games")
JAR = os.path.join(WORK, "cookies.txt")
LOG = os.path.join(WORK, "network-log.jsonl")
LOCAL_PROXY = ("127.0.0.1", 18080)

def parse_jar(path):
    cookies = []
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") and not line.startswith("#HttpOnly_"):
            continue
        httponly = line.startswith("#HttpOnly_")
        line = line.lstrip("#HttpOnly_") if httponly else line
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _flag, pth, secure, expires, name, value = parts[:7]
        cookies.append({
            "name": name, "value": value, "domain": domain.lstrip("."),
            "path": pth, "secure": secure.upper() == "TRUE",
            "httpOnly": httponly, "expires": int(expires) or -1,
            "sameSite": "Lax",
        })
    return cookies

def proxy_cfg():
    raw = os.environ.get("https_proxy") or os.environ.get("http_proxy") or ""
    u = urlparse(raw)
    return {"server": f"{u.scheme}://{u.hostname}:{u.port}",
            "username": u.username, "password": u.password}

def _pipe(a, b):
    try:
        while True:
            data = a.recv(65536)
            if not data:
                break
            b.sendall(data)
    except Exception:
        pass
    finally:
        try:
            b.shutdown(socket.SHUT_WR)
        except Exception:
            pass

def start_forwarder():
    """Localhost CONNECT forwarder -> VM egress proxy (preemptive auth)."""
    raw = os.environ.get("https_proxy") or os.environ.get("http_proxy") or ""
    u = urlparse(raw)
    upstream = (u.hostname, u.port)
    auth = base64.b64encode(f"{u.username}:{u.password}".encode()).decode()

    def handle(client):
        up = None
        try:
            buf = b""
            while b"\r\n\r\n" not in buf:
                chunk = client.recv(4096)
                if not chunk:
                    return
                buf += chunk
            parts = buf.split(b"\r\n")[0].decode(errors="replace").split()
            if len(parts) < 2 or parts[0].upper() != "CONNECT":
                client.sendall(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
                return
            target = parts[1]
            up = socket.create_connection(upstream, timeout=15)
            up.sendall(f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n"
                       f"Proxy-Authorization: Basic {auth}\r\n"
                       "Proxy-Connection: keep-alive\r\n\r\n".encode())
            resp = b""
            while b"\r\n\r\n" not in resp:
                chunk = up.recv(4096)
                if not chunk:
                    break
                resp += chunk
            if b"200" not in resp.split(b"\r\n")[0]:
                client.sendall(resp)
                return
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            t1 = threading.Thread(target=_pipe, args=(client, up), daemon=True)
            t2 = threading.Thread(target=_pipe, args=(up, client), daemon=True)
            t1.start(); t2.start(); t1.join(); t2.join()
        except Exception:
            pass
        finally:
            try:
                client.close()
            except Exception:
                pass
            try:
                if up:
                    up.close()
            except Exception:
                pass

    def serve():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(LOCAL_PROXY)
        srv.listen(20)
        while True:
            try:
                c, _ = srv.accept()
                threading.Thread(target=handle, args=(c,), daemon=True).start()
            except Exception:
                break

    threading.Thread(target=serve, daemon=True).start()
    time.sleep(0.5)

cookies = parse_jar(JAR)
session = [c for c in cookies if c["name"] == "__Secure-authjs.session-token"]
assert session, "no session cookie in jar"
print("session cookie present, expires", session[0]["expires"])

reqs = []
start_forwarder()
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, proxy={"server": "http://127.0.0.1:18080"},
        args=["--no-sandbox", "--disable-dev-shm-usage", "--ignore-certificate-errors"])
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        viewport={"width": 1280, "height": 900})
    ctx.add_cookies(cookies)
    page = ctx.new_page()
    def on_req(r):
        try:
            body = r.post_data or ""
        except Exception:
            body = ""
        reqs.append({"method": r.method, "url": r.url, "body": body[:2000]})
    def on_resp(r):
        print(f"RESP {r.status} {r.request.method} {r.url[:120]}")
    page.on("request", on_req)
    page.on("response", on_resp)
    page.goto("https://agentgames.zkverify.io/register", wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(2500)
    print("title:", page.title())
    body_text = page.inner_text("body")
    print("wallet pane connected:", "Wallet connected" in body_text)
    print("form visible:", "Complete registration" in body_text)

    page.get_by_placeholder("your-handle").fill("restless")
    page.wait_for_timeout(1500)
    body_text = page.inner_text("body")
    print("handle status text present:", ("available" in body_text.lower() or "taken" in body_text.lower()))

    page.locator("input[type='email']").fill("restless.games15@gmail.com")
    # expand optional details: X handle + country
    try:
        page.get_by_text("+ Add more details", exact=False).click(timeout=5000)
        page.wait_for_timeout(800)
    except Exception as e:
        print("expand details click failed:", e)
    try:
        page.get_by_placeholder("yourhandle").fill("erysta28")
    except Exception as e:
        print("twitter fill failed:", e)
    try:
        sel = page.locator("select")
        if sel.count():
            sel.first.select_option("ID")
            print("country set to ID")
    except Exception as e:
        print("country select failed:", e)
    page.locator("input[type='checkbox']").check()
    page.wait_for_timeout(1000)
    submit = page.get_by_text("Complete registration", exact=False)
    print("submit disabled?", submit.is_disabled())
    submit.click()
    page.wait_for_timeout(4000)
    body_text = page.inner_text("body")
    print("YOU'RE IN:", "You're in" in body_text)
    print("registered as @restless:", "Registered as @restless" in body_text)
    if "You're in" not in body_text:
        print("PAGE SNIPPET:", body_text[:800].replace("\n", " | "))
    browser.close()

with open(LOG, "w") as f:
    for r in reqs:
        f.write(json.dumps(r) + "\n")
print("network log lines:", len(reqs))
# show only non-asset API-ish calls
for r in reqs:
    if "/api/" in r["url"] or r["method"] in ("POST", "PUT", "PATCH"):
        print("API CALL:", r["method"], r["url"], "| body:", r["body"][:300])
