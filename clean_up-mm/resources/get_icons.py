import requests
import json
import os
import argparse 

import utils.utils as utils

"""
Getting icons from Freepik API, 
rate limits apply, see: https://www.freepik.com/developers/dashboard/limits
API reference: https://docs.freepik.com/api-reference/icons/get-all-icons-by-order

----- SCRIPT USAGE -----
Run this in "resource" directory to save icons to the right path:
```
API_KEY=<Freepik_API_key> python get_icons.py <TYPE> <TERM>
```
`<TYPE>` is either "normal" or "abstract".
`<TERM>` is the search term, also will be used as the directory to save the requested icons.

----- REDISTRIBUTION -----
Freepik icons come from Flation,
https://support.flaticon.com/s/article/Accessing-the-API-FI?language=en_US
We are not allowed to redistribute the downloaded icons. See section 7 and 8.
https://www.flaticon.com/legal

The workaround is to download metadata (ID, url of the icons) and store them as instance.json, 
only really download the icons on the fly, when GM populate the instance.
"""

# 0. search term 
parser = argparse.ArgumentParser(description="Download icons from Freepik API by search term.")
parser.add_argument("type", help="The type of the icon")
parser.add_argument("term", help="Search term for icons (e.g., hat, cat, phone)")
args = parser.parse_args()

type = args.type
term = args.term

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
    "per_page": 100,
    "filters[color]": "multicolor",
    "filters[shape]": "fill",
    "filters[icon_type][]": "standard"
}


response = requests.request("GET", url, headers=headers, params=params)
data = json.loads(response.text)

print(data)

# 2. Store icon metadata for instance generator
icon_info = []

for obj in data['data']: 
    icon = {
            'id': obj['id'], 
            'name': obj['name'],
            'url': obj['thumbnails'][0]['url']
        }
    icon_info.append(icon)

filepath = os.path.join("icons", "metadata.json")
utils.update_json_file(filepath, type, {term: icon_info})

# 3. Download the icon and save it to file -- dev only, remove this when the repo becomes public
dirpath = os.path.join("icons", type, term)
os.makedirs(dirpath, exist_ok=True) 

for icon in icon_info: 

    icon_response = requests.get(icon['url'])
    filename = f"{icon['name']}-{icon['id']}.png"
    filepath = os.path.join(dirpath, filename)

    with open(filepath, "wb") as f:
        f.write(icon_response.content)

    print(f"Icon saved as {filepath}")
