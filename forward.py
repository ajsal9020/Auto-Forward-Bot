import asyncio
import time
from pyrogram.errors import FloodWait
from pyrogram.enums import MessageMediaType

class Forwarder:
    def __init__(self, client):
        self.client = client
        self.is_running = False
        self.stats = {
            "total": 0,
            "processed": 0,
            "start_id": 0,
            "end_id": 0,
            "from_chat": "",
            "to_chat": "",
            "start_time": 0,
            "filter": "ALL"
        }

    async def start_forwarding(self, from_chat, to_chat, start_id, end_id, msg_filter, status_msg):
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
                
                if self.stats["processed"] % 10 == 0:
                    await self.update_status(status_msg)
                
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                self.stats["processed"] += 1
                continue

        self.is_running = False
        await status_msg.edit("✅ Forwarding Completed!")

    async def update_status(self, status_msg):
        elapsed = int(time.time() - self.stats["start_time"])
        progress = (self.stats["processed"] / self.stats["total"]) * 100
        
        # Simple ETA calculation
        if self.stats["processed"] > 0:
            eta_sec = (elapsed / self.stats["processed"]) * (self.stats["total"] - self.stats["processed"])
            eta = time.strftime("%Hh %Mm %Ss", time.gmtime(eta_sec))
        else:
            eta = "Calculating..."

        elapsed_str = time.strftime("%Mm %Ss", time.gmtime(elapsed))
        
        text = (
            f"**Copy Message...**\n"
            f"Progress: {progress:.2f}%\n"
            f"Processed: {self.stats['processed']}/{self.stats['total']}\n"
            f"From Chat: {self.stats['from_chat']}\n"
            f"To Chat: {self.stats['to_chat']}\n"
            f"Start ID: {self.stats['start_id']}\n"
            f"End ID: {self.stats['end_id']}\n"
            f"Type: {self.stats['filter']}\n"
            f"ETA: {eta}\n"
            f"Elapsed: {elapsed_str}"
        )
        try:
            await status_msg.edit(text)
        except:
            pass

    def stop(self):
        self.is_running = False
