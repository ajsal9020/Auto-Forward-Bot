import asyncio
import time
from pyrogram import enums
from pyrogram.errors import FloodWait, ChatAdminRequired, UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_font(text):
    # Small caps style font as requested
    fonts = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ',
        'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ',
        's': 's', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
        'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ғ', 'G': 'ɢ', 'H': 'ʜ', 'I': 'ɪ',
        'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'ǫ', 'R': 'ʀ',
        'S': 's', 'T': 'ᴛ', 'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 'Y': 'ʏ', 'Z': 'ᴢ'
    }
    return "".join(fonts.get(c, c) for c in text)

class Forwarder:
    def __init__(self, client):
        self.client = client
        self.is_running = False
        self.stats = {}

    async def check_admin(self, chat_id):
        try:
            if isinstance(chat_id, str) and (chat_id.startswith("-100") or chat_id.isdigit()):
                chat_id = int(chat_id)
            
            # Force refresh chat info to avoid cache issues after restart
            try:
                await self.client.get_chat(chat_id)
            except Exception:
                pass

            member = await self.client.get_chat_member(chat_id, "me")
            return member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
        except Exception as e:
            logger.error(f"Admin check error for {chat_id}: {e}")
            # Fallback: try to send a small action to verify permissions
            try:
                await self.client.send_chat_action(chat_id, enums.ChatAction.TYPING)
                return True
            except Exception:
                return False

    async def start_forwarding(self, from_chat, to_chat, start_id, end_id, msg_filter, status_msg):
        # Check admin permissions every time
        if not await self.check_admin(from_chat):
            return await status_msg.edit(f"❌ {get_font('Error')}: {get_font('Make sure the bot is admin in FROM channel')}")
        if not await self.check_admin(to_chat):
            return await status_msg.edit(f"❌ {get_font('Error')}: {get_font('Make sure the bot is admin in TO channel')}")

        self.is_running = True
        self.stats = {
            "total": end_id - start_id + 1,
            "processed": 0,
            "start_id": start_id,
            "end_id": end_id,
            "from_chat": from_chat,
            "to_chat": to_chat,
            "start_time": time.time(),
            "filter": msg_filter
        }

        for msg_id in range(start_id, end_id + 1):
            if not self.is_running:
                break
            
            try:
                msg = await self.client.get_messages(from_chat, msg_id)
                if not msg or msg.empty:
                    self.stats["processed"] += 1
                    continue

                should_forward = False
                if msg_filter == "ALL":
                    should_forward = True
                elif msg_filter == "TEXT" and msg.text:
                    should_forward = True
                elif msg_filter == "PHOTO" and msg.photo:
                    should_forward = True
                elif msg_filter == "VIDEO" and msg.video:
                    should_forward = True
                elif msg_filter == "AUDIO" and msg.audio:
                    should_forward = True
                elif msg_filter == "DOCUMENT" and msg.document:
                    should_forward = True

                if should_forward:
                    await msg.copy(to_chat)
                
                self.stats["processed"] += 1
                
                if self.stats["processed"] % 5 == 0 or self.stats["processed"] == self.stats["total"]:
                    await self.update_status(status_msg)
                
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except ChatAdminRequired:
                self.is_running = False
                return await status_msg.edit(f"❌ {get_font('Error')}: {get_font('Admin permissions lost during process')}")
            except Exception:
                self.stats["processed"] += 1
                continue

        if self.is_running:
            self.is_running = False
            await status_msg.edit(f"✅ {get_font('Forwarding Completed')}!")
        else:
            await status_msg.edit(f"🛑 {get_font('Forwarding Cancelled')}!")

    async def update_status(self, status_msg):
        elapsed = int(time.time() - self.stats["start_time"])
        progress = (self.stats["processed"] / self.stats["total"]) * 100
        
        if self.stats["processed"] > 0:
            eta_sec = (elapsed / self.stats["processed"]) * (self.stats["total"] - self.stats["processed"])
            eta = time.strftime("%Hh %Mm %Ss", time.gmtime(eta_sec))
        else:
            eta = "Calculating..."

        elapsed_str = time.strftime("%Mm %Ss", time.gmtime(elapsed))
        
        text = (
            f"**{get_font('Copy Message')}...**\n"
            f"**{get_font('Progress')}**: {progress:.2f}%\n"
            f"**{get_font('Processed')}**: {self.stats['processed']}/{self.stats['total']}\n"
            f"**{get_font('From Chat')}**: `{self.stats['from_chat']}`\n"
            f"**{get_font('To Chat')}**: `{self.stats['to_chat']}`\n"
            f"**{get_font('Start ID')}**: {self.stats['start_id']}\n"
            f"**{get_font('End ID')}**: {self.stats['end_id']}\n"
            f"**{get_font('Type')}**: {self.stats['filter']}\n"
            f"**{get_font('ETA')}**: {eta}\n"
            f"**{get_font('Elapsed')}**: {elapsed_str}"
        )
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(get_font("Stop/Cancel"), callback_data="fwd_STOP")]])
        
        try:
            await status_msg.edit(text, reply_markup=keyboard)
        except:
            pass

    def stop(self):
        self.is_running = False
