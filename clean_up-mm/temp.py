import requests
import json

response = requests.get(
  url="https://openrouter.ai/api/v1/auth/key",
  headers={
    "Authorization": f"Bearer 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"
  }
)

print(json.dumps(response.json(), indent=2))
