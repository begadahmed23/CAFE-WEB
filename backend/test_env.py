from dotenv import load_dotenv
import os

load_dotenv()

print("MONGO_URI =", os.getenv("MONGO_URI"))
print("DB_NAME =", os.getenv("DB_NAME"))
