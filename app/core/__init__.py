"""Core app wiring: controller, event bus, configuration."""
from .event_bus import EventBus
from .app_controller import AppController

__all__ = ["EventBus", "AppController"]
