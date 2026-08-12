#!/usr/bin/env python3
"""
📱 GPLinks Bypass Telegram Bot v2.1
Dual-layer: API key extraction (fast) → Playwright browser bypass (reliable)
"""

import asyncio, base64, hashlib, json, logging, os, re, sys, time
from datetime import datetime
from urllib.parse import urlparse, parse_qs, quote

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ── Optional imports ──
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass

CRYPTO_AVAILABLE = False
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    CRYPTO_AVAILABLE = True
except ImportError:
    pass

# ── Config ──────────────────────────────────────────
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8397171996:AAFZFT0ruUh4Augc4M6J19W7d9qKG5sHAVA")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
active_bypasses: dict[str, dict] = {}

SIGMA_HEADER_NAMES = ("x-request-id", "x-payload", "authorization", "x-data")
SIGMA_KEY = "k6kW8r#Tz3f;"
SIGMA_TARGET = "https://zoo0.pages.dev"
SIGMA_UA = "Dart/3.8 (dart:io)"


# ═══════════════════════════════════════════════
#  LAYER 1: API Key Extraction (sigma_study_v4)
# ═══════════════════════════════════════════════

def decode_b64_xor(cb64: str, xk: bytes) -> str:
    raw = base64.b64decode(cb64)
    out = bytearray(raw[i] ^ xk[i % len(xk)] for i in range(len(raw)))
    try:
        return out.decode("utf-8")
    except UnicodeDecodeError:
        txt = out.decode("latin1", errors="ignore")
        s, e = txt.find("{"), txt.rfind("}")
        if s != -1 and e != -1 and e > s: return txt[s:e+1]
        raise ValueError("No JSON")

def extract_baseurl(text: str) -> str:
    obj = json.loads(text)
    for k in ("baseUrl","baseurl","base_url"):
        if k in obj: return obj[k]
    raise ValueError("baseUrl missing")

def fetch_headers(target=SIGMA_TARGET) -> dict:
    s = requests.Session()
    s.headers.update({"User-Agent": SIGMA_UA})
    return dict(s.get(target, timeout=25, allow_redirects=True).headers)

def build_combined(hdrs: dict) -> str:
    return "".join(next((v.strip() for k,v in hdrs.items() if k.lower()==hn.lower()),"") for hn in SIGMA_HEADER_NAMES)

def fetch_key_flow(baseurl: str) -> tuple:
    s = requests.Session()
    s.headers.update({"User-Agent":"Mozilla/5.0"})
    j1 = s.get(baseurl.rstrip("/")+"/api/v1/auth/generate?server=1", timeout=30).json()
    ku = j1["data"]["keyUrl"]
    if "nanolinks" in ku: return _h_nano(ku, s)
    elif "arolinks" in ku: return _h_aro(ku, s)
    elif "lksfy" in ku: return _h_lksfy(ku, s)
    return _h_nano(ku, s)

def _h_nano(ku: str, s) -> tuple:
    eid = urlparse(ku).path.strip("/").split("/")[-1]
    r1 = s.get(f"https://nano.tackledsoul.com/includes/open.php?id={eid}", cookies={"tp":eid,"open":eid}, timeout=30, allow_redirects=False)
    if r1.status_code not in (301,302,303,307,308): return None,"Nano r1"
    nid = urlparse(r1.headers.get("Location","")).path.strip("/").split("/")[-1]
    r2 = s.get(f"https://vi-music.app/includes/open.php?id={nid}", cookies={"tp":nid,"open":nid}, timeout=30, allow_redirects=False)
    if r2.status_code not in (301,302,303,307,308): return None,"Nano r2"
    k = parse_qs(urlparse(r2.headers.get("Location","")).query).get("key",[None])[0]
    return (k,None) if k else (None,"Nano key missing")

def _h_aro(ku: str, s) -> tuple:
    eid = urlparse(ku).path.strip("/").split("/")[-1]
    r1 = s.get(ku, timeout=30)
    m = re.search(r'window\.location\.href\s*=\s*"([^"]+)"', r1.text)
    if not m: m = re.search(r'<a\s+href="([^"]+)"', r1.text)
    if not m: return None,"Aro redirect"
    r2 = s.get(ku, headers={"cookie":f"gt_uc_={eid}","referer":m.group(1)}, timeout=30)
    m2 = re.search(r'nofollow[^"]*href="(https?://[^"]+(?:key|code)=[^"&]+[^"]*)"', r2.text)
    if not m2: return None,"Aro key"
    km = re.search(r'(?:key|code)=([^&"]+)', m2.group(1))
    return (f"https://generateed.pages.dev/?key={km.group(1)}",None) if km else (None,"Aro key extract")

def _dec_lksfy(ct: str, alias: str):
    if not CRYPTO_AVAILABLE: return None
    try:
        kh = hashlib.sha256(("sDye71jNq5"+alias).encode()).hexdigest()[:32].encode()
        iv = hashlib.sha256(("7M9u8DG4X"+alias).encode()).hexdigest()[:16].encode()
        return unpad(AES.new(kh, AES.MODE_CBC, iv).decrypt(base64.b64decode(base64.b64decode(ct))), AES.block_size).decode("utf-8")
    except: return None

