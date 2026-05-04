from __future__ import annotations

from typing import Any

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
    # Node — UI component libraries (not network-capable)
    "@radix-ui/react-accordion": {
        "network_capable": False,
        "import_name": "@radix-ui/react-accordion",
        "category": None,
    },  # noqa: E501
    "@radix-ui/react-alert-dialog": {
        "network_capable": False,
        "import_name": "@radix-ui/react-alert-dialog",
        "category": None,
    },  # noqa: E501
    "@radix-ui/react-checkbox": {
        "network_capable": False,
        "import_name": "@radix-ui/react-checkbox",
        "category": None,
    },  # noqa: E501
    "@radix-ui/react-dialog": {
        "network_capable": False,
        "import_name": "@radix-ui/react-dialog",
        "category": None,
    },  # noqa: E501
    "@radix-ui/react-dropdown-menu": {
        "network_capable": False,
        "import_name": "@radix-ui/react-dropdown-menu",
        "category": None,
    },  # noqa: E501
    "@radix-ui/react-icons": {
        "network_capable": False,
        "import_name": "@radix-ui/react-icons",
        "category": None,
    },  # noqa: E501
    "@radix-ui/react-label": {
        "network_capable": False,
        "import_name": "@radix-ui/react-label",
        "category": None,
    },  # noqa: E501
    "@radix-ui/react-popover": {
        "network_capable": False,
        "import_name": "@radix-ui/react-popover",
        "category": None,
    },  # noqa: E501
    "@radix-ui/react-select": {
        "network_capable": False,
        "import_name": "@radix-ui/react-select",
        "category": None,
    },  # noqa: E501
    "@radix-ui/react-slot": {
        "network_capable": False,
        "import_name": "@radix-ui/react-slot",
        "category": None,
    },  # noqa: E501
    "@radix-ui/react-tabs": {
        "network_capable": False,
        "import_name": "@radix-ui/react-tabs",
        "category": None,
    },  # noqa: E501
    "@radix-ui/react-toast": {
        "network_capable": False,
        "import_name": "@radix-ui/react-toast",
        "category": None,
    },  # noqa: E501
    "@radix-ui/react-toolbar": {
        "network_capable": False,
        "import_name": "@radix-ui/react-toolbar",
        "category": None,
    },  # noqa: E501
    "@radix-ui/react-tooltip": {
        "network_capable": False,
        "import_name": "@radix-ui/react-tooltip",
        "category": None,
    },  # noqa: E501
    "@base-ui/react": {
        "network_capable": False,
        "import_name": "@base-ui/react",
        "category": None,
    },
    "@headlessui/react": {
        "network_capable": False,
        "import_name": "@headlessui/react",
        "category": None,
    },  # noqa: E501
    "@headlessui/vue": {
        "network_capable": False,
        "import_name": "@headlessui/vue",
        "category": None,
    },  # noqa: E501
    "@heroicons/react": {
        "network_capable": False,
        "import_name": "@heroicons/react",
        "category": None,
    },  # noqa: E501
    "shadcn": {"network_capable": False, "import_name": "shadcn", "category": None},
    "lucide-react": {"network_capable": False, "import_name": "lucide-react", "category": None},
    "react-icons": {"network_capable": False, "import_name": "react-icons", "category": None},
    "framer-motion": {"network_capable": False, "import_name": "framer-motion", "category": None},
    "@mui/material": {"network_capable": False, "import_name": "@mui/material", "category": None},
    "@mui/icons-material": {
        "network_capable": False,
        "import_name": "@mui/icons-material",
        "category": None,
    },  # noqa: E501
    "antd": {"network_capable": False, "import_name": "antd", "category": None},
    "sonner": {"network_capable": False, "import_name": "sonner", "category": None},
    "cmdk": {"network_capable": False, "import_name": "cmdk", "category": None},
    # Node — styling / forms / utilities (not network-capable)
    "tailwindcss": {"network_capable": False, "import_name": "tailwindcss", "category": None},
    "@tailwindcss/vite": {
        "network_capable": False,
        "import_name": "@tailwindcss/vite",
        "category": None,
    },  # noqa: E501
    "class-variance-authority": {
        "network_capable": False,
        "import_name": "class-variance-authority",
        "category": None,
    },  # noqa: E501
    "clsx": {"network_capable": False, "import_name": "clsx", "category": None},
    "tailwind-merge": {
        "network_capable": False,
        "import_name": "tailwind-merge",
        "category": None,
    },
    "tw-animate-css": {
        "network_capable": False,
        "import_name": "tw-animate-css",
        "category": None,
    },
    "react-hook-form": {
        "network_capable": False,
        "import_name": "react-hook-form",
        "category": None,
    },  # noqa: E501
    "@hookform/resolvers": {
        "network_capable": False,
        "import_name": "@hookform/resolvers",
        "category": None,
    },  # noqa: E501
    "zod": {"network_capable": False, "import_name": "zod", "category": None},
    "yup": {"network_capable": False, "import_name": "yup", "category": None},
    "react": {"network_capable": False, "import_name": "react", "category": None},
    "react-dom": {"network_capable": False, "import_name": "react-dom", "category": None},
    "react-error-boundary": {
        "network_capable": False,
        "import_name": "react-error-boundary",
        "category": None,
    },  # noqa: E501
    "react-markdown": {
        "network_capable": False,
        "import_name": "react-markdown",
        "category": None,
    },
    "react-day-picker": {
        "network_capable": False,
        "import_name": "react-day-picker",
        "category": None,
    },  # noqa: E501
    "react-force-graph-2d": {
        "network_capable": False,
        "import_name": "react-force-graph-2d",
        "category": None,
    },  # noqa: E501
    "remark-gfm": {"network_capable": False, "import_name": "remark-gfm", "category": None},
    "date-fns": {"network_capable": False, "import_name": "date-fns", "category": None},
    "dayjs": {"network_capable": False, "import_name": "dayjs", "category": None},
    "lodash": {"network_capable": False, "import_name": "lodash", "category": None},
    "zustand": {"network_capable": False, "import_name": "zustand", "category": None},
    "jotai": {"network_capable": False, "import_name": "jotai", "category": None},
    "immer": {"network_capable": False, "import_name": "immer", "category": None},
    "use-debounce": {"network_capable": False, "import_name": "use-debounce", "category": None},
    "uuid": {"network_capable": False, "import_name": "uuid", "category": None},
    "nanoid": {"network_capable": False, "import_name": "nanoid", "category": None},
    "typescript": {"network_capable": False, "import_name": "typescript", "category": None},
    "vite": {"network_capable": False, "import_name": "vite", "category": None},
    "vitest": {"network_capable": False, "import_name": "vitest", "category": None},
    "eslint": {"network_capable": False, "import_name": "eslint", "category": None},
    "prettier": {"network_capable": False, "import_name": "prettier", "category": None},
    # Node — common utilities / middleware (not network-capable)
    "dotenv": {"network_capable": False, "import_name": "dotenv", "category": None},
    "express-session": {
        "network_capable": False,
        "import_name": "express-session",
        "category": None,
    },
    "express-rate-limit": {
        "network_capable": False,
        "import_name": "express-rate-limit",
        "category": None,
    },
    "cookie-parser": {"network_capable": False, "import_name": "cookie-parser", "category": None},
    "cors": {"network_capable": False, "import_name": "cors", "category": None},
    "helmet": {"network_capable": False, "import_name": "helmet", "category": None},
    "morgan": {"network_capable": False, "import_name": "morgan", "category": None},
    "compression": {"network_capable": False, "import_name": "compression", "category": None},
    "bcrypt": {"network_capable": False, "import_name": "bcrypt", "category": None},
    "bcryptjs": {"network_capable": False, "import_name": "bcryptjs", "category": None},
    "jsonwebtoken": {"network_capable": False, "import_name": "jsonwebtoken", "category": None},
    "passport": {"network_capable": False, "import_name": "passport", "category": None},
    "multer": {"network_capable": False, "import_name": "multer", "category": None},
    "@tanstack/react-query-devtools": {  # devtools UI only, no network
        "network_capable": False,
        "import_name": "@tanstack/react-query-devtools",
        "category": None,
    },
    # Node — database clients (network_call — open TCP connections)
    "pg": {"network_capable": True, "import_name": "pg", "category": "network_call"},
    "mysql2": {"network_capable": True, "import_name": "mysql2", "category": "network_call"},
    "mysql": {"network_capable": True, "import_name": "mysql", "category": "network_call"},
    "mongoose": {"network_capable": True, "import_name": "mongoose", "category": "network_call"},
    "sequelize": {"network_capable": True, "import_name": "sequelize", "category": "network_call"},
    "typeorm": {"network_capable": True, "import_name": "typeorm", "category": "network_call"},
    "prisma": {
        "network_capable": True,
        "import_name": "@prisma/client",
        "category": "network_call",
    },
    "@prisma/client": {
        "network_capable": True,
        "import_name": "@prisma/client",
        "category": "network_call",
    },
    "connect-pg-simple": {
        "network_capable": True,
        "import_name": "connect-pg-simple",
        "category": "network_call",
    },
    "drizzle-orm": {
        "network_capable": True,
        "import_name": "drizzle-orm",
        "category": "network_call",
    },
    # Python — database / key-value clients
    "psycopg2": {"network_capable": True, "import_name": "psycopg2", "category": "network_call"},
    "psycopg2-binary": {
        "network_capable": True,
        "import_name": "psycopg2",
        "category": "network_call",
    },
    "psycopg": {"network_capable": True, "import_name": "psycopg", "category": "network_call"},
    "asyncpg": {"network_capable": True, "import_name": "asyncpg", "category": "network_call"},
    "aiomysql": {"network_capable": True, "import_name": "aiomysql", "category": "network_call"},
    "databases": {"network_capable": True, "import_name": "databases", "category": "network_call"},
    "valkey": {"network_capable": True, "import_name": "valkey", "category": "network_call"},
    "py-key-value-aio": {
        "network_capable": True,
        "import_name": "key_value_aio",
        "category": "network_call",
    },
    # Python — not network
    "jsonschema": {"network_capable": False, "import_name": "jsonschema", "category": None},
    "watchfiles": {"network_capable": False, "import_name": "watchfiles", "category": None},
    "python-multipart": {"network_capable": False, "import_name": "multipart", "category": None},
    "python-slugify": {"network_capable": False, "import_name": "slugify", "category": None},
    "python-dateutil": {"network_capable": False, "import_name": "dateutil", "category": None},
    "arrow": {"network_capable": False, "import_name": "arrow", "category": None},
    "marshmallow": {"network_capable": False, "import_name": "marshmallow", "category": None},
    "attrs": {"network_capable": False, "import_name": "attr", "category": None},
    "cattrs": {"network_capable": False, "import_name": "cattr", "category": None},
    "msgspec": {"network_capable": False, "import_name": "msgspec", "category": None},
}

