"""Pytest-Konfiguration: fuegt das Projekt-Root zum Python-Pfad hinzu."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