def _h_lksfy(ku: str, s) -> tuple:
    alias = urlparse(ku).path.strip("/").split("/")[-1]
    r1 = s.get(ku, headers={"referer":ku}, timeout=30, allow_redirects=False)
    rdr = r1.headers.get("Location","") if r1.status_code in (301,302,303,307,308) else ""
    r2 = s.get(ku, headers={"referer":rdr or ku}, timeout=30)
    m = re.search(r"var\s+base64\s*=\s*'([^']+)'", r2.text)
    if not m: return None,"Lksfy b64"
    html = _dec_lksfy(m.group(1), alias)
    if not html: return None,"Lksfy decrypt"
    csrf = (re.search(r'name="_csrfToken"[^>]*value="([^"]+)"', html) or type('',(),{'group':lambda s:''})()).group(1)
    ad = (re.search(r'name="ad_form_data"[^>]*value="([^"]+)"', html) or type('',(),{'group':lambda s:''})()).group(1)
    tf = (re.search(r'name="_Token\[fields\]"[^>]*value="([^"]+)"', html) or type('',(),{'group':lambda s:''})()).group(1)
    tu = (re.search(r'name="_Token\[unlocked\]"[^>]*value="([^"]+)"', html) or type('',(),{'group':lambda s:''})()).group(1)
    act = (re.search(r'action="([^"]+)"', html) or type('',(),{'group':lambda s:''})()).group(1)
    ckc = re.search(r'csrfToken=([^;]+)', r2.headers.get("set-cookie",""))
    time.sleep(5)
    hdrs = {"content-type":"application/x-www-form-urlencoded","x-requested-with":"XMLHttpRequest"}
    if ckc: hdrs["cookie"] = f"csrfToken={ckc.group(1)}"
    body = f"_method=POST&_csrfToken={quote(csrf)}&ad_form_data={quote(ad)}&_Token%5Bfields%5D={tf}&_Token%5Bunlocked%5D={quote(tu)}"
    r3 = s.post(f"https://lksfy.com{act}", headers=hdrs, data=body, timeout=30)
    j3 = r3.json()
    if "url" in j3 and j3["url"]:
        url_dec = _dec_lksfy(j3["url"], alias)
        if url_dec:
            km = re.search(r'[a-fA-F0-9]{8,}', url_dec)
            if km: return f"https://generateed.pages.dev/?key={km.group(0)}", None
    return None, f"Lksfy: {j3.get('message','?')}"

def api_bypass_gplinks(url: str) -> str | None:
    try:
        hdrs = fetch_headers()
        c = build_combined(hdrs)
        if not c.strip(): return None
        decoded = decode_b64_xor(c, SIGMA_KEY.encode())
        baseurl = extract_baseurl(decoded)
        key, err = fetch_key_flow(baseurl)
        return key if key else None
    except Exception as e:
        logger.warning(f"API error: {e}")
        return None


# ═══════════════════════════════════════════════
#  LAYER 2: Browser Bypass
# ═══════════════════════════════════════════════

def is_valid_dest(u: str) -> bool:
    skip = ["gplinks.co","gplinks.com","gplink.co","gplink.com",
            "skrresults.com","mrdrt.com","trustify.click",
            "rostelshute.shop","banchibipack.com","loginbreton.com",
            "google.com","doubleclick.net","googlesyndication.com",
            "generateed.pages.dev","cheatedgret.shop"]
    dom = urlparse(u).netloc.lower()
    return not any(dom == s or dom.endswith("."+s) for s in skip)

async def browser_bypass(url: str, cb=None) -> str | None:
    if not PLAYWRIGHT_AVAILABLE: return None
    steps, dest = 0, None
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage","--disable-gpu"])
        ctx = await b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151.0.0.0 Safari/537.36", viewport={"width":1366,"height":768})
        pg = await ctx.new_page()
        await pg.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>false});window.chrome={runtime:{}};")
        if cb: await cb("🌐 <b>Opening GPLinks...</b>")
        await pg.goto(url, wait_until="domcontentloaded", timeout=30000)
        for _ in range(15):
            if "skrresults" in pg.url.lower(): break
            await asyncio.sleep(1)
        if cb: await cb("🔄 <b>Clicking through steps...</b>")
        for _ in range(40):
            cur = pg.url
            if is_valid_dest(cur): dest = cur; break
            try:
                await pg.evaluate("(function(){var t=document.getElementById('myTimer');if(t)t.textContent='0';var d=document.getElementById('myTimerDiv');if(d)d.style.display='none';var v=document.getElementById('VerifyBtn');if(v){v.style.display='block';v.disabled=false;}var g=document.getElementById('GoNewxtDiv');if(g)g.style.display='block';document.querySelectorAll('button').forEach(function(b){if((b.textContent||'').toUpperCase().trim()==='CANCEL')b.click();});})();")
            except: pass
            await asyncio.sleep(0.5)
            try:
                ok = await pg.evaluate("(function(){var v=document.getElementById('VerifyBtn');if(v&&v.offsetParent){v.click();return'clicked';}return'no';})();")
                if ok == 'clicked': steps+=1; await asyncio.sleep(0.8)
            except: pass
            try: await pg.evaluate("(function(){var n=document.getElementById('NextBtn');if(n&&n.offsetParent)n.click();})();")
            except: pass
            try: await pg.evaluate("(function(){var f=document.getElementById('adsForm');if(f){var s=f.querySelector('[name=step_id]');if(s)s.value='5';var a=f.querySelector('[name=ad_impressions]');if(a)a.value='5';}})();")
            except: pass
            nu = pg.url
            if nu != cur and is_valid_dest(nu): dest = nu; break
            await asyncio.sleep(1.0)
        await b.close()
    if dest: return dest
    if steps >= 5: raise Exception("DEST_SERVER_DOWN")
    return None


