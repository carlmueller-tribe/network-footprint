from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from footprint.patterns import PatternSpec


@dataclass
class ParsedDep:
    name: str
    ecosystem: str  # "node" | "python" | "go" | "rust"
    transitive: bool = False


def parse_package_json(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        data: dict[str, Any] = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    deps: dict[str, Any] = data.get("dependencies") or {}
    return [ParsedDep(name=name, ecosystem="node") for name in deps]


def parse_package_lock_json(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        data: dict[str, Any] = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    packages: dict[str, Any] = data.get("packages") or {}
    result: list[ParsedDep] = []
    for key in packages:
        if not key or key == "":
            continue
        name = key.removeprefix("node_modules/")
        if name:
            result.append(ParsedDep(name=name, ecosystem="node", transitive=True))
    return result


def parse_requirements_txt(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return []
    result: list[ParsedDep] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name = re.split(r"[=<>!~;\[]", line)[0].strip()
        if name:
            result.append(ParsedDep(name=name, ecosystem="python"))
    return result


def parse_pyproject_toml(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        data: dict[str, Any] = tomllib.loads(path.read_text())
    except Exception:
        return []
    deps: list[Any] = data.get("project", {}).get("dependencies") or []
    result: list[ParsedDep] = []
    for dep in deps:
        if not isinstance(dep, str):
            continue
        name = re.split(r"[=<>!~;\[]", dep)[0].strip()
        if name:
            result.append(ParsedDep(name=name, ecosystem="python"))
    return result


def parse_pipfile(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        data: dict[str, Any] = tomllib.loads(path.read_text())
    except Exception:
        return []
    packages: dict[str, Any] = data.get("packages") or {}
    return [ParsedDep(name=name, ecosystem="python") for name in packages]


def parse_go_mod(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        text = path.read_text()
    except OSError:
        return []
    result: list[ParsedDep] = []
    in_require = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("require ("):
            in_require = True
            continue
        if in_require and stripped == ")":
            in_require = False
            continue
        if in_require or stripped.startswith("require "):
            parts = stripped.removeprefix("require ").split()
            if parts:
                result.append(ParsedDep(name=parts[0], ecosystem="go"))
    return result


def parse_cargo_toml(path: Path) -> list[ParsedDep]:
    if not path.exists():
        return []
    try:
        data: dict[str, Any] = tomllib.loads(path.read_text())
    except Exception:
        return []
    deps: dict[str, Any] = data.get("dependencies") or {}
    return [ParsedDep(name=name, ecosystem="rust") for name in deps]


_SKIP_DIRS = frozenset(
    {
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".git",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "coverage",
        ".mypy_cache",
        ".ruff_cache",
    }
)


def _find_manifests(repo_root: Path, filename: str) -> list[Path]:
    """Find all manifest files with the given name under repo_root, skipping build/dep dirs.

    Uses os.walk with in-place dir pruning so node_modules/.venv trees are never traversed.
    """
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        if filename in filenames:
            found.append(Path(dirpath) / filename)
    return found


def parse_all(repo_root: Path) -> list[ParsedDep]:
    """Parse all dependency manifests found anywhere under repo_root.

    Searches subdirectories so monorepos (e.g. frontend/ + backend/) are covered.
    Deduplicates by (name, ecosystem) to avoid double-counting shared packages.
    """
    seen: set[tuple[str, str]] = set()
    result: list[ParsedDep] = []

    def add(deps: list[ParsedDep]) -> None:
        for dep in deps:
            key = (dep.name.lower(), dep.ecosystem)
            if key not in seen:
                seen.add(key)
                result.append(dep)

    for p in _find_manifests(repo_root, "package.json"):
        add(parse_package_json(p))
    for p in _find_manifests(repo_root, "package-lock.json"):
        add(parse_package_lock_json(p))
    for p in _find_manifests(repo_root, "requirements.txt"):
        add(parse_requirements_txt(p))
    for p in _find_manifests(repo_root, "pyproject.toml"):
        add(parse_pyproject_toml(p))
    for p in _find_manifests(repo_root, "Pipfile"):
        add(parse_pipfile(p))
    for p in _find_manifests(repo_root, "go.mod"):
        add(parse_go_mod(p))
    for p in _find_manifests(repo_root, "Cargo.toml"):
        add(parse_cargo_toml(p))

    return result


@dataclass
class ResolvedPackage:
    package: str
    import_name: str
    network_capable: bool
    category: str | None
    source: str  # "lookup" | "claude" | "manifest_override" | "unknown_package"
    transitive: bool = False


KNOWN_PACKAGES: dict[str, dict[str, Any]] = {
    # Node
    "axios": {"network_capable": True, "import_name": "axios", "category": "network_call"},
    "node-fetch": {
        "network_capable": True,
        "import_name": "node-fetch",
        "category": "network_call",
    },
    "got": {"network_capable": True, "import_name": "got", "category": "network_call"},
    "superagent": {
        "network_capable": True,
        "import_name": "superagent",
        "category": "network_call",
    },
    "ky": {"network_capable": True, "import_name": "ky", "category": "network_call"},
    "undici": {"network_capable": True, "import_name": "undici", "category": "network_call"},
    "ws": {"network_capable": True, "import_name": "ws", "category": "network_call"},
    "socket.io-client": {
        "network_capable": True,
        "import_name": "socket.io-client",
        "category": "network_call",
    },
    "@apollo/client": {
        "network_capable": True,
        "import_name": "@apollo/client",
        "category": "network_call",
    },
    "graphql-request": {
        "network_capable": True,
        "import_name": "graphql-request",
        "category": "network_call",
    },
    "express": {"network_capable": True, "import_name": "express", "category": "route_definition"},
    "fastify": {"network_capable": True, "import_name": "fastify", "category": "route_definition"},
    "koa": {"network_capable": True, "import_name": "koa", "category": "route_definition"},
    # Python
    "requests": {"network_capable": True, "import_name": "requests", "category": "network_call"},
    "httpx": {"network_capable": True, "import_name": "httpx", "category": "network_call"},
    "aiohttp": {"network_capable": True, "import_name": "aiohttp", "category": "network_call"},
    "boto3": {"network_capable": True, "import_name": "boto3", "category": "network_call"},
    "botocore": {"network_capable": True, "import_name": "botocore", "category": "network_call"},
    "openai": {"network_capable": True, "import_name": "openai", "category": "network_call"},
    "anthropic": {"network_capable": True, "import_name": "anthropic", "category": "network_call"},
    "fastapi": {"network_capable": True, "import_name": "fastapi", "category": "route_definition"},
    "flask": {"network_capable": True, "import_name": "flask", "category": "route_definition"},
    "django": {"network_capable": True, "import_name": "django", "category": "route_definition"},
    "pillow": {"network_capable": False, "import_name": "PIL", "category": None},
    "opencv-python": {"network_capable": False, "import_name": "cv2", "category": None},
    "python-dotenv": {"network_capable": False, "import_name": "dotenv", "category": None},
    "numpy": {"network_capable": False, "import_name": "numpy", "category": None},
    "pandas": {"network_capable": False, "import_name": "pandas", "category": None},
    "pydantic": {"network_capable": False, "import_name": "pydantic", "category": None},
    # Telemetry / observability — background calls, not core function
    "sentry-sdk": {"network_capable": True, "import_name": "sentry_sdk", "category": "telemetry"},
    "datadog": {"network_capable": True, "import_name": "datadog", "category": "telemetry"},
    "ddtrace": {"network_capable": True, "import_name": "ddtrace", "category": "telemetry"},
    "opentelemetry-sdk": {
        "network_capable": True,
        "import_name": "opentelemetry",
        "category": "telemetry",
    },
    "opentelemetry-api": {
        "network_capable": True,
        "import_name": "opentelemetry",
        "category": "telemetry",
    },
    "segment-analytics-python": {
        "network_capable": True,
        "import_name": "segment",
        "category": "telemetry",
    },
    "analytics-python": {
        "network_capable": True,
        "import_name": "analytics",
        "category": "telemetry",
    },
    "posthog": {"network_capable": True, "import_name": "posthog", "category": "telemetry"},
    "mixpanel": {"network_capable": True, "import_name": "mixpanel", "category": "telemetry"},
    "amplitude": {"network_capable": True, "import_name": "amplitude", "category": "telemetry"},
    "newrelic": {"network_capable": True, "import_name": "newrelic", "category": "telemetry"},
    "rollbar": {"network_capable": True, "import_name": "rollbar", "category": "telemetry"},
    "bugsnag": {"network_capable": True, "import_name": "bugsnag", "category": "telemetry"},
    "honeybadger": {
        "network_capable": True,
        "import_name": "honeybadger",
        "category": "telemetry",
    },
    "prometheus-client": {
        "network_capable": True,
        "import_name": "prometheus_client",
        "category": "telemetry",
    },
    # Node telemetry
    "@sentry/node": {
        "network_capable": True,
        "import_name": "@sentry/node",
        "category": "telemetry",
    },
    "@sentry/browser": {
        "network_capable": True,
        "import_name": "@sentry/browser",
        "category": "telemetry",
    },
    "@datadog/datadog-ci": {
        "network_capable": True,
        "import_name": "@datadog/datadog-ci",
        "category": "telemetry",
    },
    "@opentelemetry/sdk-node": {
        "network_capable": True,
        "import_name": "@opentelemetry/sdk-node",
        "category": "telemetry",
    },
    "@segment/analytics-node": {
        "network_capable": True,
        "import_name": "@segment/analytics-node",
        "category": "telemetry",
    },
    "posthog-node": {
        "network_capable": True,
        "import_name": "posthog-node",
        "category": "telemetry",
    },
    "mixpanel-browser": {
        "network_capable": True,
        "import_name": "mixpanel-browser",
        "category": "telemetry",
    },
    "pino": {"network_capable": False, "import_name": "pino", "category": None},
    "winston": {"network_capable": False, "import_name": "winston", "category": None},
    # Node — data fetching / real-time
    "swr": {"network_capable": True, "import_name": "swr", "category": "network_call"},
    "@tanstack/react-query": {
        "network_capable": True,
        "import_name": "@tanstack/react-query",
        "category": "network_call",
    },
    "@tanstack/query-core": {
        "network_capable": True,
        "import_name": "@tanstack/query-core",
        "category": "network_call",
    },
    "@microsoft/fetch-event-source": {
        "network_capable": True,
        "import_name": "@microsoft/fetch-event-source",
        "category": "network_call",
    },
    "eventsource": {
        "network_capable": True,
        "import_name": "eventsource",
        "category": "network_call",
    },
    "reconnecting-websocket": {
        "network_capable": True,
        "import_name": "reconnecting-websocket",
        "category": "network_call",
    },
    # Node — frameworks / routing
    "next": {"network_capable": True, "import_name": "next", "category": "route_definition"},
    "nuxt": {"network_capable": True, "import_name": "nuxt", "category": "route_definition"},
    "hono": {"network_capable": True, "import_name": "hono", "category": "route_definition"},
    "h3": {"network_capable": True, "import_name": "h3", "category": "route_definition"},
    "@hapi/hapi": {
        "network_capable": True,
        "import_name": "@hapi/hapi",
        "category": "route_definition",
    },
    "nestjs": {
        "network_capable": True,
        "import_name": "@nestjs/core",
        "category": "route_definition",
    },
    "@nestjs/core": {
        "network_capable": True,
        "import_name": "@nestjs/core",
        "category": "route_definition",
    },
    "@nestjs/common": {
        "network_capable": True,
        "import_name": "@nestjs/common",
        "category": "route_definition",
    },
    "react-router-dom": {
        "network_capable": True,
        "import_name": "react-router-dom",
        "category": "route_definition",
    },
    "react-router": {
        "network_capable": True,
        "import_name": "react-router",
        "category": "route_definition",
    },
    "vue-router": {
        "network_capable": True,
        "import_name": "vue-router",
        "category": "route_definition",
    },
    # Node — payments / messaging / infra
    "stripe": {"network_capable": True, "import_name": "stripe", "category": "network_call"},
    "@stripe/stripe-js": {
        "network_capable": True,
        "import_name": "@stripe/stripe-js",
        "category": "network_call",
    },
    "twilio": {"network_capable": True, "import_name": "twilio", "category": "network_call"},
    "@sendgrid/mail": {
        "network_capable": True,
        "import_name": "@sendgrid/mail",
        "category": "network_call",
    },
    "nodemailer": {
        "network_capable": True,
        "import_name": "nodemailer",
        "category": "network_call",
    },
    "@slack/web-api": {
        "network_capable": True,
        "import_name": "@slack/web-api",
        "category": "network_call",
    },
    "@slack/bolt": {
        "network_capable": True,
        "import_name": "@slack/bolt",
        "category": "network_call",
    },
    "firebase": {"network_capable": True, "import_name": "firebase", "category": "network_call"},
    "firebase-admin": {
        "network_capable": True,
        "import_name": "firebase-admin",
        "category": "network_call",
    },
    "@supabase/supabase-js": {
        "network_capable": True,
        "import_name": "@supabase/supabase-js",
        "category": "network_call",
    },
    "supabase": {
        "network_capable": True,
        "import_name": "@supabase/supabase-js",
        "category": "network_call",
    },
    "ioredis": {"network_capable": True, "import_name": "ioredis", "category": "network_call"},
    "redis": {"network_capable": True, "import_name": "redis", "category": "network_call"},
    # Node — AWS
    "aws-sdk": {"network_capable": True, "import_name": "aws-sdk", "category": "network_call"},
    "@aws-sdk/client-s3": {
        "network_capable": True,
        "import_name": "@aws-sdk/client-s3",
        "category": "network_call",
    },
    "@aws-sdk/client-ses": {
        "network_capable": True,
        "import_name": "@aws-sdk/client-ses",
        "category": "network_call",
    },
    "@aws-sdk/client-sqs": {
        "network_capable": True,
        "import_name": "@aws-sdk/client-sqs",
        "category": "network_call",
    },
    # Node — AI
    "@anthropic-ai/sdk": {
        "network_capable": True,
        "import_name": "@anthropic-ai/sdk",
        "category": "network_call",
    },
    "@google/generative-ai": {
        "network_capable": True,
        "import_name": "@google/generative-ai",
        "category": "network_call",
    },
    "cohere-ai": {
        "network_capable": True,
        "import_name": "cohere-ai",
        "category": "network_call",
    },
    "groq-sdk": {
        "network_capable": True,
        "import_name": "groq-sdk",
        "category": "network_call",
    },
    # Node — telemetry (additional)
    "@sentry/react": {
        "network_capable": True,
        "import_name": "@sentry/react",
        "category": "telemetry",
    },
    "@sentry/nextjs": {
        "network_capable": True,
        "import_name": "@sentry/nextjs",
        "category": "telemetry",
    },
    "@sentry/vue": {
        "network_capable": True,
        "import_name": "@sentry/vue",
        "category": "telemetry",
    },
    "@opentelemetry/sdk-trace-web": {
        "network_capable": True,
        "import_name": "@opentelemetry/sdk-trace-web",
        "category": "telemetry",
    },
    "@opentelemetry/auto-instrumentations-node": {
        "network_capable": True,
        "import_name": "@opentelemetry/auto-instrumentations-node",
        "category": "telemetry",
    },
    # Python — network / HTTP
    "urllib3": {
        "network_capable": True,
        "import_name": "urllib3",
        "category": "network_call",
    },
    "httpcore": {
        "network_capable": True,
        "import_name": "httpcore",
        "category": "network_call",
    },
    "websockets": {
        "network_capable": True,
        "import_name": "websockets",
        "category": "network_call",
    },
    "websocket-client": {
        "network_capable": True,
        "import_name": "websocket",
        "category": "network_call",
    },
    "grpcio": {"network_capable": True, "import_name": "grpc", "category": "network_call"},
    "paramiko": {"network_capable": True, "import_name": "paramiko", "category": "network_call"},
    # Python — frameworks / servers
    "uvicorn": {
        "network_capable": True,
        "import_name": "uvicorn",
        "category": "route_definition",
    },
    "gunicorn": {
        "network_capable": True,
        "import_name": "gunicorn",
        "category": "route_definition",
    },
    "starlette": {
        "network_capable": True,
        "import_name": "starlette",
        "category": "route_definition",
    },
    "tornado": {
        "network_capable": True,
        "import_name": "tornado",
        "category": "route_definition",
    },
    "falcon": {
        "network_capable": True,
        "import_name": "falcon",
        "category": "route_definition",
    },
    "litestar": {
        "network_capable": True,
        "import_name": "litestar",
        "category": "route_definition",
    },
    "sanic": {"network_capable": True, "import_name": "sanic", "category": "route_definition"},
    # Python — payments / messaging / infra
    "sendgrid": {
        "network_capable": True,
        "import_name": "sendgrid",
        "category": "network_call",
    },
    "slack-sdk": {
        "network_capable": True,
        "import_name": "slack_sdk",
        "category": "network_call",
    },
    "slack_bolt": {
        "network_capable": True,
        "import_name": "slack_bolt",
        "category": "network_call",
    },
    "aioredis": {
        "network_capable": True,
        "import_name": "aioredis",
        "category": "network_call",
    },
    "pymongo": {"network_capable": True, "import_name": "pymongo", "category": "network_call"},
    "motor": {"network_capable": True, "import_name": "motor", "category": "network_call"},
    "elasticsearch": {
        "network_capable": True,
        "import_name": "elasticsearch",
        "category": "network_call",
    },
    "opensearch-py": {
        "network_capable": True,
        "import_name": "opensearchpy",
        "category": "network_call",
    },
    "celery": {"network_capable": True, "import_name": "celery", "category": "network_call"},
    "pika": {"network_capable": True, "import_name": "pika", "category": "network_call"},
    "aiokafka": {
        "network_capable": True,
        "import_name": "aiokafka",
        "category": "network_call",
    },
    "kafka-python": {
        "network_capable": True,
        "import_name": "kafka",
        "category": "network_call",
    },
    "msal": {"network_capable": True, "import_name": "msal", "category": "network_call"},
    # Python — cloud
    "google-cloud-storage": {
        "network_capable": True,
        "import_name": "google.cloud.storage",
        "category": "network_call",
    },
    "google-cloud-bigquery": {
        "network_capable": True,
        "import_name": "google.cloud.bigquery",
        "category": "network_call",
    },
    "google-auth": {
        "network_capable": True,
        "import_name": "google.auth",
        "category": "network_call",
    },
    "google-api-python-client": {
        "network_capable": True,
        "import_name": "googleapiclient",
        "category": "network_call",
    },
    "azure-storage-blob": {
        "network_capable": True,
        "import_name": "azure.storage.blob",
        "category": "network_call",
    },
    "azure-identity": {
        "network_capable": True,
        "import_name": "azure.identity",
        "category": "network_call",
    },
    "azure-keyvault-secrets": {
        "network_capable": True,
        "import_name": "azure.keyvault.secrets",
        "category": "network_call",
    },
    "kubernetes": {
        "network_capable": True,
        "import_name": "kubernetes",
        "category": "network_call",
    },
    # Python — AI / LLM
    "langchain": {
        "network_capable": True,
        "import_name": "langchain",
        "category": "network_call",
    },
    "langchain-openai": {
        "network_capable": True,
        "import_name": "langchain_openai",
        "category": "network_call",
    },
    "langchain-anthropic": {
        "network_capable": True,
        "import_name": "langchain_anthropic",
        "category": "network_call",
    },
    "langchain-google-genai": {
        "network_capable": True,
        "import_name": "langchain_google_genai",
        "category": "network_call",
    },
    "cohere": {"network_capable": True, "import_name": "cohere", "category": "network_call"},
    "groq": {"network_capable": True, "import_name": "groq", "category": "network_call"},
    "together": {"network_capable": True, "import_name": "together", "category": "network_call"},
    "litellm": {"network_capable": True, "import_name": "litellm", "category": "network_call"},
    "replicate": {
        "network_capable": True,
        "import_name": "replicate",
        "category": "network_call",
    },
    "huggingface-hub": {
        "network_capable": True,
        "import_name": "huggingface_hub",
        "category": "network_call",
    },
    "openai-agents": {
        "network_capable": True,
        "import_name": "agents",
        "category": "network_call",
    },
    "mcp": {"network_capable": True, "import_name": "mcp", "category": "network_call"},
    # Python — telemetry (additional)
    "opentelemetry-distro": {
        "network_capable": True,
        "import_name": "opentelemetry",
        "category": "telemetry",
    },
    "opentelemetry-exporter-otlp": {
        "network_capable": True,
        "import_name": "opentelemetry",
        "category": "telemetry",
    },
    "logfire": {"network_capable": True, "import_name": "logfire", "category": "telemetry"},
    "elastic-apm": {
        "network_capable": True,
        "import_name": "elasticapm",
        "category": "telemetry",
    },
    # Python — not network
    "pydantic-settings": {
        "network_capable": False,
        "import_name": "pydantic_settings",
        "category": None,
    },
    "sqlalchemy": {"network_capable": False, "import_name": "sqlalchemy", "category": None},
    "alembic": {"network_capable": False, "import_name": "alembic", "category": None},
    "orjson": {"network_capable": False, "import_name": "orjson", "category": None},
    "pyyaml": {"network_capable": False, "import_name": "yaml", "category": None},
    "rich": {"network_capable": False, "import_name": "rich", "category": None},
    "typer": {"network_capable": False, "import_name": "typer", "category": None},
    "click": {"network_capable": False, "import_name": "click", "category": None},
    "aiofiles": {"network_capable": False, "import_name": "aiofiles", "category": None},
    "backoff": {"network_capable": False, "import_name": "backoff", "category": None},
    "tenacity": {"network_capable": False, "import_name": "tenacity", "category": None},
    "cryptography": {"network_capable": False, "import_name": "cryptography", "category": None},
    "passlib": {"network_capable": False, "import_name": "passlib", "category": None},
    "python-jose": {"network_capable": False, "import_name": "jose", "category": None},
    "pyjwt": {"network_capable": False, "import_name": "jwt", "category": None},
    "pdf2image": {"network_capable": False, "import_name": "pdf2image", "category": None},
    "boto3-stubs": {"network_capable": False, "import_name": "mypy_boto3", "category": None},
}

_CLASSIFIER_PROMPT = """\
You are a code analysis assistant. Given a list of package names, classify each one.

For each package return:
- network_capable: true if the package makes or handles any outbound network connections
- import_name: the canonical Python or JS import name (may differ from package name)
- category: one of:
    "network_call"     — explicit developer-initiated calls to an external third-party service
                         (e.g. payment APIs, AI inference, cloud SDKs, external REST clients)
    "route_definition" — defines or calls internal app routes (server frameworks, internal
                         HTTP clients)
    "telemetry"        — background/implicit calls to monitoring, analytics, or observability
                         services that are a side-effect of SDK init, not core app function
                         (e.g. error tracking, metrics, distributed tracing, analytics events)
    null               — not network-related

Respond ONLY with a JSON array, no preamble, no markdown fences:
[
  {{"package": "stripe", "network_capable": true, "import_name": "stripe",
    "category": "network_call"}},
  {{"package": "sentry-sdk", "network_capable": true, "import_name": "sentry_sdk",
    "category": "telemetry"}},
  {{"package": "numpy", "network_capable": false, "import_name": "numpy", "category": null}},
  ...
]

Packages to classify:
{packages}
"""


def _classify_with_claude(packages: list[str]) -> str:
    """Call Claude for package classification. Tries claude CLI subprocess first, SDK fallback."""
    preview = ", ".join(packages[:5]) + ("..." if len(packages) > 5 else "")
    print(
        f"[footprint] asking Claude to classify {len(packages)} unknown package(s): {preview}",
        file=sys.stderr,
    )
    prompt = _CLASSIFIER_PROMPT.format(packages="\n".join(packages))
    if shutil.which("claude"):
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        raise RuntimeError(f"claude CLI failed: {result.stderr.strip()}")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return _classify_with_sdk(packages)
    raise RuntimeError(
        "No Claude authentication available. "
        "Install Claude Code (claude.ai/code) or set ANTHROPIC_API_KEY."
    )


def _classify_with_sdk(packages: list[str]) -> str:
    """Call Claude via anthropic SDK using ANTHROPIC_API_KEY."""
    import anthropic  # noqa: PLC0415

    prompt = _CLASSIFIER_PROMPT.format(packages="\n".join(packages))
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    content = msg.content[0]
    if content.type != "text":
        raise RuntimeError("Unexpected response type from Claude SDK")
    print(
        f"[footprint] Claude SDK: {msg.usage.input_tokens} in / {msg.usage.output_tokens} out",  # noqa: E501
        file=sys.stderr,
    )
    return str(content.text)


def _parse_claude_response(raw: str) -> list[dict[str, Any]]:
    """Extract JSON array from Claude response, handling markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        end_fence = next((i for i, ln in enumerate(lines[1:], 1) if ln.strip() == "```"), None)
        text = "\n".join(lines[1:end_fence] if end_fence else lines[1:])
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        return list(json.loads(text[start : end + 1]))
    except json.JSONDecodeError:
        return []


def resolve_packages(
    deps: list[ParsedDep],
    overrides: dict[str, str] | None = None,
) -> list[ResolvedPackage]:
    """Resolve deps to ResolvedPackage list. overrides maps package name -> import_name."""
    overrides = overrides or {}
    results: list[ResolvedPackage] = []
    unknown: list[ParsedDep] = []

    for dep in deps:
        name_lower = dep.name.lower()
        if dep.name in overrides:
            entry = KNOWN_PACKAGES.get(name_lower, {})
            results.append(
                ResolvedPackage(
                    package=dep.name,
                    import_name=overrides[dep.name],
                    network_capable=bool(entry.get("network_capable", False)),
                    category=entry.get("category"),
                    source="manifest_override",
                    transitive=dep.transitive,
                )
            )
        elif name_lower in KNOWN_PACKAGES:
            entry = KNOWN_PACKAGES[name_lower]
            results.append(
                ResolvedPackage(
                    package=dep.name,
                    import_name=str(entry["import_name"]),
                    network_capable=bool(entry["network_capable"]),
                    category=entry.get("category"),
                    source="lookup",
                    transitive=dep.transitive,
                )
            )
        else:
            unknown.append(dep)

    if unknown:
        try:
            raw = _classify_with_claude([d.name for d in unknown])
            classified = _parse_claude_response(raw)
            classified_map: dict[str, dict[str, Any]] = {
                item["package"]: item for item in classified if isinstance(item, dict)
            }
        except Exception as exc:
            warnings.warn(
                f"Claude classifier failed: {exc}. Treating unknown packages as non-network.",
                stacklevel=2,
            )
            classified_map = {}

        for dep in unknown:
            item = classified_map.get(dep.name)
            if item:
                results.append(
                    ResolvedPackage(
                        package=dep.name,
                        import_name=str(item.get("import_name", dep.name)),
                        network_capable=bool(item.get("network_capable", False)),
                        category=item.get("category"),
                        source="claude",
                        transitive=dep.transitive,
                    )
                )
            else:
                results.append(
                    ResolvedPackage(
                        package=dep.name,
                        import_name=dep.name,
                        network_capable=True,  # conservative: assume capable, let human verify
                        category="network_call",
                        source="unknown_package",
                        transitive=dep.transitive,
                    )
                )

    return results


def _make_pattern(
    pat: str,
    cat: str,
    stack: str,
    transitive: bool,
    source: str = "dependency_resolved",
) -> PatternSpec:
    spec: PatternSpec = {
        "pattern": pat,
        "category": cat,
        "stack": stack,
        "source": source,
    }
    if transitive:
        spec["transitive"] = True
    return spec


def generate_patterns(
    resolved: list[ResolvedPackage],
    ecosystem: str,
) -> list[PatternSpec]:
    """Generate regex patterns from network-capable resolved packages."""
    patterns: list[PatternSpec] = []
    for pkg in resolved:
        if not pkg.network_capable:
            continue
        escaped = re.escape(pkg.import_name)
        cat = pkg.category or "network_call"
        stack = ecosystem if ecosystem in ("node", "python", "devops") else "node"
        base_source = (
            "dependency_resolved" if pkg.source != "unknown_package" else "unknown_package"
        )
        if ecosystem == "python":
            patterns.append(
                _make_pattern(f"import {escaped}", cat, stack, pkg.transitive, base_source)
            )
            patterns.append(
                _make_pattern(f"from {escaped}", cat, stack, pkg.transitive, base_source)
            )
        else:  # node
            patterns.append(
                _make_pattern(f"from ['\"]{escaped}['\"]", cat, stack, pkg.transitive, base_source)
            )
            patterns.append(
                _make_pattern(
                    rf"require\(['\"]{escaped}['\"]", cat, stack, pkg.transitive, base_source
                )
            )
    return patterns
