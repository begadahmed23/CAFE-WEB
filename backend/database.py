from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

# Connect to MongoDB
client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))

# Force the database name to match your screenshot exactly
db = client["Jackelscafe"] 

# Collections
users_collection = db["users"]
reviews_collection = db["reviews"] # This will now show up in the same list!
orders_collection = db["orders"]