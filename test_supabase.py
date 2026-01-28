from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

print("URL:", url)
print("KEY EXISTS:", bool(key))

client = create_client(url, key)
print("Supabase connected ✅")
