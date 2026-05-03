import re

import pytest

from footprint.patterns import ALL_PATTERNS, DEVOPS_PATTERNS, NODE_PATTERNS, PYTHON_PATTERNS


@pytest.mark.parametrize(
    "line,expected_category",
    [
        ("import axios from 'axios';", "network_call"),
        ("import { get } from 'node-fetch';", "network_call"),
        ("const res = fetch('https://api.example.com/data');", "network_call"),
        ("const ws = new WebSocket('wss://example.com');", "network_call"),
        ("app.get('/users', handler);", "route_definition"),
        ("router.post('/items', handler);", "route_definition"),
        ("router.delete('/items/:id', handler);", "route_definition"),
        ("require('axios')", "network_call"),
        ("import got from 'got';", "network_call"),
        ("const client = new XMLHttpRequest();", "network_call"),
        ("const es = new EventSource('/stream');", "network_call"),
        ("const server = createServer(handler);", "route_definition"),
    ],
)
def test_node_patterns_positive(line: str, expected_category: str) -> None:
    matched = [p for p in NODE_PATTERNS if re.search(p["pattern"], line)]
    categories = [p["category"] for p in matched]
    assert expected_category in categories, (
        f"Expected category {expected_category!r} not matched in {line!r}\nGot: {categories}"
    )


@pytest.mark.parametrize(
    "line",
    [
        "export function formatDate(d: Date): string { return d.toISOString(); }",
        "const PI = 3.14159;",
        "type UserId = string;",
    ],
)
def test_node_patterns_no_false_positive(line: str) -> None:
    matched = [p for p in NODE_PATTERNS if re.search(p["pattern"], line)]
    assert not matched, f"Unexpected match for: {line!r} — matched: {matched}"


@pytest.mark.parametrize(
    "line,expected_category",
    [
        ("import requests", "network_call"),
        ("from requests import Session", "network_call"),
        ("import httpx", "network_call"),
        ("from httpx import AsyncClient", "network_call"),
        ("import aiohttp", "network_call"),
        ("import boto3", "network_call"),
        ("@app.get('/health')", "route_definition"),
        ("@router.post('/items')", "route_definition"),
        ("@blueprint.delete('/items/<int:item_id>')", "route_definition"),
        ("import openai", "network_call"),
        ("import anthropic", "network_call"),
        ("from urllib.request import urlopen", "network_call"),
        ("import urllib", "network_call"),
        ("import http.client", "network_call"),
        ("@app.route('/submit')", "route_definition"),
    ],
)
def test_python_patterns_positive(line: str, expected_category: str) -> None:
    matched = [p for p in PYTHON_PATTERNS if re.search(p["pattern"], line)]
    categories = [p["category"] for p in matched]
    assert expected_category in categories, (
        f"Expected {expected_category!r} not matched in {line!r}\nGot: {categories}"
    )


@pytest.mark.parametrize(
    "line",
    [
        "def slugify(text: str) -> str:",
        "return text.lower().replace(' ', '-')",
        "PI = 3.14159",
    ],
)
def test_python_patterns_no_false_positive(line: str) -> None:
    matched = [p for p in PYTHON_PATTERNS if re.search(p["pattern"], line)]
    assert not matched, f"Unexpected match for: {line!r}"


@pytest.mark.parametrize(
    "line,expected_category",
    [
        ("EXPOSE 8080", "devops"),
        ("    ports:", "devops"),
        ("ENV API_URL=https://api.example.com", "devops"),
        ("    ENV HOST=localhost", "devops"),
        ("  curl https://example.com/health", "devops"),
        ("  wget https://example.com/file.tar.gz", "devops"),
        ("ingress:", "devops"),
        ("  LoadBalancer", "devops"),
    ],
)
def test_devops_patterns_positive(line: str, expected_category: str) -> None:
    matched = [p for p in DEVOPS_PATTERNS if re.search(p["pattern"], line)]
    categories = [p["category"] for p in matched]
    assert expected_category in categories, (
        f"Expected {expected_category!r} not matched in {line!r}\nGot: {categories}"
    )


@pytest.mark.parametrize(
    "line",
    [
        "transports: []",  # should NOT match ports:
        "supported_ports: [443]",  # should NOT match ports:
        "import sys",  # should NOT match devops patterns
    ],
)
def test_devops_patterns_no_false_positive(line: str) -> None:
    matched = [p for p in DEVOPS_PATTERNS if re.search(p["pattern"], line)]
    assert not matched, f"Unexpected devops match for: {line!r} — matched: {matched}"


def test_all_patterns_contains_all_stacks() -> None:
    stacks = {p["stack"] for p in ALL_PATTERNS}
    assert stacks == {"node", "python", "devops"}


def test_each_pattern_has_required_keys() -> None:
    for p in ALL_PATTERNS:
        assert "pattern" in p
        assert "category" in p
        assert "stack" in p
        assert p["category"] in ("route_definition", "network_call", "devops")
        assert p["stack"] in ("node", "python", "devops")
