import os
os.environ["GHOST_API_URL"] = "http://localhost:2368"
os.environ["GHOST_ADMIN_API_KEY"] = "68d15fc0a1affd0001b5c0db:e3a2638cc139821e9fc17e0bfb54ca92ab67cfd14ce5aabc53b65e43353d60cb"

from ghostctl.client import GhostClient
from ghostctl.config import Profile

profile = Profile(
    name="test",
    url="http://localhost:2368",
    admin_key="68d15fc0a1affd0001b5c0db:e3a2638cc139821e9fc17e0bfb54ca92ab67cfd14ce5aabc53b65e43353d60cb"
)

client = GhostClient(profile)

try:
    # Try a simple request
    result = client.get_posts(limit=1)
    print("✓ Connection successful!")
    print(f"Found {len(result.get('posts', []))} posts")
except Exception as e:
    print(f"✗ Connection failed: {e}")
    import traceback
    traceback.print_exc()
