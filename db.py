from motor import motor_asyncio
from dotenv import dotenv_values
from config import DATABASE

MONGO_URI = dotenv_values()["MONGO_URI"]
_client = motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = _client[DATABASE]


async def use_counter(counter_id: str) -> int:
    counter = await db.counters.find_one_and_update({"_id": counter_id}, {"$inc": {"value": 1}})
    return counter["value"]
