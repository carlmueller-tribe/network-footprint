from typing import TypedDict


class PatternSpec(TypedDict):
    pattern: str
    category: str
    stack: str


NODE_PATTERNS: list[PatternSpec] = [
    # Network calls — library imports
    {"pattern": r"import.*axios", "category": "network_call", "stack": "node"},
    {"pattern": r"require.*axios", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*node-fetch", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*\bgot\b", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*superagent", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*\bky\b", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*undici", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*\bws\b", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*socket\.io", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*@apollo/client", "category": "network_call", "stack": "node"},
    {"pattern": r"import.*graphql-request", "category": "network_call", "stack": "node"},
    # Network calls — native APIs
    {"pattern": r"\bfetch\(", "category": "network_call", "stack": "node"},
    {"pattern": r"new XMLHttpRequest", "category": "network_call", "stack": "node"},
    {"pattern": r"WebSocket\(", "category": "network_call", "stack": "node"},
    {"pattern": r"EventSource\(", "category": "network_call", "stack": "node"},
    # Route definitions
    {
        "pattern": r"(app|router)\.(get|post|put|patch|delete|use)\(",
        "category": "route_definition",
        "stack": "node",
    },
    {"pattern": r"createServer\(", "category": "route_definition", "stack": "node"},
]

PYTHON_PATTERNS: list[PatternSpec] = [
    # Network calls — library imports
    {"pattern": r"import requests", "category": "network_call", "stack": "python"},
    {"pattern": r"from requests", "category": "network_call", "stack": "python"},
    {"pattern": r"import httpx", "category": "network_call", "stack": "python"},
    {"pattern": r"from httpx", "category": "network_call", "stack": "python"},
    {"pattern": r"import aiohttp", "category": "network_call", "stack": "python"},
    {"pattern": r"from aiohttp", "category": "network_call", "stack": "python"},
    {"pattern": r"import boto3", "category": "network_call", "stack": "python"},
    {"pattern": r"import botocore", "category": "network_call", "stack": "python"},
    {"pattern": r"import openai", "category": "network_call", "stack": "python"},
    {"pattern": r"import anthropic", "category": "network_call", "stack": "python"},
    {"pattern": r"from openai", "category": "network_call", "stack": "python"},
    {"pattern": r"from anthropic", "category": "network_call", "stack": "python"},
    {"pattern": r"from urllib", "category": "network_call", "stack": "python"},
    {"pattern": r"import urllib", "category": "network_call", "stack": "python"},
    {"pattern": r"import http\.client", "category": "network_call", "stack": "python"},
    # Route definitions
    {
        "pattern": r"@(app|router|blueprint)\.(get|post|put|patch|delete|route)\(",
        "category": "route_definition",
        "stack": "python",
    },
    {"pattern": r"\bpath\(", "category": "route_definition", "stack": "python"},
    {"pattern": r"\bre_path\(", "category": "route_definition", "stack": "python"},
    {"pattern": r"\burl\(", "category": "route_definition", "stack": "python"},
]

DEVOPS_PATTERNS: list[PatternSpec] = [
    {"pattern": r"EXPOSE\s+\d+", "category": "devops", "stack": "devops"},
    {"pattern": r"^\s*ports:", "category": "devops", "stack": "devops"},
    {"pattern": r"ENV.*(URL|HOST|ENDPOINT)", "category": "devops", "stack": "devops"},
    {"pattern": r"curl\s", "category": "devops", "stack": "devops"},
    {"pattern": r"wget\s", "category": "devops", "stack": "devops"},
    {"pattern": r"ingress:", "category": "devops", "stack": "devops"},
    {"pattern": r"LoadBalancer", "category": "devops", "stack": "devops"},
]

ALL_PATTERNS: list[PatternSpec] = NODE_PATTERNS + PYTHON_PATTERNS + DEVOPS_PATTERNS
