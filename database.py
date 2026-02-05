import os
from motor.motor_asyncio import AsyncIOMotorClient

class Database:
    def __init__(self):
        self.client = None
        self.db = None
        self.users = None
        self.config = None

    async def connect(self):
        mongo_url = os.environ.get("MONGO_URL")
        if not mongo_url:
            return False
        self.client = AsyncIOMotorClient(mongo_url)
        self.db = self.client["forwarder_bot"]
        self.users = self.db["users"]
        self.config = self.db["config"]
        return True

    async def add_user(self, user_id, name):
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name}},
            upsert=True
        )

    async def get_all_users(self):
        cursor = self.users.find({})
        return await cursor.to_list(length=1000)

    async def set_config(self, key, value):
        await self.config.update_one(
            {"key": key},
            {"$set": {"value": value}},
            upsert=True
        )

    async def get_config(self, key):
        res = await self.config.find_one({"key": key})
        return res["value"] if res else None

db = Database()
