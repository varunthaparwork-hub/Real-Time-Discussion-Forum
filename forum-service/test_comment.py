"""Make a test comment on thread 13 as testuser1 (user_id=5)"""
import urllib.request
import json

# Step 1: Login as testuser1
login_data = json.dumps({"username": "testuser1", "password": "Test@1234"}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8001/api/accounts/login/",
    data=login_data,
    headers={"Content-Type": "application/json"}
)
resp = urllib.request.urlopen(req)
tokens = json.loads(resp.read())
access_token = tokens["access"]
print(f"Logged in. Token: {access_token[:20]}...")

# Step 2: Post a comment on thread 13
comment_data = json.dumps({
    "content": "DEBUG TEST COMMENT - checking publish events",
    "thread_id": 13
}).encode()
req2 = urllib.request.Request(
    "http://127.0.0.1:8000/comments/",
    data=comment_data,
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
)
resp2 = urllib.request.urlopen(req2)
result = json.loads(resp2.read())
print(f"Comment created: {json.dumps(result, indent=2, default=str)}")
