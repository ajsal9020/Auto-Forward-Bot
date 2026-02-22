import os
import time
import psutil
import asyncio
import logging
import requests
import random
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from forward import Forwarder, get_font
from uniquify import Uniquifier
from aiohttp import web
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv("config.env")

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMINS = [int(x) for x in os.environ.get("ADMINS", "").split()]
RENDER_URL = os.environ.get("RENDER_URL", "")

app = Client("forwarder_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
forwarder = Forwarder(app)
uniquifier = Uniquifier(app)
start_time = time.time()

async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    server = web.Application()
    server.add_routes([web.get('/', handle)])
    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Web server started on port {port}")

async def auto_pinger():
    if not RENDER_URL:
        logger.warning("RENDER_URL not set, auto-pinger disabled.")
        return
    
    while True:
        # Jitter mode: random interval between 5 and 13 minutes (300-780 seconds)
        sleep_time = random.randint(300, 780)
        logger.info(f"Pinger sleeping for {sleep_time} seconds...")
        await asyncio.sleep(sleep_time)
        try:
            requests.get(RENDER_URL)
            logger.info(f"Pinged {RENDER_URL} successfully.")
        except Exception as e:
            logger.error(f"Ping failed: {e}")

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    await db.add_user(message.from_user.id, message.from_user.first_name)
    
    text = (
        f"👋 {get_font('Welcome')} **{message.from_user.first_name}**!\n\n"
        f"🚀 {get_font('I am a powerful Auto Forward Bot with advanced Uniquify features')}.\n\n"
        f"📂 {get_font('Use the buttons below to learn more about my capabilities')}.\n"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"ℹ️ {get_font('About')}", callback_data="bot_ABOUT"),
            InlineKeyboardButton(f"❓ {get_font('Help')}", callback_data="bot_HELP")
        ],
        [
            InlineKeyboardButton(f"📊 {get_font('Stats')}", callback_data="bot_STATS"),
            InlineKeyboardButton(f"👥 {get_font('Users')}", callback_data="bot_USERS")
        ]
    ])
    
    await message.reply(text, reply_markup=keyboard)

@app.on_message(filters.command("help") & filters.private)
async def help_cmd(client, message):
    help_text = (
        f"📖 **{get_font('Help Menu')}**\n\n"
        f"📤 **{get_font('Forwarding')}**:\n"
        f"• `/forward from_id to_id start_id end_id`\n"
        f"• {get_font('Works with public channels without admin status')}.\n\n"
        f"🧹 **{get_font('Uniquify')}**:\n"
        f"• `/chat chat_id` - {get_font('Set target chat')}\n"
        f"• `/delay seconds` - {get_font('Set deletion delay')}\n"
        f"• `/uniquify start_id end_id` - {get_font('Remove duplicates')}\n\n"
        f"⚙️ **{get_font('Other')}**:\n"
        f"• `/fsub id1 id2` - {get_font('Set force sub channels')}\n"
        f"• `/stats` - {get_font('Check system status')}\n"
        f"• `/users` - {get_font('View bot users')}"
    )
    await message.reply(help_text)

@app.on_message(filters.command("about") & filters.private)
async def about_cmd(client, message):
    about_text = (
        f"🤖 **{get_font('About This Bot')}**\n\n"
        f"✨ **{get_font('Name')}**: {get_font('Auto Forward Bot')}\n"
        f"🛠️ **{get_font('Framework')}**: Pyrogram\n"
        f"🗄️ **{get_font('Database')}**: MongoDB\n"
        f"🌐 **{get_font('Host')}**: Render\n\n"
        f"💎 **{get_font('Features')}**:\n"
        f"• {get_font('High-speed forwarding')}\n"
        f"• {get_font('Advanced duplicate removal')}\n"
        f"• {get_font('Public channel support')}\n"
        f"• {get_font('Low resource consumption')}"
    )
    await message.reply(about_text)

@app.on_message(filters.command("fsub") & filters.user(ADMINS))
async def fsub_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply(f"{get_font('Usage')}: /fsub id1 id2 ...")
    channels = message.command[1:]
    await db.set_config("fsub_channels", channels)
    await message.reply(f"✅ {get_font('Force sub channels updated')}!")

@app.on_message(filters.command("users") & filters.user(ADMINS))
async def users_cmd(client, message):
    users = await db.get_all_users()
    text = f"👥 **{get_font('Total Users')}**: {len(users)}\n\n"
    for user in users:
        uid = user["user_id"]
        name = user["name"]
        text += f"• [{name}](tg://user?id={uid}) (`{uid}`)\n"
    await message.reply(text)

