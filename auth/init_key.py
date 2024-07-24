import os


# Generate a random 256 bit key
def generate_aes_key():
    return os.urandom(16)


if __name__ == "__main__":
    # Call function to generate key
    key = generate_aes_key()
    # Convert the key to hexadecimal format for display
    key_hex = key.hex()
    print("key:", key_hex)

