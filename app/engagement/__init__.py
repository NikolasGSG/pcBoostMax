"""Engagement features — achievements, streaks, share cards.

These don't change the user's PC. They drive return visits and social
sharing, which is how an ads-only app earns enough to stay free.
"""
from .achievements import (
    Achievement,
    AchievementService,
    DEFAULT_ACHIEVEMENTS,
)
from .share_cards import (
    render_boost_card,
    render_cleanup_card,
    render_fps_card,
)
from .streaks import StreakService

__all__ = [
    "Achievement",
    "AchievementService",
    "DEFAULT_ACHIEVEMENTS",
    "StreakService",
    "render_boost_card",
    "render_cleanup_card",
    "render_fps_card",
]
