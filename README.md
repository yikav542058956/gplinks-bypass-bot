# GPLinks Bypass Telegram Bot

Telegram bot that bypasses GPLinks short links using Playwright real browser automation.

## Usage
1. Send `/start` to the bot on Telegram
2. Send any GPLinks URL (e.g., `https://gplinks.co/xxxxx`)
3. Bot will automatically bypass and return the destination URL

## Deploy on Railway
1. Fork this repo
2. Go to [Railway.app](https://railway.app)
3. Deploy from GitHub repo
4. Set environment variable: `TELEGRAM_BOT_TOKEN`
5. Done!

## Requirements
- Python 3.11+
- Playwright (Chromium)
- python-telegram-bot
- Railway account (or any Docker host with 1GB+ RAM)
