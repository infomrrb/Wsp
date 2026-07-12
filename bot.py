import os
import asyncio
import sqlite3
from datetime import datetime

# ================== ১. কনফিগারেশন (শুধু এনভায়রনমেন্ট থেকে পড়ে) ==================
BOT_TOKEN = os.environ.get("8753784982:AAEIZmLXTMETbhYcdkS83WS5TbpRKvePEEA")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN environment variable is not set! Please set it in Render Environment tab.")

ADMIN_IDS = []
admin_str = os.environ.get("ADMIN_IDS", "")
if admin_str:
    ADMIN_IDS = [int(x.strip()) for x in admin_str.split(",") if x.strip()]
if not ADMIN_IDS:
    raise ValueError("❌ ADMIN_IDS environment variable is not set! Please set it in Render Environment tab.")

# ================== ২. ইমপোর্ট (ডিপেন্ডেন্সি) ==================
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ================== ৩. ডাটাবেস (SQLite) ==================
DB_PATH = "bot_data.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, added_by INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, action TEXT, details TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
        for uid in ADMIN_IDS:
            conn.execute("INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)", (uid, 0))
        conn.commit()

def is_admin(user_id: int) -> bool:
    with get_db() as conn:
        return conn.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)).fetchone() is not None

def get_all_admins():
    with get_db() as conn:
        return conn.execute("SELECT user_id FROM admins").fetchall()

def add_admin(user_id: int, added_by: int):
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)", (user_id, added_by))
        conn.commit()

def remove_admin(user_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        conn.commit()

def log_action(admin_id, action, details=""):
    with get_db() as conn:
        conn.execute("INSERT INTO logs (admin_id, action, details) VALUES (?, ?, ?)", (admin_id, action, details))
        conn.commit()

def get_recent_logs(limit=10):
    with get_db() as conn:
        return conn.execute("SELECT * FROM logs ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()

# ================== ৪. ইউটিলিটি ==================
def split_ids(raw: str):
    return [x.strip() for x in raw.replace(",", " ").split() if x.strip().lstrip("-").isdigit()]

SEMAPHORE = asyncio.Semaphore(30)
async def rate_limited_send(func, *args, **kwargs):
    async with SEMAPHORE:
        return await func(*args, **kwargs)

# ================== ৫. এফএসএম (উইজার্ড স্টেট) ==================
class BroadcastState(StatesGroup):
    waiting_for_targets = State()
    waiting_for_message = State()
    waiting_for_media = State()
    waiting_for_count = State()
    waiting_for_delay = State()

# ================== ৬. বট ও রাউটার ==================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
router = Router()
dp = Dispatcher()
dp.include_router(router)

running_tasks = {}  # ইউজার আইডি অনুযায়ী টাস্ক ট্র্যাক

async def ensure_admin(message: Message = None, callback: CallbackQuery = None):
    uid = message.from_user.id if message else callback.from_user.id
    if not is_admin(uid):
        if message: await message.answer("⛔ আপনি অ্যাডমিন নন।")
        else: await callback.answer("⛔ অ্যাডমিন নন", show_alert=True)
        return False
    return True

# ================== ৭. কমান্ডসমূহ ==================
@router.message(Command("start"))
async def start_cmd(message: Message):
    if not await ensure_admin(message): return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 ব্রডকাস্ট", callback_data="menu_broadcast")],
        [InlineKeyboardButton(text="👥 অ্যাডমিন", callback_data="menu_admins"),
         InlineKeyboardButton(text="📜 লগ", callback_data="menu_logs")],
    ])
    await message.answer("🔐 **অ্যাডমিন প্যানেল**\nনিচের বাটন ব্যবহার করুন।", reply_markup=kb)

@router.callback_query(F.data.startswith("menu_"))
async def menu_handler(callback: CallbackQuery):
    if not await ensure_admin(callback=callback): return
    action = callback.data.split("_")[1]
    if action == "broadcast":
        await callback.message.delete()
        await callback.message.answer("📢 **ব্রডকাস্ট**\n`/broadcast` কমান্ড দিন উইজার্ড শুরু করতে।")
    elif action == "admins":
        admins = get_all_admins()
        txt = "👥 **অ্যাডমিন লিস্ট**\n\n"
        for a in admins: txt += f"• `{a['user_id']}`\n"
        txt += "\n➕ `/add_admin <id>`\n➖ `/remove_admin <id>`"
        await callback.message.edit_text(txt)
    elif action == "logs":
        logs = get_recent_logs()
        txt = "📜 **সর্বশেষ লগ**\n\n" + "\n".join([f"`{l['timestamp']}` → {l['action']}" for l in logs]) or "কোনো লগ নেই।"
        await callback.message.edit_text(txt[:4000])
    await callback.answer()

