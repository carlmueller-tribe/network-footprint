from flask import Flask

app = Flask(__name__)


@app.get("/health")
def health():  # type: ignore[return]
    return "ok"


@app.post("/users")
def create_user():  # type: ignore[return]
    pass
