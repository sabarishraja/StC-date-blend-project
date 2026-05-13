import os
import requests
import base64
from dotenv import load_dotenv

load_dotenv()

FS_API_KEY = os.environ.get("FULLSTORY_API_KEY")
FS_API_URL = "https://api.fullstory.com/segments/v1/exports"

payload = {
    "segmentId": "everyone",
    "format": "FORMAT_CSV",
    "type": "TYPE_EVENT"
}

def try_auth(name, headers, auth=None):
    print(f"\nTrying {name}...")
    resp = requests.post(FS_API_URL, json=payload, headers=headers, auth=auth)
    print("Status:", resp.status_code)
    print("Response:", resp.text)

if __name__ == "__main__":
    # 1. Bearer
    try_auth("Bearer", {"Authorization": f"Bearer {FS_API_KEY}"})
    
    # 2. Basic literal
    try_auth("Basic Literal", {"Authorization": f"Basic {FS_API_KEY}"})
    
    # 3. Basic requests tuple (base64)
    try_auth("Requests auth tuple", {}, auth=(FS_API_KEY, ''))
    
    # 4. Basic with base64 explicitly
    b64_key = base64.b64encode(f"{FS_API_KEY}:".encode()).decode()
    try_auth("Explicit Basic Base64", {"Authorization": f"Basic {b64_key}"})
