#!/usr/bin/env python3
"""
📱 GPLinks Bypass Telegram Bot v2.0
Dual-layer bypass: API-first (fast), Playwright browser (fallback)
Integrates sigma_study_v4 logic for nanolinks/arolinks/lksfy handlers
"""

import asyncio, base64, hashlib, json, logging, os, re, sys, time
from datetime import datetime
from urllib.parse import urlparse, parse_qs, quote

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Optional: Playwright for browser fallback
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

# Optional: Crypto for lksfy AES decryption
CRYPTO_AVAILABLE = False
try:
    from Crypto.Cipher import AES
    CRYPTO_AVAILABLE = True
except ImportError:
    pass

# ── Config ──────────────────────────────────────────
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8397171996:AAFZFT0ruUh4Augc4M6J19W7d9qKG5sHAVA")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

active_bypasses: dict[str, dict] = {}

# ── Constants from sigma_study_v4 ────────────────────
SIGMA_HEADER_NAMES = ("x-request-id", "x-payload", "authorization", "x-data")
SIGMA_KEY = "k6kW8r#Tz3f;"
SIGMA_DEFAULT_TARGET = "https://zoo0.pages.dev"
SIGMA_USER_AGENT = "Dart/3.8 (dart:io)"


# ══════════════════════════════════════════════════════
#  LAYER 1: API Bypass (sigma_study_v4 logic)
# ══════════════════════════════════════════════════════

def decode_b64_xor(combined_b64: str, xor_key: bytes) -> str:
    raw = base64.b64decode(combined_b64)
    out = bytearray(len(raw))
    for i, b in enumerate(raw):
        out[i] = b ^ xor_key[i % len(xor_key)]
    try:
        return out.decode("utf-8")
    except UnicodeDecodeError:
        txt = out.decode("latin1", errors="ignore")
        start = txt.find("{")
        end = txt.rfind("}")
        if start != -1 and end != -1 and end > start:
            return txt[start:end+1]
        raise ValueError("Not UTF-8 and no JSON found")


def extract_baseurl(decoded_text: str) -> str:
    obj = json.loads(decoded_text)
    for k in ("baseUrl", "baseurl", "base_url"):
        if k in obj:
            return obj[k]
    raise ValueError("baseUrl not found")


def fetch_initial_headers(target_url: str = SIGMA_DEFAULT_TARGET) -> dict:
    sess = requests.Session()
    sess.headers.update({"User-Agent": SIGMA_USER_AGENT})
    resp = sess.get(target_url, timeout=25, allow_redirects=True)
    return dict(resp.headers)


def build_combined(headers: dict) -> str:
    parts = []
    for hn in SIGMA_HEADER_NAMES:
        val = None
        for k, v in headers.items():
            if k.lower() == hn.lower():
                val = v.strip()
                break
        parts.append(val or "")
    return "".join(parts)


def fetch_key_flow(baseurl: str, user_agent: str = None) -> tuple:
    sess = requests.Session()
    ua = user_agent or "Mozilla/5.0 (compatible; Python script)"
    sess.headers.update({"User-Agent": ua})
    url1 = baseurl.rstrip("/") + "/api/v1/auth/generate?server=1"
    r1 = sess.get(url1, timeout=30)
    r1.raise_for_status()
    j1 = r1.json()
    key_url = j1["data"]["keyUrl"]
    logger.info(f"keyUrl: {key_url}")
    if "nanolinks" in key_url:
        return handle_nano_links(key_url, sess)
    elif "arolinks" in key_url:
        return handle_aro_links(key_url, sess)
    elif "lksfy" in key_url:
        return handle_lksfy(key_url, sess)
    else:
        return handle_nano_links(key_url, sess)


def handle_nano_links(key_url: str, sess: requests.Session) -> tuple:
    extracted_id = urlparse(key_url).path.strip("/").split("/")[-1]
    url1 = f"https://nano.tackledsoul.com/includes/open.php?id={extracted_id}"
    r1 = sess.get(url1, cookies={"tp": extracted_id, "open": extracted_id}, timeout=30, allow_redirects=False)
    if r1.status_code in (301, 302, 303, 307, 308):
        redirect = r1.headers.get("Location", "")
        new_id = urlparse(redirect).path.strip("/").split("/")[-1]
        url2 = f"https://vi-music.app/includes/open.php?id={new_id}"
        r2 = sess.get(url2, cookies={"tp": new_id, "open": new_id}, timeout=30, allow_redirects=False)
        if r2.status_code in (301, 302, 303, 307, 308):
            final = r2.headers.get("Location", "")
            key = parse_qs(urlparse(final).query).get("key", [None])[0]
            if key:
                return key, None
    return None, "Nano redirect chain failed"


