import asyncio
import logging
from pyrogram import enums, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from forward import get_font

logger = logging.getLogger(__name__)

class Uniquifier:
    def __init__(self, client):
        self.client = client
        self.purge_status = {}
        self.chat_configs = {} # user_id: chat_id
        self.delays = {} # user_id: delay_seconds
        self.FILE_TYPES = ["photo", "animation", "document", "video", "audio"]

    async def set_chat(self, user_id, chat_id_str, message):
        try:
            if isinstance(chat_id_str, str) and (chat_id_str.startswith("-100") or chat_id_str.isdigit()):
                chat_id = int(chat_id_str)
            else:
                return await message.reply(f"❌ {get_font('Invalid Chat ID format')}")

            member = await self.client.get_chat_member(chat_id, "me")
            if member.status not in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                return await message.reply(f"❌ {get_font('Bot must be admin with delete permissions')}")
            
            if not member.privileges.can_delete_messages:
                return await message.reply(f"❌ {get_font('Bot does not have delete messages permission')}")

            self.chat_configs[user_id] = chat_id
            await message.reply(f"✅ {get_font('Chat')} `{chat_id}` {get_font('saved')}!\n{get_font('You can now use')} `/uniquify start_id end_id`")
        except Exception as e:
            logger.error(f"Set chat error: {e}")
            await message.reply(f"❌ {get_font('Error')}: {get_font('Make sure the bot is in the chat and is admin')}")

    async def set_delay(self, user_id, delay_str, message):
        if not delay_str.isdigit():
            return await message.reply(f"❌ {get_font('Delay must be a number')}")
        
        delay = int(delay_str)
        self.delays[user_id] = delay
        await message.reply(f"✅ {get_font('Delay set to')} {delay} {get_font('seconds')}")

    async def start_purge(self, user_id, start_id, end_id, message):
        if user_id not in self.chat_configs:
            return await message.reply(f"❌ {get_font('Configure the target chat first using')} `/chat chat_id`")

        chat_id = self.chat_configs[user_id]
        delay = self.delays.get(user_id, 0)
        self.purge_status[user_id] = True
        
        msg1 = await message.reply(f"⏳ {get_font('Processing... This will take some time')}")
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(get_font("Cancel"), callback_data="uni_CANCEL")]])
        msg2 = await message.reply(f"🔍 {get_font('Looking for Duplicates')}...", reply_markup=keyboard)

        id_index = []
        duplicates = 0
        total_scanned = 0

        try:
            # Use ID-range scanning instead of get_chat_history for bot compatibility
            for msg_id in range(start_id, end_id + 1):
                if user_id not in self.purge_status:
                    await msg1.delete()
                    await msg2.edit(f"🛑 {get_font('Purging Cancelled by user')}")
                    return

                try:
                    msg = await self.client.get_messages(chat_id, msg_id)
                    total_scanned += 1
                    
                    if msg and not msg.empty:
                        for file_type in self.FILE_TYPES:
                            media = getattr(msg, file_type, None)
                            if media is not None:
                                uid = str(media.file_unique_id)
                                if uid in id_index:
                                    try:
                                        await msg.delete()
                                        duplicates += 1
                                        if duplicates % 5 == 0:
                                            await msg1.edit(f"**{get_font('Messages deleted')}**: {duplicates}\n**{get_font('Current ID')}**: {msg.id}")
                                    except FloodWait as e:
                                        await asyncio.sleep(e.value)
                                    except Exception:
                                        pass
                                    await asyncio.sleep(delay)
                                else:
                                    id_index.append(uid)
                    
                    if total_scanned % 50 == 0:
                        await msg2.edit(f"🔍 {get_font('Scanning ID')}: {msg_id}\n📊 {get_font('Scanned')}: {total_scanned}\n🗑️ {get_font('Duplicates Found')}: {duplicates}", reply_markup=keyboard)

                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception:
                    continue

            if duplicates == 0:
                await msg1.delete()
                await msg2.edit(f"✅ {get_font('No duplicates found in the range')} {start_id}-{end_id}")
            else:
                await msg2.edit(f"✅ {get_font('Success! All duplicate media were deleted')}\n**{get_font('Total Scanned')}**: {total_scanned}\n**{get_font('Total Deleted')}**: {duplicates}")
        
        except Exception as e:
            logger.error(f"Purge error: {e}")
            await msg2.edit(f"❌ {get_font('Error')}: {str(e)}")
        finally:
            self.purge_status.pop(user_id, None)

    def cancel(self, user_id):
        self.purge_status.pop(user_id, None)
