import base64
import getpass
import os
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet

def get_key_secret_from_password() -> tuple[str, str]:
    print("--- API Key loading ---")
    
    # Get password to decrypt the file
    password = getpass.getpass("Enter your encryption password: ")
    
    try:
        # Generate decryption key
        key = generate_key_from_password(password)
        f = Fernet(key)

        # Load and decrypt the file
        if not os.path.exists("credentials.enc"):
            print("Error: credentials.enc file not found.")
            return None, None

        with open("credentials.enc", "rb") as file:
            encrypted_data = file.read()
        
        decrypted_data = f.decrypt(encrypted_data).decode()
        stored_key, stored_secret = decrypted_data.split(',')

    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None, None

    return stored_key.strip(), stored_secret.strip()

def generate_key_from_password(password: str):
    # This must match the salt used in generate_key.py
    salt = b'Steven is human.' 
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key
