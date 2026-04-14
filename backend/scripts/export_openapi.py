from app.core.config import settings
from pathlib import Path
import requests

if settings.BACKEND_HOST == "0.0.0.0":
    settings.BACKEND_HOST = "localhost"
url = f"http://{settings.BACKEND_HOST}:{settings.BACKEND_PORT}/openapi.json"


response = requests.get(url)
if response.status_code != 200:
    raise Exception(f"Failed to export openapi.json: {response.status_code}")
target_path = Path(__file__).parent.parent.parent / "frontend" / "openapi.json"
with open(target_path, "w") as f:
    f.write(response.text)
print(f"Exported openapi.json to {target_path}")