@app.on_message(filters.command("chat") & filters.user(ADMINS))
async def chat_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply(f"{get_font('Usage')}: /chat chat_id")
    await uniquifier.set_chat(message.from_user.id, message.command[1], message)

@app.on_message(filters.command("delay") & filters.user(ADMINS))
async def delay_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply(f"{get_font('Usage')}: /delay seconds")
    await uniquifier.set_delay(message.from_user.id, message.command[1], message)

@app.on_message(filters.command(["uniquify", "purge"]) & filters.user(ADMINS))
async def uniquify_cmd(client, message):
    if len(message.command) < 3:
        return await message.reply(f"{get_font('Usage')}: /uniquify start_id end_id")
    
    try:
        start_id = int(message.command[1])
        end_id = int(message.command[2])
    except ValueError:
        return await message.reply(get_font("Start ID and End ID must be integers"))
        
    await uniquifier.start_purge(message.from_user.id, start_id, end_id, message)

@app.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_cmd(client, message):
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    uptime = time.strftime("%Hh %Mm %Ss", time.gmtime(time.time() - start_time))
    
    text = (
        f"📊 **{get_font('System Stats')}**\n\n"
        f"🖥️ **{get_font('CPU')}**: {cpu}%\n"
        f"💾 **{get_font('RAM')}**: {ram}%\n"
        f"💿 **{get_font('Disk')}**: {disk}%\n"
        f"⏰ **{get_font('Uptime')}**: {uptime}"
    )
    await message.reply(text)

@app.on_message(filters.command("forward") & filters.user(ADMINS))
async def forward_cmd(client, message):
    if len(message.command) < 5:
        return await message.reply(f"{get_font('Usage')}: /forward from_id to_id start_id end_id")
    
    from_chat = message.command[1]
    to_chat = message.command[2]
    try:
        start_id = int(message.command[3])
        end_id = int(message.command[4])
    except ValueError:
        return await message.reply(get_font("Start ID and End ID must be integers"))

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✅ {get_font('All')}", callback_data=f"fwd_ALL_{from_chat}_{to_chat}_{start_id}_{end_id}"),
            InlineKeyboardButton(get_font("Text"), callback_data=f"fwd_TEXT_{from_chat}_{to_chat}_{start_id}_{end_id}"),
            InlineKeyboardButton(get_font("Photo"), callback_data=f"fwd_PHOTO_{from_chat}_{to_chat}_{start_id}_{end_id}")
        ],
        [
            InlineKeyboardButton(get_font("Video"), callback_data=f"fwd_VIDEO_{from_chat}_{to_chat}_{start_id}_{end_id}"),
            InlineKeyboardButton(get_font("Audio"), callback_data=f"fwd_AUDIO_{from_chat}_{to_chat}_{start_id}_{end_id}"),
            InlineKeyboardButton(get_font("Document"), callback_data=f"fwd_DOCUMENT_{from_chat}_{to_chat}_{start_id}_{end_id}")
        ],
        [
            InlineKeyboardButton(f"❌ {get_font('Cancel')}", callback_data="fwd_CANCEL")
        ]
    ])
    
    await message.reply(get_font("Select message type to forward"), reply_markup=keyboard)

@app.on_callback_query(filters.regex("^(fwd_|uni_|bot_)"))
async def callback_handler(client, query):
    data = query.data.split("_")
    
    if data[0] == "bot":
        if data[1] == "ABOUT":
            await about_cmd(client, query.message)
        elif data[1] == "HELP":
            await help_cmd(client, query.message)
        elif data[1] == "STATS":
            await stats_cmd(client, query.message)
        elif data[1] == "USERS":
            await users_cmd(client, query.message)
        return await query.answer()

    if data[0] == "uni":
        if data[1] == "CANCEL":
            uniquifier.cancel(query.from_user.id)
            return await query.answer(get_font("Cancelling..."))
        return

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
    
    status_msg = await query.message.edit(f"⏳ {get_font('Initializing forwarding')}...")
    asyncio.create_task(forwarder.start_forwarding(from_chat, to_chat, start_id, end_id, msg_filter, status_msg))

async def main():
    await app.start()
    await start_web_server()
    asyncio.create_task(auto_pinger())
    logger.info("Bot started!")
    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(main())
