import asyncio
import logging
import hashlib
from pyrogram import enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from forward import get_font

logger = logging.getLogger(__name__)

class DuplicateRemover:
    def __init__(self, client):
        self.client = client
        self.is_running = False

    async def remove_duplicates(self, chat_id, start_id, end_id, status_msg):
        self.is_running = True
        try:
            if isinstance(chat_id, str) and (chat_id.startswith("-100") or chat_id.isdigit()):
                chat_id = int(chat_id)
            
            # Check admin
            try:
                member = await self.client.get_chat_member(chat_id, "me")
                if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                    return await status_msg.edit(f"❌ {get_font('Error')}: {get_font('Bot must be admin to delete messages')}")
            except Exception as e:
                logger.error(f"Admin check failed in duplicate: {e}")
                return await status_msg.edit(f"❌ {get_font('Error')}: {get_font('Could not verify admin status')}")

            await status_msg.edit(f"🔍 {get_font('Scanning for duplicates')}...")
            
            seen_items = set() # Set of hashes for unique identification
            deleted_count = 0
            total_scanned = 0

            for msg_id in range(start_id, end_id + 1):
                if not self.is_running:
                    break
                
                try:
                    message = await self.client.get_messages(chat_id, msg_id)
                    total_scanned += 1
                    
                    if not message or message.empty:
                        continue

                    item_hash = None
                    
                    # 1. Handle Media
                    if message.document:
                        item_hash = f"doc_{message.document.file_name}_{message.document.file_size}"
                    elif message.video:
                        item_hash = f"vid_{message.video.file_name or 'v'}_{message.video.file_size}_{message.video.duration}"
                    elif message.audio:
                        item_hash = f"aud_{message.audio.file_name or 'a'}_{message.audio.file_size}_{message.audio.duration}"
                    elif message.photo:
                        item_hash = f"pho_{message.photo.file_size}_{message.photo.width}_{message.photo.height}"
                    elif message.voice:
                        item_hash = f"voi_{message.voice.file_size}_{message.voice.duration}"
                    elif message.video_note:
                        item_hash = f"vnt_{message.video_note.file_size}_{message.video_note.duration}"
                    elif message.animation:
                        item_hash = f"ani_{message.animation.file_name or 'ani'}_{message.animation.file_size}"
                    
                    # 2. Handle Text (if no media)
                    elif message.text:
                        # Hash the text to identify identical messages
                        text_content = message.text.strip()
                        if len(text_content) > 10: # Only hash meaningful text
                            item_hash = f"txt_{hashlib.md5(text_content.encode()).hexdigest()}"

                    if item_hash:
                        if item_hash in seen_items:
                            try:
                                await message.delete()
                                deleted_count += 1
                            except Exception as e:
                                logger.error(f"Failed to delete duplicate: {e}")
                        else:
                            seen_items.add(item_hash)
                    
                    if total_scanned % 20 == 0:
                        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(get_font("Stop/Cancel"), callback_data="dup_STOP")]])
                        await status_msg.edit(
                            f"🔍 {get_font('Scanning ID')}: {msg_id}\n"
                            f"📊 {get_font('Scanned')}: {total_scanned}\n"
                            f"🗑️ {get_font('Deleted')}: {deleted_count}",
                            reply_markup=keyboard
                        )
                
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception:
                    continue

            if not self.is_running:
                await status_msg.edit(f"🛑 {get_font('Cleanup Cancelled')}!\n\n📊 {get_font('Scanned')}: {total_scanned}\n🗑️ {get_font('Deleted')}: {deleted_count}")
            else:
                await status_msg.edit(f"✅ {get_font('Duplicate Cleanup Completed')}!\n\n📊 {get_font('Total Scanned')}: {total_scanned}\n🗑️ {get_font('Total Deleted')}: {deleted_count}")
        
        except Exception as e:
            logger.error(f"Duplicate removal error: {e}")
            await status_msg.edit(f"❌ {get_font('Error')}: {get_font('An error occurred during cleanup')}\n\n`{str(e)}`")
        finally:
            self.is_running = False

    def stop(self):
        self.is_running = False
