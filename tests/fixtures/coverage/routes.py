from flask import Flask

app = Flask(__name__)


@app.get("/health")
def health():  # type: ignore[return]
    return "ok"


@app.get("/users")
def list_users():  # type: ignore[return]
    pass


@app.post("/users")
def create_user():  # type: ignore[return]
    pass


@app.get("/orphaned-endpoint")
def orphaned():  # type: ignore[return]
    pass
