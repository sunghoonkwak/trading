from key.key import generate_key_from_password
import getpass
import base64
from cryptography.fernet import Fernet

def validate_credentials():
    print("--- API Key Validation ---")
    
    # 1. Get password to decrypt the file
    password = getpass.getpass("Enter your encryption password: ")
    
    try:
        # Generate decryption key
        key = generate_key_from_password(password)
        f = Fernet(key)

        # 2. Load and decrypt the file
        with open("credentials.enc", "rb") as file:
            encrypted_data = file.read()
        
        decrypted_data = f.decrypt(encrypted_data).decode()
        stored_key, stored_secret = decrypted_data.split(',')
        
        print("\n[INFO] File decrypted successfully. Now enter the keys to compare.")
        
        # 3. Get actual keys from user to verify
        input_key = getpass.getpass("Enter the APP KEY to verify: ")
        input_secret = getpass.getpass("Enter the APP SECRET to verify: ")

        # 4. Comparison logic
        if input_key == stored_key and input_secret == stored_secret:
            print("\n" + "="*50)
            print("[PASS] Validation Successful!")
            print("The keys match the encrypted file perfectly.")
            print("="*50)
        else:
            print("\n" + "!"*50)
            print("[FAIL] Validation Failed.")
            print("The entered keys do not match the stored information.")
            print("!"*50)

    except Exception as e:
        print("\n[ERROR] Failed to decrypt or read the file.")
        print("Possible reasons: Wrong password, corrupted file, or missing 'credentials.enc'.")

if __name__ == "__main__":
    validate_credentials()