@router.message(Command("broadcast"))
async def broadcast_cmd(message: Message, state: FSMContext):
    if not await ensure_admin(message): return
    await state.set_state(BroadcastState.waiting_for_targets)
    await message.answer("📢 **ধাপ ১/৫**\nটার্গেট আইডি দিন (কমা/স্পেস দিয়ে):\nউদা: `123, 456, 789`\n'cancel' লিখে বাতিল করুন।")

@router.message(BroadcastState.waiting_for_targets)
async def step_targets(msg: Message, state: FSMContext):
    if msg.text.lower() == "cancel": await state.clear(); return await msg.answer("❌ বাতিল।")
    ids = split_ids(msg.text)
    if not ids: return await msg.answer("⚠️ কোনো বৈধ আইডি নেই। আবার চেষ্টা করুন।")
    await state.update_data(targets=ids)
    await state.set_state(BroadcastState.waiting_for_message)
    await msg.answer("📝 **ধাপ ২/৫**\nমেসেজ টেক্সট লিখুন:")

@router.message(BroadcastState.waiting_for_message)
async def step_msg(msg: Message, state: FSMContext):
    if msg.text.lower() == "cancel": await state.clear(); return await msg.answer("❌ বাতিল।")
    await state.update_data(message_text=msg.text)
    await state.set_state(BroadcastState.waiting_for_media)
    await msg.answer("🖼️ **ধাপ ৩/৫**\nমিডিয়া টাইপ লিখুন:\n`text` / `photo` / `video` / `document`\n'skip' দিন যদি মিডিয়া না চান।")

@router.message(BroadcastState.waiting_for_media)
async def step_media(msg: Message, state: FSMContext):
    if msg.text.lower() == "cancel": await state.clear(); return await msg.answer("❌ বাতিল।")
    media_type = msg.text.lower()
    if media_type not in ["text", "photo", "video", "document", "skip"]:
        return await msg.answer("⚠️ ভুল টাইপ। `text`, `photo`, `video`, `document` বা `skip` দিন।")
    await state.update_data(media_type=media_type)
    
    if media_type == "text" or media_type == "skip":
        await state.set_state(BroadcastState.waiting_for_count)
        await msg.answer("🔢 **ধাপ ৪/৫**\nপ্রতি আইডিতে কতবার পাঠাবেন? (সংখ্যা)")
    else:
        await state.set_state(BroadcastState.waiting_for_media_file)
        await msg.answer(f"📁 {media_type} আপলোড করুন অথবা URL দিন (সরাসরি লিংক)।")

@router.message(BroadcastState.waiting_for_media_file)
async def step_media_file(msg: Message, state: FSMContext):
    if msg.text and msg.text.startswith("http"):
        await state.update_data(media_url=msg.text, media_file_id="")
        await state.set_state(BroadcastState.waiting_for_count)
        return await msg.answer("🔢 **ধাপ ৪/৫**\nপ্রতি আইডিতে কতবার পাঠাবেন?")
    
    file_id = None
    if msg.photo: file_id = msg.photo[-1].file_id
    elif msg.video: file_id = msg.video.file_id
    elif msg.document: file_id = msg.document.file_id
    if file_id:
        await state.update_data(media_url="", media_file_id=file_id)
        await state.set_state(BroadcastState.waiting_for_count)
        await msg.answer("🔢 **ধাপ ৪/৫**\nপ্রতি আইডিতে কতবার পাঠাবেন?")
    else:
        await msg.answer("⚠️ সঠিক ফাইল বা URL দিন।")

@router.message(BroadcastState.waiting_for_count)
async def step_count(msg: Message, state: FSMContext):
    try:
        count = int(msg.text)
        if count < 1: raise ValueError
    except:
        return await msg.answer("⚠️ ধনাত্মক সংখ্যা দিন।")
    await state.update_data(count=count)
    await state.set_state(BroadcastState.waiting_for_delay)
    await msg.answer("⏱️ **ধাপ ৫/৫**\nবিরতি (সেকেন্ড): যেমন `0.2`")

