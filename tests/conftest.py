"""Pytest configuration — makes ``custom_components`` importable.

These tests exercise the parts of the integration that have no Home
Assistant *runtime* dependency (data models, validators, manager state).
They DO need ``pycryptodome`` (the integration imports it eagerly) and
the ``homeassistant`` core (for SettingsManager's dispatcher import).
Both are listed in requirements_test.txt; CI installs them.

Individual test modules call ``pytest.importorskip`` so a bare dev
sandbox without those deps gets clean skips, not collection errors.
"""
from __future__ import annotations

import os
import sys

# Make ``custom_components.bytewatt`` importable from the repo root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