# Prefix-based families — any package matching these prefixes is classified without Claude.
# import_name is derived by replacing hyphens with dots in the package name.
_KNOWN_PREFIXES: list[tuple[str, bool, str | None]] = [
    # (prefix, network_capable, category)
    ("opentelemetry-instrumentation-", True, "telemetry"),
    ("opentelemetry-exporter-", True, "telemetry"),
    ("opentelemetry-semantic-conventions", True, "telemetry"),
    ("opentelemetry-contrib-", True, "telemetry"),
    ("@opentelemetry/instrumentation-", True, "telemetry"),
    ("@opentelemetry/exporter-", True, "telemetry"),
    ("@sentry/", True, "telemetry"),
    ("@aws-sdk/client-", True, "network_call"),
    ("@aws-sdk/lib-", True, "network_call"),
    ("langchain-", True, "network_call"),
]


def lookup_prefix(name: str) -> dict[str, Any] | None:
    """Return a KNOWN_PACKAGES-style entry if name matches a known prefix, else None."""
    lower = name.lower()
    for prefix, network_capable, category in _KNOWN_PREFIXES:
        if lower.startswith(prefix):
            import_name = name.replace("-", ".").replace("/", ".")
            return {
                "network_capable": network_capable,
                "import_name": import_name,
                "category": category,
            }
    return None
