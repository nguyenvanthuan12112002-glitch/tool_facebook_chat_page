import asyncio
import sqlite3
import requests

conn = sqlite3.connect('facebook_sync.db')
cursor = conn.cursor()
pages = cursor.execute('select page_id, page_name, page_access_token from v_pages').fetchall()
conn.close()

print(f"Found {len(pages)} pages in DB.")

psid = "37138655979114649"

for p in pages:
    page_id, page_name, token = p[0], p[1], p[2]
    url = f"https://graph.facebook.com/v19.0/{psid}"
    params = {
        "fields": "name,first_name,last_name,profile_pic",
        "access_token": token
    }
    try:
        r = requests.get(url, params=params, timeout=5)
        print(f"Page '{page_name}' ({page_id}) -> Response: {r.status_code} {r.json()}")
    except Exception as e:
        print(f"Error querying for page '{page_name}': {e}")
