from motor import motor_asyncio
from dotenv import dotenv_values
from config import DATABASE

MONGO_URI = dotenv_values()["MONGO_URI"]
_client = motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = _client[DATABASE]
