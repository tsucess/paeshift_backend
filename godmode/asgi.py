"""
ASGI config for godmode FastAPI app.
"""

import os

from django.core.asgi import get_asgi_application
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware

from .fastapi_app import app as fastapi_app

# Set up Django ASGI application
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "payshift.settings")
django_asgi_app = get_asgi_application()

# Create the main FastAPI application
app = FastAPI()

# Mount the FastAPI app
app.mount("/api", fastapi_app)

# Mount Django for the rest
app.mount("/", WSGIMiddleware(django_asgi_app))
