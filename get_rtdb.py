import json
import firebase_admin
from firebase_admin import credentials, db

# 1) Service account JSON file (ensure it's correct path and filename)
cred = credentials.Certificate("secrets/nautiqal-firebase-adminsdk-fbsvc-f658523edc.json")

# 2) Use your exact database URL (region included)
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://nautiqal-default-rtdb.asia-southeast1.firebasedatabase.app/"
})

# 3) Reference the root and fetch data
root_ref = db.reference("/")
data = root_ref.get()

# 4) Print and save data
print("Fetched data (type):", type(data).__name__)
print(json.dumps(data, indent=2, ensure_ascii=False))

with open("rtdb_dump.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("Data saved to rtdb_dump.json")
