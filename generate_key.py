# generate_key.py

from auth.api_key import generate_api_key, hash_api_key
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

raw_key = generate_api_key()
hashed = hash_api_key(raw_key)

supabase.table("api_keys").insert({
    "key_hash": hashed,
    "name": "Demo Key"
}).execute()

print("SAVE THIS KEY (shown once):")
print(raw_key)
