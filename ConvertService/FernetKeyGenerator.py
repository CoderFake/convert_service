import base64
from cryptography.fernet import Fernet

def generate_fernet_key():
    key = Fernet.generate_key()
    urlsafe_key = base64.urlsafe_b64encode(key)
    return urlsafe_key

print(generate_fernet_key().decode('utf-8'))