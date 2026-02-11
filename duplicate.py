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

            await status_msg.edit(f"🔍 {get_font('Scanning for duplicates and unsupported media')}...")
            
            seen_items = set() # Set of hashes for unique identification
            deleted_count = 0
            unsupported_count = 0
            total_scanned = 0

            # Supported media types for movie bots are usually Video and Document
            SUPPORTED_MEDIA = [enums.MessageMediaType.VIDEO, enums.MessageMediaType.DOCUMENT]

            for msg_id in range(start_id, end_id + 1):
                if not self.is_running:
                    break
                
                try:
                    message = await self.client.get_messages(chat_id, msg_id)
                    total_scanned += 1
                    
                    if not message or message.empty:
                        continue

                    should_delete = False
                    item_hash = None
                    
                    # 1. Check for Unsupported Media (Stickers, Audio, Voice, etc.)
                    if message.media and message.media not in SUPPORTED_MEDIA:
                        should_delete = True
                        unsupported_count += 1
                    
                    # 2. Handle Supported Media and Text for Duplicate Detection
                    else:
                        if message.document:
                            # Advanced hash: name + size
                            item_hash = f"doc_{message.document.file_name}_{message.document.file_size}"
                        elif message.video:
                            # Advanced hash: name + size + duration
                            item_hash = f"vid_{message.video.file_name or 'v'}_{message.video.file_size}_{message.video.duration}"
                        elif message.photo:
                            # Advanced hash: size + dimensions
                            item_hash = f"pho_{message.photo.file_size}_{message.photo.width}_{message.photo.height}"
                        elif message.text:
                            # Hash the text content
                            text_content = message.text.strip()
                            if text_content:
                                item_hash = f"txt_{hashlib.md5(text_content.encode()).hexdigest()}"

                        if item_hash:
                            if item_hash in seen_items:
                                should_delete = True
                            else:
                                seen_items.add(item_hash)

                    if should_delete:
                        try:
                            await message.delete()
                            deleted_count += 1
                        except Exception as e:
                            logger.error(f"Failed to delete: {e}")
                    
                    if total_scanned % 20 == 0:
                        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(get_font("Stop/Cancel"), callback_data="dup_STOP")]])
                        await status_msg.edit(
                            f"🔍 {get_font('Scanning ID')}: {msg_id}\n"
                            f"📊 {get_font('Scanned')}: {total_scanned}\n"
                            f"🗑️ {get_font('Deleted')}: {deleted_count}\n"
                            f"🚫 {get_font('Unsupported')}: {unsupported_count}",
                            reply_markup=keyboard
                        )
                
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception:
                    continue

            if not self.is_running:
                await status_msg.edit(f"🛑 {get_font('Cleanup Cancelled')}!\n\n📊 {get_font('Scanned')}: {total_scanned}\n🗑️ {get_font('Total Deleted')}: {deleted_count}")
            else:
                await status_msg.edit(f"✅ {get_font('Duplicate Cleanup Completed')}!\n\n📊 {get_font('Total Scanned')}: {total_scanned}\n🗑️ {get_font('Total Deleted')}: {deleted_count}")
        
        except Exception as e:
            logger.error(f"Duplicate removal error: {e}")
            await status_msg.edit(f"❌ {get_font('Error')}: {get_font('An error occurred during cleanup')}\n\n`{str(e)}`")
        finally:
            self.is_running = False

    def stop(self):
        self.is_running = False
