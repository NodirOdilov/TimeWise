"""
ASGI config for TimeWise project.

Exposes the ASGI callable as a module-level variable named ``application``.
Supports HTTP and WebSocket connections for real-time timer updates.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_asgi_application()
