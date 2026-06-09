import requests
from flask import Flask

app = Flask(__name__)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/sync")
def sync() -> dict[str, object]:
    resp = requests.get("https://api.example.com/data")
    return resp.json()
