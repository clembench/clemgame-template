import os
import subprocess

"""
This script write the metadata of the icons to `icons/metadata.json` and downloads the icons to `icons/<TYPE>/<TERM>`.

----- SCRIPT USAGE -----
Update `pairs` with the desired icon types and search terms.

Run this in "resource" directory to save icons to the right path:
```
API_KEY=<Freepik_API_key> python batch_get_icons.py
```
"""
API_KEY = os.getenv("API_KEY")

pairs = [
    # ("normal", "alarm clock"),
    # ("normal", "speaker"),
    # ("normal", "blender"),
    # ("normal", "mixer"),
    # ("normal", "electric kettle"),
    # ("normal", "flashlight"),
    # ("normal", "french fries"),
    # ("normal", "burger"),
    # ("normal", "hot dog"),
    # ("normal", "hairdryer"),
    # ("normal", "laptop"),
    # ("normal", "toilet paper"),
    # ("normal", "utensils"),
    # ("normal", "microwave"),
    # ("normal", "toaster"),
    # ("normal", "shower head"),
    # ("normal", "smartphone"),
    # ("normal", "keyboard"),
    # ("normal", "coffee cup"),
    # ("normal", "television"),
    # ("normal", "washing machine"),
    # ("normal", "refrigerator"),
    # ("normal", "bathtub"),
    # ("normal", "sunglasses"),
    # ("normal", "shopping cart"),


    ("abstract", "abstract shape"),
    ("abstract", "shape"),
    ("abstract", "math"),
    ("abstract", "triangle"),
    # ("abstract", "generic"),
    # ("abstract", "miscellaneous"),
    # ("abstract", "widget"),
    # ("abstract", "utility"),
    # ("abstract", "workflow"),
    # ("abstract", "integration"),
    # ("abstract", "process"),
    # ("abstract", "custom"),
    # ("abstract", "system"),
    # ("abstract", "service"),
    # ("abstract", "operations"),
    # ("abstract", "channel"),
    # ("abstract", "environment"),
    # ("abstract", "framework"),
    # ("abstract", "container"),
    # ("abstract", "instance"),
    # ("abstract", "logic"),
    # ("abstract", "trigger"),
    # ("abstract", "control"),
    # ("abstract", "artifact"),
    # ("abstract", "pattern"),
    # ("abstract", "state"),
    # ("abstract", "node"),
    # ("abstract", "stack"),
    # ("abstract", "function")

]

for type_, term in pairs:
    env = os.environ.copy()
    env["API_KEY"] = API_KEY
    subprocess.run(["python", "get_icons.py", type_, term], env=env)
