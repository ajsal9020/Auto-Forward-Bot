import os
import asyncio
import psutil
import time
import logging
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from forward import Forwarder
from aiohttp import web
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from config.env if it exists
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
start_time = time.time()

# Web Server for Render
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    server = web.Application()
    server.router.add_get('/', handle)
    runner = web.AppRunner(server)
    await runner.setup()
    # Render uses PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Web server started on port {port}")

async def pinger():
    import requests
    while True:
        await asyncio.sleep(300) # Ping every 5 minutes instead of 30s to be polite
        if RENDER_URL:
            try:
                requests.get(RENDER_URL, timeout=10)
                logger.info("Pinged Render URL successfully")
            except Exception as e:
                logger.error(f"Pinger error: {e}")

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    db.add_user(message.from_user.id, message.from_user.first_name)
    await message.reply("Welcome! Use /forward to start forwarding or /stats to see system status.")

@app.on_message(filters.command("fsub") & filters.user(ADMINS))
async def fsub_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: /fsub id1 id2 ...")
    channels = message.command[1:]
    db.set_config("fsub_channels", ",".join(channels))
    await message.reply(f"FSub channels set to: {', '.join(channels)}")

@app.on_message(filters.command("users") & filters.user(ADMINS))
async def users_cmd(client, message):
    users = db.get_all_users()
    if not users:
        return await message.reply("No users found in database.")
    
    text = "**Bot Users:**\n"
    for uid, name in users:
        text += f"- [{name}](tg://user?id={uid}) (`{uid}`)\n"
    await message.reply(text)

@app.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_cmd(client, message):
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    uptime_sec = int(time.time() - start_time)
    uptime = time.strftime("%Hh %Mm %Ss", time.gmtime(uptime_sec))
    await message.reply(f"**System Stats:**\nCPU: {cpu}%\nRAM: {ram}%\nDisk: {disk}%\nUptime: {uptime}")

@app.on_message(filters.command("forward") & filters.user(ADMINS))
async def forward_init(client, message):
    if len(message.command) < 5:
        return await message.reply("Usage: /forward from_chat_id to_chat_id start_id end_id")
    
    from_chat = message.command[1]
    to_chat = message.command[2]
    try:
        start_id = int(message.command[3])
        end_id = int(message.command[4])
    except ValueError:
        return await message.reply("Start ID and End ID must be integers.")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("All ✅", callback_data=f"fwd_ALL_{from_chat}_{to_chat}_{start_id}_{end_id}"),
         InlineKeyboardButton("Text", callback_data=f"fwd_TEXT_{from_chat}_{to_chat}_{start_id}_{end_id}")],
        [InlineKeyboardButton("Photo", callback_data=f"fwd_PHOTO_{from_chat}_{to_chat}_{start_id}_{end_id}"),
         InlineKeyboardButton("Video", callback_data=f"fwd_VIDEO_{from_chat}_{to_chat}_{start_id}_{end_id}")],
        [InlineKeyboardButton("Audio", callback_data=f"fwd_AUDIO_{from_chat}_{to_chat}_{start_id}_{end_id}"),
         InlineKeyboardButton("Document", callback_data=f"fwd_DOCUMENT_{from_chat}_{to_chat}_{start_id}_{end_id}")],
        [InlineKeyboardButton("Stop/Cancel", callback_data="fwd_STOP")]
    ])
    
    await message.reply("Select message type to forward:", reply_markup=keyboard)

@app.on_callback_query(filters.regex("^fwd_"))
async def callback_handler(client, query):
    data = query.data.split("_")
    if data[1] == "STOP":
        forwarder.stop()
        return await query.answer("Stopping process...")
    
    msg_filter = data[1]
    from_chat = data[2]
    to_chat = data[3]
    start_id = int(data[4])
    end_id = int(data[5])
    
    await query.message.edit(f"Starting {msg_filter} forwarding...")
    asyncio.create_task(forwarder.start_forwarding(from_chat, to_chat, start_id, end_id, msg_filter, query.message))

async def main():
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
