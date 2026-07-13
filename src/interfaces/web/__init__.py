"""Web transport adapter."""

from .server import WebDependencies, create_web_app, start_web_server

__all__ = ["WebDependencies", "create_web_app", "start_web_server"]