# ═══════════════════════════════════════════════
#  Bot Router
# ═══════════════════════════════════════════════

async def bypass_gplinks(update: Update, url: str):
    cid = str(update.effective_chat.id)
    active_bypasses[cid] = {"status":"running","url":url,"start":time.time()}
    await update.effective_chat.send_message(f"⚡ <b>Processing...</b>\n🔗 <code>{url[:55]}...</code>", parse_mode=ParseMode.HTML)

    # Layer 1: API key (informational only)
    await update.effective_chat.send_message("🔍 <b>Extracting key...</b>", parse_mode=ParseMode.HTML)
    api_result = api_bypass_gplinks(url)
    if api_result:
        await update.effective_chat.send_message(f"🔑 Key: <code>{api_result}</code>", parse_mode=ParseMode.HTML)

    # Layer 2: Browser bypass (always run — key is not the destination)
    await update.effective_chat.send_message("🌐 <b>Browser bypass...</b>", parse_mode=ParseMode.HTML)
    if not PLAYWRIGHT_AVAILABLE:
        del active_bypasses[cid]
        raise Exception("Playwright unavailable on this server")

    async def cb(m): await update.effective_chat.send_message(m, parse_mode=ParseMode.HTML)
    dest = await browser_bypass(url, cb)
    elapsed = round(time.time() - active_bypasses[cid]["start"], 1)
    del active_bypasses[cid]
    if dest: return dest, elapsed
    raise Exception("DEST_SERVER_DOWN")


# ═══════════════════════════════════════════════
#  Telegram Handlers
# ═══════════════════════════════════════════════

def extract_url(t: str) -> str | None:
    m = re.search(r"https?://(?:www\.)?gplinks?\.(?:co|com)/[a-zA-Z0-9]+(?:\?[^\s]*)?", t)
    return m.group(0) if m else None

async def cmd_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("⚡ <b>GPLinks Bypass Bot v2.1</b>\n\n🔗 Koi bhi GPLinks link bhejo!\nAuto browser bypass\n\n<b>Example:</b>\n<code>https://gplinks.co/xxxxx</code>", parse_mode=ParseMode.HTML)

async def cmd_status(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if not active_bypasses:
        await u.message.reply_text("ℹ️ Idle")
    else:
        await u.message.reply_text("\n".join(f"• {ci}: <b>{i['status']}</b>" for ci,i in active_bypasses.items()), parse_mode=ParseMode.HTML)

async def on_msg(u: Update, c: ContextTypes.DEFAULT_TYPE):
    t = u.message.text.strip()
    cid = str(u.effective_chat.id)
    if OWNER_ID and u.effective_user.id != OWNER_ID:
        await u.message.reply_text("⛔ Private")
        return
    if cid in active_bypasses and active_bypasses[cid].get("status") not in ("done","error"):
        await u.message.reply_text("⏳ Processing...")
        return
    url = extract_url(t)
    if not url:
        await u.message.reply_text("❌ GPLinks link nahi mila!\nSend: <code>https://gplinks.co/xxxxx</code>", parse_mode=ParseMode.HTML)
        return
    try:
        dest, elapsed = await bypass_gplinks(u, url)
        await u.message.reply_text(f"✅ <b>Done!</b>\n🔗 <code>{dest}</code>\n⏱️ {elapsed}s\n<a href='{dest}'>Open →</a>", parse_mode=ParseMode.HTML, disable_web_page_preview=False)
    except Exception as e:
        if "DEST_SERVER_DOWN" in str(e):
            await u.message.reply_text("⚠️ <b>Destination DOWN!</b>\n✅ Steps complete\n❌ Server offline\n\n<b>Doosra link try karo!</b>", parse_mode=ParseMode.HTML)
        else:
            await u.message.reply_text(f"❌ {str(e)[:300]}", parse_mode=ParseMode.HTML)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_msg))
    logger.info("🤖 Bot v2.1 starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
