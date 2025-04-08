"""
Generate a Fernet encryption key for securely storing Oura API tokens.
Run this script to generate a new key, then add it to your .env file.
"""
from cryptography.fernet import Fernet

def generate_fernet_key():
    """Generate a new Fernet key and print it."""
    key = Fernet.generate_key()
    print("\nGenerated Fernet key:")
    print(key.decode())
    print("\nAdd this to your .env file as FERNET_KEY.\n")
    return key

if __name__ == "__main__":
    generate_fernet_key() 