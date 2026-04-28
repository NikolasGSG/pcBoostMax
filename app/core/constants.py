"""App-wide constants. Centralised so every module agrees."""
from __future__ import annotations

APP_NAME = "GameBoost APEX"
APP_SHORT = "GameBoost"
APP_VERSION = "2.1.2"
ORG_NAME = "GameBoost"

# Monitoring cadence
MONITOR_SAMPLE_HZ = 2            # samples per second
MONITOR_HISTORY_SECONDS = 120    # retain ~2 minutes of rolling data in memory

# Risk levels used by the optimization engine + UI badges.
RISK_SAFE = "safe"
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_ORDER = (RISK_SAFE, RISK_LOW, RISK_MEDIUM, RISK_HIGH)

# Impact score bucket names.
IMPACT_MINOR = "minor"
IMPACT_MODERATE = "moderate"
IMPACT_SIGNIFICANT = "significant"

# Named modes
MODE_SAFE = "safe"
MODE_ADVANCED = "advanced"