def handle_aro_links(key_url: str, sess: requests.Session) -> tuple:
    identifier = urlparse(key_url).path.strip("/").split("/")[-1]
    r1 = sess.get(key_url, timeout=30)
    if r1.status_code != 200:
        return None, f"Aro status {r1.status_code}"
    m = re.search(r'window\.location\.href\s*=\s*"([^"]+)"', r1.text)
    if not m:
        m = re.search(r'<a\s+href="([^"]+)"', r1.text)
    if not m:
        return None, "Aro redirect URL not found"
    redirect_url = m.group(1)
    headers = {"cookie": f"gt_uc_={identifier}", "referer": redirect_url}
    r2 = sess.get(key_url, headers=headers, timeout=30)
    if r2.status_code != 200:
        return None, f"Aro step2 status {r2.status_code}"
    m = re.search(r'nofollow[^"]*href="(https?://[^"]+key=[^"&]+[^"]*)"', r2.text)
    if not m:
        m = re.search(r'nofollow[^"]*href="(https?://[^"]+code=[^"&]+[^"]*)"', r2.text)
    if m:
        final_url = m.group(1)
        km = re.search(r'(?:key|code)=([^&"]+)', final_url)
        if km:
            return km.group(1), None
    return None, "Aro key not found"


def decrypt_lksfy(ciphertext: str, alias: str) -> str | None:
    if not CRYPTO_AVAILABLE:
        return None
    try:
        key_src = "sDye71jNq5" + alias
        iv_src = "7M9u8DG4X" + alias
        key_hash = hashlib.sha256(key_src.encode()).hexdigest()[:32].encode()
        iv_hash = hashlib.sha256(iv_src.encode()).hexdigest()[:16].encode()
        raw = base64.b64decode(base64.b64decode(ciphertext))
        cipher = AES.new(key_hash, AES.MODE_CBC, iv=iv_hash)
        return cipher.decrypt(raw).decode("utf-8", errors="ignore")
    except Exception:
        return None


def extract_lksfy_form(html: str) -> dict:
    return {
        "csrf": re.search(r'name="_csrfToken"[^>]*value="([^"]+)"', html),
        "ad_data": re.search(r'name="ad_form_data"[^>]*value="([^"]+)"', html),
        "token_fields": re.search(r'name="_Token\[fields\]"[^>]*value="([^"]+)"', html),
        "token_unlocked": re.search(r'name="_Token\[unlocked\]"[^>]*value="([^"]+)"', html),
        "action": re.search(r'action="([^"]+)"', html),
    }


def handle_lksfy(key_url: str, sess: requests.Session) -> tuple:
    alias = urlparse(key_url).path.strip("/").split("/")[-1]
    logger.info(f"Lksfy alias: {alias}")
    r1 = sess.get(key_url, headers={"referer": key_url}, timeout=30, allow_redirects=False)
    if r1.status_code in (301, 302, 303, 307, 308):
        redirect = r1.headers.get("Location", "")
        r2 = sess.get(key_url, headers={"referer": redirect}, timeout=30)
    else:
        r2 = r1
    if r2.status_code != 200:
        return None, f"Lksfy step2 status {r2.status_code}"
    m = re.search(r"var\s+base64\s*=\s*'([^']+)'", r2.text)
    if not m:
        return None, "Lksfy base64 not found"
    html = decrypt_lksfy(m.group(1), alias)
    if not html:
        return None, "Lksfy decryption failed"
    fd = extract_lksfy_form(html)
    csrf = fd["csrf"].group(1) if fd["csrf"] else ""
    action = fd["action"].group(1) if fd["action"] else ""
    csrf_cookie = re.search(r'csrfToken=([^;]+)', r2.headers.get("set-cookie", ""))
    post_url = f"https://lksfy.com{action}"
    body = (
        f"_method=POST"
        f"&_csrfToken={quote(csrf)}"
        f"&ad_form_data={quote(fd['ad_data'].group(1) if fd['ad_data'] else '')}"
        f"&_Token%5Bfields%5D={fd['token_fields'].group(1) if fd['token_fields'] else ''}"
        f"&_Token%5Bunlocked%5D={quote(fd['token_unlocked'].group(1) if fd['token_unlocked'] else '')}"
    )
    headers = {
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "x-requested-with": "XMLHttpRequest",
    }
    if csrf_cookie:
        headers["cookie"] = f"csrfToken={csrf_cookie.group(1)}"
    time.sleep(5)
    r3 = sess.post(post_url, headers=headers, data=body, timeout=30)
    if r3.status_code != 200:
        return None, f"Lksfy POST status {r3.status_code}"
    j3 = r3.json()
    # Note: lksfy sometimes returns "Captcha Error" even with valid URL
    if "url" in j3 and j3["url"]:
        url_dec = decrypt_lksfy(j3["url"], alias)
        if url_dec:
            km = re.search(r'(?:key|code)=([^&"\\s]+)', url_dec)
            if km:
                key = re.sub(r'[^a-zA-Z0-9_=-]', '', km.group(1))
                return key, None
    if j3.get("status") != "success":
        return None, f"Lksfy error: {j3.get('message')}"
    url_dec = decrypt_lksfy(j3["url"], alias)
    if url_dec:
        km = re.search(r'(?:key|code)=([^&"\\s]+)', url_dec)
        if km:
            key = re.sub(r'[^a-zA-Z0-9_=-]', '', km.group(1))
            return key, None
    return None, "Lksfy key not found"


