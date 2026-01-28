from dotenv import load_dotenv
import os

# 1️⃣ Load .env
load_dotenv()

# 2️⃣ Verify env variable
key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
print("FERNET KEY FOUND:", bool(key))

# 3️⃣ Import AFTER env is loaded
from utils.crypto import encrypt_token, decrypt_token

# 4️⃣ Test encryption / decryption
plaintext = "hello"

encrypted = encrypt_token(plaintext)
decrypted = decrypt_token(encrypted)

print("Encrypted:", encrypted)
print("Decrypted:", decrypted)

# 5️⃣ Final assertion
assert decrypted == plaintext
print("✅ Fernet encryption working correctly")
