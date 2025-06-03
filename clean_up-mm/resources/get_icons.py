import requests
import json
import os
import argparse 

"""
Getting icons from Freepik API, 
rate limits apply, see: https://www.freepik.com/developers/dashboard/limits

Usage: 
Run this in "resource" directory to save icons to the right path:
```
API_KEY=<Freepik_API_key> python get_icons.py <TERM>
```

`<TERM>` is the search term, also will be used as the directory to save the requested icons.
"""

# 0. search term 
parser = argparse.ArgumentParser(description="Download icons from Freepik API by search term.")
parser.add_argument("term", help="Search term for icons (e.g., hat, cat, phone)")
args = parser.parse_args()

term = args.term
os.makedirs(term, exist_ok=True) 

# 1. get icon download url
# Freepik API key
API_KEY = os.getenv("API_KEY")

if API_KEY is None:
    raise EnvironmentError("Freepik API_KEY not set")

url = "https://api.freepik.com/v1/icons"

headers = {"x-freepik-api-key": API_KEY }

params = {
    "term": term,
    "page": 1,
    "per_page": 20,
    "filters[color]": "multicolor",
    "filters[shape]": "fill",
    "filters[icon_type][]": "standard"
}


response = requests.request("GET", url, headers=headers, params=params)
data = json.loads(response.text)

# print(data)

icon_info = []

for obj in data['data']: 
    icon = {
            'id': obj['id'], 
            'name': obj['name'],
            'url': obj['thumbnails'][0]['url']
        }
    icon_info.append(icon)

# 2. Download the icon and save it to file
for icon in icon_info: 

    icon_response = requests.get(icon['url'])
    filename = f"{icon['name']}-{icon['id']}.png"
    filepath = os.path.join("icons", term, filename)

    with open(filepath, "wb") as f:
        f.write(icon_response.content)

    print(f"Icon saved as {filepath}")
