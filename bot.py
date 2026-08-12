#!/usr/bin/env python3
"""
📱 GPLinks Bypass Telegram Bot
Hosted on Railway.app — Real browser bypass via Playwright
"""

import asyncio
import logging
import os
import re
import time
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

from playwright.async_api import async_playwright

# ── Config ──────────────────────────────────────────
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8397171996:AAFZFT0ruUh4Augc4M6J19W7d9qKG5sHAVA")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))  # Optional: restrict to owner

# ── Logging ─────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ── Active bypass sessions ──────────────────────────
active_bypasses: dict[str, dict] = {}


def is_gplinks_url(text: str) -> bool:
    pattern = r"https?://(?:www\.)?gplinks?\.(?:co|com)/[a-zA-Z0-9]+"
    return bool(re.search(pattern, text))


def extract_gplinks_url(text: str) -> str | None:
    pattern = r"https?://(?:www\.)?gplinks?\.(?:co|com)/[a-zA-Z0-9]+(?:\?[^\s]*)?"
    match = re.search(pattern, text)
    return match.group(0) if match else None


def is_valid_destination(url: str) -> bool:
    skip_domains = [
        "gplinks.co", "gplinks.com", "gplink.co", "gplink.com",
        "skrresults.com", "mrdrt.com", "trustify.click",
        "rostelshute.shop", "banchibipack.com", "loginbreton.com",
        "google.com", "doubleclick.net", "googlesyndication.com",
    ]
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower()
    for skip in skip_domains:
        if domain == skip or domain.endswith("." + skip):
            return False
    return True


async def bypass_gplinks(update: Update, url: str) -> str | None:
    chat_id = str(update.effective_chat.id)
    active_bypasses[chat_id] = {
        "status": "starting", "step": 0, "url": url, "start_time": time.time(),
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage","--disable-gpu"],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
                viewport={"width":1366,"height":768},
                locale="en-US",
            )
            page = await context.new_page()

            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => false});
                window.chrome = {runtime: {}};
            """)

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Cloudflare wait
            for i in range(15):
                cur = page.url.lower()
                if "skrresults" in cur or "/best-" in cur or "/top-" in cur:
                    break
                await asyncio.sleep(1)

            steps_completed = 0
            destination_url = None

            for iteration in range(40):
                current_url = page.url

                if is_valid_destination(current_url):
                    destination_url = current_url
                    break

                # Kill timer + show buttons
                try:
                    await page.evaluate("""
                        (function(){
                            var t=document.getElementById('myTimer');
                            if(t)t.textContent='0';
                            var td=document.getElementById('myTimerDiv');
                            if(td)td.style.display='none';
                            var v=document.getElementById('VerifyBtn');
                            if(v){v.style.display='block';v.disabled=false;}
                            var g=document.getElementById('GoNewxtDiv');
                            if(g)g.style.display='block';
                        })();
                    """)
                except: pass

                await asyncio.sleep(0.5)

                # VERIFY click
                try:
                    ok = await page.evaluate("""
                        (function(){var v=document.getElementById('VerifyBtn');
                        if(v&&v.offsetParent){v.click();return'clicked';}return'no';})();
                    """)
                    if ok == 'clicked':
                        steps_completed += 1
                        await asyncio.sleep(1.0)
                except: pass

                # CONTINUE click
                try:
                    ok = await page.evaluate("""
                        (function(){var n=document.getElementById('NextBtn');
                        if(n&&n.offsetParent){n.click();return'clicked';}return'no';})();
                    """)
                except: pass

                # Form tracking
                try:
                    await page.evaluate("""
                        (function(){var f=document.getElementById('adsForm');
                        if(f){var s=f.querySelector('[name=step_id]');if(s)s.value='5';
                        var a=f.querySelector('[name=ad_impressions]');if(a)a.value='5';}})();
                    """)
                except: pass

                # Popup dismiss
                try:
                    await page.evaluate("""
                        document.querySelectorAll('button').forEach(function(b){
                            var x=(b.textContent||'').toUpperCase().trim();
                            if(x==='CANCEL')b.click();
                        });
                    """)
                except: pass

                new_url = page.url
                if new_url != current_url and is_valid_destination(new_url):
                    destination_url = new_url
                    break

                await asyncio.sleep(1.0)

            await browser.close()
            elapsed = round(time.time() - active_bypasses[chat_id]["start_time"], 1)

            if destination_url:
                active_bypasses[chat_id]["status"] = "done"
                return destination_url, elapsed
            elif steps_completed >= 5:
                raise Exception("DEST_SERVER_DOWN")
            return None, elapsed

    except Exception as e:
        logger.error(f"Bypass error: {e}")
        active_bypasses[chat_id]["status"] = "error"
        raise


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ <b>GPLinks Bypass Bot</b>\n\n"
        "🔗 Koi bhi <b>GPLinks short link</b> bhejo — "
        "main real browser se bypass karke <b>destination URL</b> de dunga!\n\n"
        "⏱️ Bypass time: ~30-60 seconds\n"
        "📊 Live progress dikhegi!\n\n"
        "<b>Example:</b>\n<code>https://gplinks.co/xxxxx</code>",
        parse_mode=ParseMode.HTML,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = str(update.effective_chat.id)

    if OWNER_ID and update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Private bot. Only owner can use.")
        return

    if chat_id in active_bypasses and active_bypasses[chat_id]["status"] not in ("done", "error"):
        await update.message.reply_text("⏳ Already processing! Please wait...", parse_mode=ParseMode.HTML)
        return

    url = extract_gplinks_url(text)
    if not url:
        await update.message.reply_text(
            "❌ GPLinks link nahi mila!\nSend: <code>https://gplinks.co/xxxxx</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    await update.message.reply_text(
        "⚡ <b>Processing...</b>\n🔗 <code>" + url[:50] + "...</code>\n⏳ ~30-60 seconds...",
        parse_mode=ParseMode.HTML,
    )

    try:
        destination, elapsed = await bypass_gplinks(update, url)
        if destination:
            await update.message.reply_text(
                f"✅ <b>Bypass Successful!</b>\n\n"
                f"🔗 <b>Destination:</b>\n<code>{destination}</code>\n\n"
                f"⏱️ Time: <b>{elapsed}s</b>\n\n"
                f"<a href='{destination}'>Open Link →</a>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
        else:
            await update.message.reply_text(
                "⚠️ Destination not found. Try another link.",
                parse_mode=ParseMode.HTML,
            )
    except Exception as e:
        if "DEST_SERVER_DOWN" in str(e):
            await update.message.reply_text(
                "⚠️ <b>Destination Server DOWN!</b>\n\n"
                "✅ All 5 steps completed!\n"
                "❌ Destination server offline/404.\n\n"
                "<b>Koi doosra GPLinks link try karo!</b>",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text(f"❌ Error: {str(e)[:200]}", parse_mode=ParseMode.HTML)
    finally:
        if chat_id in active_bypasses:
            del active_bypasses[chat_id]


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not active_bypasses:
        await update.message.reply_text("ℹ️ No active bypass sessions.")
        return
    lines = ["<b>📊 Active Sessions:</b>\n"]
    for cid, info in active_bypasses.items():
        lines.append(f"• Chat {cid}: <b>{info['status']}</b> | URL: <code>{info.get('url','?')[:30]}...</code>")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


def main():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("🤖 Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
