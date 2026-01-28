import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Load .env exactly once (safe even if called multiple times)
load_dotenv()

FERNET_KEY = os.getenv("CREDENTIAL_ENCRYPTION_KEY")

if not FERNET_KEY:
    raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY missing")

try:
    fernet = Fernet(FERNET_KEY.encode())
except Exception as e:
    raise RuntimeError("Invalid Fernet key format") from e


def encrypt_token(token: str) -> str:
    """
    Encrypt a plaintext token and return base64 string
    """
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(token: str) -> str:
    """
    Decrypt an encrypted token back to plaintext
    """
    return fernet.decrypt(token.encode()).decode()
