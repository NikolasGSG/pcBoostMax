"""Pure-function analyzers — turn raw monitoring data into findings.

These don't run their own threads. They subscribe to event-bus topics
(``"monitor.sample"``, ``"fps.sample"``, etc.) or take snapshots of the
existing services on demand. That keeps the cost low and makes them
easy to unit-test.
"""
from .anomaly_detector import AnomalyAlert, AnomalyDetector
from .predictive_maintenance import (
    MaintenancePrediction,
    PredictiveMaintenance,
)
from .stutter_detector import StutterDetector, StutterEvent

__all__ = [
    "AnomalyAlert",
    "AnomalyDetector",
    "MaintenancePrediction",
    "PredictiveMaintenance",
    "StutterDetector",
    "StutterEvent",
]
