from key import generate_key_from_password
from cryptography.fernet import Fernet
import base64
import getpass  # Used to mask all inputs (hidden from terminal)

print("--- API Key Security Setup (Input will be hidden) ---")

# 1. Process all inputs using getpass
# Characters will not appear on screen while typing. Press Enter when finished.
user_password = getpass.getpass("1. Set a password for file encryption: ")
target_app_key = getpass.getpass("2. Enter your APP KEY: ")
target_app_secret = getpass.getpass("3. Enter your APP SECRET: ")
target_hts_id = getpass.getpass("4. Enter your HTS ID: ")

# 2. Generate encryption key
key = generate_key_from_password(user_password)
f = Fernet(key)

# 3. Combine and encrypt data
data = f"{target_app_key},{target_app_secret},{target_hts_id}".encode()
encrypted_data = f.encrypt(data)

# 4. Save to file
with open("credentials.enc", "wb") as file:
    file.write(encrypted_data)

print("\n" + "="*60)
print("[SUCCESS] 'credentials.enc' has been created.")
print("No sensitive information remains in the source code or terminal.")
print("="*60)