"""
Root-pytest-konfiguration.

Springer automatisk tests over, der afhænger af miljøer, vi endnu ikke
har i CI:

- Windows-specifikke, native moduler (`pywin32`, `pyaudiowpatch`).
- Det eksterne `spark_core`-/`leverance.core`-framework beskrevet i
  PROGRESS.md.
- Tests der kræver tunge, valgfrie afhængigheder (fx `nltk`), der endnu
  ikke er i dev-gruppen.

Vi bruger `pytest_ignore_collect` frem for at markere indsamlede items,
så moduler, der fejler ved *import*, også springes rent over.

Når afhængighederne bliver tilgængelige, bliver disse predikater no-ops.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()


def _available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


WINDOWS = sys.platform.startswith("win")
HAS_SPARK_CORE = _available("spark_core")
HAS_LEVERANCE_CORE = _available("leverance.core")
HAS_NLTK = _available("nltk")
HAS_WIN32 = _available("win32gui")


def pytest_ignore_collect(collection_path, config):  # type: ignore[override]
    path = Path(str(collection_path)).resolve()
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return False

    parts = rel.parts
    name = rel.name

    # audio_streamer-tests kræver pywin32 — springes over uden for Windows.
    if parts[:1] == ("tests",) and "audio_streamer" in name and not HAS_WIN32:
        return True

    # End-to-end-tests kræver Azure-credentials og netværk.
    if "end_to_end_and_load_test" in parts:
        return True

    # Leverance business component-tests kræver det eksterne framework.
    if parts[:1] == ("leverance",) and name.startswith("_test_"):
        if not (HAS_SPARK_CORE and HAS_LEVERANCE_CORE):
            return True
        # Text processor-testen kræver nltk.
        if "text_processor" in name and not HAS_NLTK:
            return True

    return False