@router.message(BroadcastState.waiting_for_delay)
async def step_delay(msg: Message, state: FSMContext):
    try:
        delay = float(msg.text)
        if delay < 0: raise ValueError
    except:
        return await msg.answer("⚠️ সঠিক সংখ্যা দিন (যেমন 0.5)")

    data = await state.get_data()
    targets = data["targets"]
    text = data["message_text"]
    media_type = data["media_type"]
    count = data["count"]
    media_url = data.get("media_url", "")
    media_file_id = data.get("media_file_id", "")

    total = len(targets) * count
    await state.clear()

    await msg.answer(f"🚀 **ব্রডকাস্ট শুরু!**\nটার্গেট: {len(targets)}টি\nমোট মেসেজ: {total}\nবিরতি: {delay}সে.\n\n🛑 বন্ধ করতে `/stop` দিন।")

    task = asyncio.create_task(run_broadcast(
        bot=bot, targets=targets, text=text, media_type=media_type,
        media_url=media_url, media_file_id=media_file_id,
        count=count, delay=delay, admin_id=msg.from_user.id
    ))
    running_tasks[msg.from_user.id] = task

async def run_broadcast(bot, targets, text, media_type, media_url, media_file_id, count, delay, admin_id):
    sent = 0
    try:
        for i in range(count):
            for chat_id in targets:
                try:
                    if media_type == "text" or media_type == "skip":
                        await rate_limited_send(bot.send_message, chat_id=chat_id, text=text)
                    elif media_type == "photo":
                        await rate_limited_send(bot.send_photo, chat_id=chat_id, photo=media_url or media_file_id, caption=text)
                    elif media_type == "video":
                        await rate_limited_send(bot.send_video, chat_id=chat_id, video=media_url or media_file_id, caption=text)
                    elif media_type == "document":
                        await rate_limited_send(bot.send_document, chat_id=chat_id, document=media_url or media_file_id, caption=text)
                    sent += 1
                    await asyncio.sleep(delay)
                except Exception as e:
                    print(f"Send failed to {chat_id}: {e}")
        log_action(admin_id, "broadcast_completed", f"Sent {sent}")
        await bot.send_message(admin_id, f"✅ সম্পন্ন! {sent}টি মেসেজ পাঠানো হয়েছে।")
    except asyncio.CancelledError:
        log_action(admin_id, "broadcast_cancelled", f"Sent {sent}")
        await bot.send_message(admin_id, f"⛔ বন্ধ করা হয়েছে। পাঠানো: {sent}")
    finally:
        if admin_id in running_tasks: del running_tasks[admin_id]

@router.message(Command("stop"))
async def stop_cmd(msg: Message):
    if not await ensure_admin(msg): return
    if msg.from_user.id in running_tasks:
        running_tasks[msg.from_user.id].cancel()
        await msg.answer("🛑 ব্রডকাস্ট বন্ধ করার চেষ্টা করা হচ্ছে...")
    else:
        await msg.answer("❌ আপনার কোনো চলমান ব্রডকাস্ট নেই।")

@router.message(Command("add_admin"))
async def add_admin_cmd(msg: Message):
    if not await ensure_admin(msg): return
    args = msg.text.split()
    if len(args) != 2: return await msg.answer("⚠️ `/add_admin <id>`")
    try:
        uid = int(args[1])
    except:
        return await msg.answer("⚠️ সঠিক সংখ্যা দিন।")
    add_admin(uid, msg.from_user.id)
    log_action(msg.from_user.id, "add_admin", f"added {uid}")
    await msg.answer(f"✅ অ্যাডমিন {uid} যোগ করা হয়েছে।")

@router.message(Command("remove_admin"))
async def remove_admin_cmd(msg: Message):
    if not await ensure_admin(msg): return
    args = msg.text.split()
    if len(args) != 2: return await msg.answer("⚠️ `/remove_admin <id>`")
    try:
        uid = int(args[1])
    except:
        return await msg.answer("⚠️ সঠিক সংখ্যা দিন।")
    if uid in ADMIN_IDS: return await msg.answer("⚠️ মুল অ্যাডমিন সরানো যাবে না।")
    remove_admin(uid)
    log_action(msg.from_user.id, "remove_admin", f"removed {uid}")
    await msg.answer(f"✅ অ্যাডমিন {uid} সরানো হয়েছে।")

@router.message(Command("logs"))
async def logs_cmd(msg: Message):
    if not await ensure_admin(msg): return
    logs = get_recent_logs(10)
    txt = "📜 **সর্বশেষ লগ**\n\n" + "\n".join([f"`{l['timestamp']}` → {l['action']}" for l in logs]) or "কোনো লগ নেই।"
    await msg.answer(txt[:4000])

# ================== ৮. মেইন ফাংশন ==================
async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
