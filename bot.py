import os
import asyncio
import psutil
import time
import logging
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from forward import Forwarder, get_font
from duplicate import DuplicateRemover
from aiohttp import web
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if os.path.exists("config.env"):
    load_dotenv("config.env")

# Config
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMINS = [int(x) for x in os.environ.get("ADMINS", "").split() if x]
RENDER_URL = os.environ.get("RENDER_URL", "")

app = Client("forwarder_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
forwarder = Forwarder(app)
duplicate_remover = DuplicateRemover(app)
start_time = time.time()

async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    server = web.Application()
    server.router.add_get('/', handle)
    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Web server started on port {port}")

async def pinger():
    import requests
    import random
    while True:
        # Jitter mode: Sleep for a random interval between 5 and 13 minutes (300 to 780 seconds)
        # This stays below Render's 15-minute inactivity limit while appearing less robotic.
        sleep_time = random.randint(300, 780)
        await asyncio.sleep(sleep_time)
        if RENDER_URL:
            try:
                requests.get(RENDER_URL, timeout=10)
                logger.info(f"Jitter Pinger: Sent request after {sleep_time}s sleep")
            except Exception as e:
                logger.error(f"Pinger error: {e}")

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await db.add_user(message.from_user.id, message.from_user.first_name)
    await message.reply(f"**{get_font('Welcome')}!**\n{get_font('Use')} /forward {get_font('to start forwarding or')} /stats {get_font('to see system status')}.")

@app.on_message(filters.command("fsub") & filters.user(ADMINS))
async def fsub_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply(f"{get_font('Usage')}: /fsub id1 id2 ...")
    channels = message.command[1:]
    await db.set_config("fsub_channels", ",".join(channels))
    await message.reply(f"**{get_font('FSub channels set to')}**: {', '.join(channels)}")

@app.on_message(filters.command("users") & filters.user(ADMINS))
async def users_cmd(client, message):
    users = await db.get_all_users()
    if not users:
        return await message.reply(get_font("No users found in database"))
    
    text = f"**{get_font('Bot Users')}:**\n"
    for user in users:
        uid = user["user_id"]
        name = user["name"]
        text += f"- [{name}](tg://user?id={uid}) (`{uid}`)\n"
    await message.reply(text)

@app.on_message(filters.command("duplicate") & filters.user(ADMINS))
async def duplicate_cmd(client, message):
    if len(message.command) < 4:
        return await message.reply(f"{get_font('Usage')}: /duplicate Channel_ID Start_ID End_ID")
    
    chat_id = message.command[1]
    try:
        start_id = int(message.command[2])
        end_id = int(message.command[3])
    except ValueError:
        return await message.reply(get_font("Start ID and End ID must be integers"))
        
    status_msg = await message.reply(f"⏳ {get_font('Initializing cleanup')}...")
    asyncio.create_task(duplicate_remover.remove_duplicates(chat_id, start_id, end_id, status_msg))

@app.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_cmd(client, message):
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    uptime_sec = int(time.time() - start_time)
    uptime = time.strftime("%Hh %Mm %Ss", time.gmtime(uptime_sec))
    await message.reply(f"**{get_font('System Stats')}:**\n{get_font('CPU')}: {cpu}%\n{get_font('RAM')}: {ram}%\n{get_font('Disk')}: {disk}%\n{get_font('Uptime')}: {uptime}")

@app.on_message(filters.command("forward") & filters.user(ADMINS))
async def forward_init(client, message):
    if len(message.command) < 5:
        return await message.reply(f"{get_font('Usage')}: /forward from_chat_id to_chat_id start_id end_id")
    
    from_chat = message.command[1]
    to_chat = message.command[2]
    
    # Ensure IDs are integers if they look like Telegram IDs
    if from_chat.startswith("-100") or from_chat.isdigit():
        from_chat = int(from_chat)
    if to_chat.startswith("-100") or to_chat.isdigit():
        to_chat = int(to_chat)

    try:
        start_id = int(message.command[3])
        end_id = int(message.command[4])
    except ValueError:
        return await message.reply(get_font("Start ID and End ID must be integers"))
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{get_font('All')} ✅", callback_data=f"fwd_ALL_{from_chat}_{to_chat}_{start_id}_{end_id}"),
         InlineKeyboardButton(get_font("Text"), callback_data=f"fwd_TEXT_{from_chat}_{to_chat}_{start_id}_{end_id}")],
        [InlineKeyboardButton(get_font("Photo"), callback_data=f"fwd_PHOTO_{from_chat}_{to_chat}_{start_id}_{end_id}"),
         InlineKeyboardButton(get_font("Video"), callback_data=f"fwd_VIDEO_{from_chat}_{to_chat}_{start_id}_{end_id}")],
        [InlineKeyboardButton(get_font("Audio"), callback_data=f"fwd_AUDIO_{from_chat}_{to_chat}_{start_id}_{end_id}"),
         InlineKeyboardButton(get_font("Document"), callback_data=f"fwd_DOCUMENT_{from_chat}_{to_chat}_{start_id}_{end_id}")],
        [InlineKeyboardButton(get_font("Cancel"), callback_data="fwd_CANCEL")]
    ])
    
    await message.reply(get_font("Select message type to forward"), reply_markup=keyboard)

@app.on_callback_query(filters.regex("^fwd_"))
async def callback_handler(client, query):
    data = query.data.split("_")
    if data[1] == "STOP":
        forwarder.stop()
        return await query.answer(get_font("Stopping process"))
    
    if data[1] == "CANCEL":
        await query.message.delete()
        return await query.answer(get_font("Cancelled"))
    
    msg_filter = data[1]
    from_chat = data[2]
    to_chat = data[3]
    start_id = int(data[4])
    end_id = int(data[5])
    
    await query.message.edit(f"{get_font('Starting')} {msg_filter} {get_font('forwarding')}...")
    asyncio.create_task(forwarder.start_forwarding(from_chat, to_chat, start_id, end_id, msg_filter, query.message))

async def main():
    if not await db.connect():
        logger.error("MONGO_URL not found in environment!")
        return
    
    if not API_ID or not API_HASH or not BOT_TOKEN:
        logger.error("API_ID, API_HASH, or BOT_TOKEN not found in environment!")
        return

    await app.start()
    logger.info("Bot started!")
    
    await start_web_server()
    asyncio.create_task(pinger())
    
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
