import asyncio
import logging
from pyrogram import enums
from forward import get_font

logger = logging.getLogger(__name__)

class DuplicateRemover:
    def __init__(self, client):
        self.client = client
        self.is_running = False

    async def remove_duplicates(self, chat_id, status_msg):
        self.is_running = True
        try:
            if isinstance(chat_id, str) and (chat_id.startswith("-100") or chat_id.isdigit()):
                chat_id = int(chat_id)
            
            # Check admin
            member = await self.client.get_chat_member(chat_id, "me")
            if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                return await status_msg.edit(f"❌ {get_font('Error')}: {get_font('Bot must be admin to delete messages')}")

            await status_msg.edit(f"🔍 {get_font('Scanning for duplicates')}...")
            
            seen_files = {} # {(file_name, file_size): first_msg_id}
            deleted_count = 0
            total_scanned = 0

            # Bots cannot use get_chat_history in channels easily, 
            # but they CAN use search_messages with no query to get all messages.
            async for message in self.client.search_messages(chat_id):
                if not self.is_running:
                    break
                
                total_scanned += 1
                file_info = None
                
                if message.document:
                    file_info = (message.document.file_name, message.document.file_size)
                elif message.video:
                    file_info = (message.video.file_name or "video", message.video.file_size)
                elif message.audio:
                    file_info = (message.audio.file_name or "audio", message.audio.file_size)
                elif message.photo:
                    file_info = ("photo", message.photo.file_size)

                if file_info:
                    if file_info in seen_files:
                        try:
                            await message.delete()
                            deleted_count += 1
                        except Exception as e:
                            logger.error(f"Failed to delete duplicate: {e}")
                    else:
                        seen_files[file_info] = message.id
                
                if total_scanned % 50 == 0:
                    try:
                        await status_msg.edit(f"🔍 {get_font('Scanning')}: {total_scanned}\n🗑️ {get_font('Deleted')}: {deleted_count}")
                    except:
                        pass

            await status_msg.edit(f"✅ {get_font('Duplicate Cleanup Completed')}!\n\n📊 {get_font('Total Scanned')}: {total_scanned}\n🗑️ {get_font('Total Deleted')}: {deleted_count}")
        
        except Exception as e:
            logger.error(f"Duplicate removal error: {e}")
            await status_msg.edit(f"❌ {get_font('Error')}: {get_font('Telegram restricted this action or an error occurred')}\n\n`{str(e)}`")
        finally:
            self.is_running = False

    def stop(self):
        self.is_running = False