def api_bypass_gplinks(link_url: str) -> str | None:
    try:
        headers = fetch_initial_headers()
        combined = build_combined(headers)
        if not combined.strip():
            return None
        xor_key = SIGMA_KEY.encode("utf-8")
        decoded = decode_b64_xor(combined, xor_key)
        baseurl = extract_baseurl(decoded)
        logger.info(f"API bypass baseUrl: {baseurl}")
        key, error = fetch_key_flow(baseurl)
        if key:
            logger.info(f"API bypass key: {key[:20]}...")
            return key
        logger.warning(f"API bypass failed: {error}")
        return None
    except Exception as e:
        logger.warning(f"API bypass error: {e}")
        return None


# ══════════════════════════════════════════════════════
#  LAYER 2: Playwright Browser Bypass (fallback)
# ══════════════════════════════════════════════════════

def is_valid_destination(url: str) -> bool:
    skip = ["gplinks.co","gplinks.com","gplink.co","gplink.com",
            "skrresults.com","mrdrt.com","trustify.click",
            "rostelshute.shop","banchibipack.com","loginbreton.com",
            "google.com","doubleclick.net","googlesyndication.com"]
    domain = urlparse(url).netloc.lower()
    return not any(domain == s or domain.endswith("."+s) for s in skip)


async def browser_bypass_gplinks(url: str, progress_callback=None) -> str | None:
    if not PLAYWRIGHT_AVAILABLE:
        return None
    steps = 0
    dest = None
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage","--disable-gpu"]
        )
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0.0.0 Safari/537.36",
            viewport={"width":1366,"height":768}
        )
        page = await ctx.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator,'webdriver',{get:()=>false});
            window.chrome={runtime:{}};
        """)
        if progress_callback:
            await progress_callback("🌐 <b>Browser Bypass</b> — Opening link...")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        for _ in range(15):
            if "skrresults" in page.url.lower():
                break
            await asyncio.sleep(1)
        if progress_callback:
            await progress_callback("🔄 <b>Bypass Loop</b> — Clicking through steps...")
        for _ in range(40):
            current_url = page.url
            if is_valid_destination(current_url):
                dest = current_url
                break
            try:
                await page.evaluate("""
                    (function(){
                        var t=document.getElementById('myTimer');if(t)t.textContent='0';
                        var td=document.getElementById('myTimerDiv');if(td)td.style.display='none';
                        var v=document.getElementById('VerifyBtn');if(v){v.style.display='block';v.disabled=false;}
                        var g=document.getElementById('GoNewxtDiv');if(g)g.style.display='block';
                        document.querySelectorAll('button').forEach(function(b){
                            if((b.textContent||'').toUpperCase().trim()==='CANCEL')b.click();
                        });
                    })();
                """)
            except: pass
            await asyncio.sleep(0.5)
            try:
                ok = await page.evaluate("(function(){var v=document.getElementById('VerifyBtn');if(v&&v.offsetParent){v.click();return'clicked';}return'no';})();")
                if ok == 'clicked':
                    steps += 1
                    if progress_callback:
                        await progress_callback(f"🖱️ <b>Step {min(steps,5)}/5</b> — VERIFY")
                    await asyncio.sleep(0.8)
            except: pass
            try:
                await page.evaluate("(function(){var n=document.getElementById('NextBtn');if(n&&n.offsetParent){n.click();}})();")
            except: pass
            try:
                await page.evaluate("(function(){var f=document.getElementById('adsForm');if(f){var s=f.querySelector('[name=step_id]');if(s)s.value='5';var a=f.querySelector('[name=ad_impressions]');if(a)a.value='5';}})();")
            except: pass
            new_url = page.url
            if new_url != current_url and is_valid_destination(new_url):
                dest = new_url
                break
            await asyncio.sleep(1.0)
        await browser.close()
    if dest:
        return dest
    if steps >= 5:
        raise Exception("DEST_SERVER_DOWN")
    return None


# ══════════════════════════════════════════════════════
#  Main Bypass Router
# ══════════════════════════════════════════════════════

async def bypass_gplinks(update: Update, url: str) -> str:
    chat_id = str(update.effective_chat.id)
    active_bypasses[chat_id] = {"status":"starting","url":url,"start_time":time.time()}
    await update.effective_chat.send_message(
        "⚡ <b>GPLinks Bypass Started!</b>\n🔗 <code>" + url[:55] + "...</code>",
        parse_mode=ParseMode.HTML
    )
    await update.effective_chat.send_message("🔍 <b>Trying API bypass...</b>", parse_mode=ParseMode.HTML)
    result = api_bypass_gplinks(url)
    if result:
        elapsed = round(time.time() - active_bypasses[chat_id]["start_time"], 1)
        del active_bypasses[chat_id]
        return result, elapsed, "api"
    await update.effective_chat.send_message(
        "⚠️ API bypass failed. Trying <b>browser bypass</b>...", parse_mode=ParseMode.HTML
    )
    if not PLAYWRIGHT_AVAILABLE:
        raise Exception("Playwright not installed — browser bypass unavailable")
    async def progress(msg):
        await update.effective_chat.send_message(msg, parse_mode=ParseMode.HTML)
    dest = await browser_bypass_gplinks(url, progress)
    elapsed = round(time.time() - active_bypasses[chat_id]["start_time"], 1)
    del active_bypasses[chat_id]
    if dest:
        return dest, elapsed, "browser"
    raise Exception("DEST_SERVER_DOWN")


# ══════════════════════════════════════════════════════
#  Telegram Bot Handlers
# ══════════════════════════════════════════════════════

def extract_gplinks_url(text: str) -> str | None:
    m = re.search(r"https?://(?:www\.)?gplinks?\.(?:co|com)/[a-zA-Z0-9]+(?:\?[^\s]*)?", text)
    return m.group(0) if m else None


async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ <b>GPLinks Bypass Bot v2.0</b>\n\n"
        "🔗 Koi bhi <b>GPLinks short link</b> bhejo!\n"
        "Dual-layer bypass: API → Browser\n\n"
        "<b>Example:</b>\n<code>https://gplinks.co/xxxxx</code>",
        parse_mode=ParseMode.HTML
    )


async def handle_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    cid = str(update.effective_chat.id)
    if OWNER_ID and update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Private bot.")
        return
    if cid in active_bypasses and active_bypasses[cid].get("status") not in ("done","error"):
        await update.message.reply_text("⏳ Already processing...")
        return
    url = extract_gplinks_url(text)
    if not url:
        await update.message.reply_text(
            "❌ GPLinks link nahi mila!\nSend: <code>https://gplinks.co/xxxxx</code>",
            parse_mode=ParseMode.HTML
        )
        return
    try:
        destination, elapsed, method = await bypass_gplinks(update, url)
        method_label = "API" if method == "api" else "Browser"
        await update.message.reply_text(
            f"✅ <b>Bypass Successful!</b> ({method_label})\n\n"
            f"🔗 <b>Destination:</b>\n<code>{destination}</code>\n\n"
            f"⏱️ Time: <b>{elapsed}s</b>\n\n"
            f"<a href='{destination}'>Open Link →</a>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
        )
    except Exception as e:
        if "DEST_SERVER_DOWN" in str(e):
            await update.message.reply_text(
                "⚠️ <b>Destination Server DOWN!</b>\n\n"
                "✅ All steps completed!\n❌ Destination offline/404.\n\n<b>Koi doosra link try karo!</b>",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text(f"❌ <b>Error:</b> {str(e)[:300]}", parse_mode=ParseMode.HTML)


async def status_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not active_bypasses:
        await update.message.reply_text("ℹ️ No active sessions.")
        return
    lines = ["<b>📊 Active:</b>"]
    for cid, info in active_bypasses.items():
        lines.append(f"• Chat {cid}: <b>{info['status']}</b> — {info.get('url','?')[:40]}...")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    logger.info("🤖 Bot v2.0 starting (API + Browser dual-layer)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
