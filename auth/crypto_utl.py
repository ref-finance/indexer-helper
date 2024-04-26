import os
from base64 import urlsafe_b64encode, urlsafe_b64decode

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def encrypt(plaintext: str, key: str) -> str:
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key.encode()), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plaintext.encode('utf-8')) + padder.finalize()
    ciphertext = encryptor.update(padded_data)
    return urlsafe_b64encode(iv).decode('utf-8') + urlsafe_b64encode(ciphertext+encryptor.finalize()).decode('utf-8')


def decrypt(ciphertext: str, key: str) -> str:
    iv = urlsafe_b64decode(ciphertext[0:24])
    encrypted_data = urlsafe_b64decode(ciphertext[24:])
    cipher = Cipher(algorithms.AES(key.encode()), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_plaintext = decryptor.update(encrypted_data) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
    return plaintext.decode('utf-8')


if __name__ == "__main__":
    key = '8309c61008a5f5ba6c51bbf977781c55'
    params = '{"path":"/list-token-price","time":"1714101889"}'
    encrypted_params = encrypt(params, key)
    print(f"encrypt：{encrypted_params}")
    decrypted_params = decrypt(encrypted_params, key)
    print(f"decrypt：{decrypted_params}")
