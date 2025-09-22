import jwt
import time
from datetime import datetime

# The API key
api_key = "68d15fc0a1affd0001b5c0db:e3a2638cc139821e9fc17e0bfb54ca92ab67cfd14ce5aabc53b65e43353d60cb"

# Split the key
key_id, secret = api_key.split(":")

# Decode the secret from hex
secret_bytes = bytes.fromhex(secret)

# Create JWT token
iat = int(time.time())
header = {
    "alg": "HS256",
    "typ": "JWT",
    "kid": key_id
}
payload = {
    "iat": iat,
    "exp": iat + 5 * 60,
    "aud": "/admin/"
}

token = jwt.encode(
    payload,
    secret_bytes,
    algorithm="HS256",
    headers=header
)

print(f"Key ID: {key_id}")
print(f"Secret (hex): {secret}")
print(f"JWT Token: {token}")

# Test with requests
import requests

headers = {
    "Authorization": f"Ghost {token}",
    "Accept-Version": "v5.0"
}

response = requests.get("http://localhost:2368/ghost/api/admin/posts/", headers=headers)
print(f"\nAPI Response: {response.status_code}")
if response.status_code == 200:
    print("✓ Authentication successful!")
    data = response.json()
    print(f"Found {len(data.get('posts', []))} posts")
else:
    print(f"✗ Authentication failed: {response.text}")
