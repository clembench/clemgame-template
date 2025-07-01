import json
import os

def load_or_create_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    return data

def save_json(data, filepath):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

"""
Adding a grandchild level key-value pair to the JSON file at filepath. 
{
    "normal": {
        "cake": [
            {
                "id": 1,
                "name": "Chocolate Cake",
                "url": "https://example.com/chocolate_cake.png"
            },
            // ...
        ], 
        // ...
    }, 
    "abstract:" {
        "abstract": [
            {
                "id": 2,
                "name": "Abstract Cake",
                "url": "https://example.com/abstract_cake.png"
            },
            // ...
        ]
    }
}
"""
def update_json_file(filepath, parent_key: str, new_items: dict):
    data = load_or_create_json(filepath)

    # Ensure parent_key exists and is a dict
    if parent_key not in data or not isinstance(data[parent_key], dict):
        data[parent_key] = {}

    # Update nested dict
    data[parent_key].update(new_items)

    save_json(data, filepath)
