"""Smoke-tests — hurtige tjek af, at alle pakker kan importeres, og at
de symboler, vores CI-workflow forudsætter, faktisk eksisterer.

Disse erstatter de deaktiverede `_test_*.py`- og Windows-specifikke
tests, indtil det eksterne `spark_core`-/`leverance.core`-framework er
tilgængeligt lokalt (se PROGRESS.md).
"""

from __future__ import annotations

import importlib
import sys

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "aiservice",
        "aiservice.openai_assistant",
        "aiservice.authentication",
        "aiservice.core_functions",
    ],
)
def test_aiservice_modules_import(module: str) -> None:
    """Alle aiservice-moduler skal kunne importeres rent på alle platforme."""
    assert importlib.import_module(module) is not None


def test_openai_assistant_has_expected_api() -> None:
    from aiservice.openai_assistant import OpenAIAssistant

    assert callable(OpenAIAssistant)


@pytest.mark.skipif(
    not sys.platform.startswith("win"),
    reason="audio_streamer trækker pywin32 ind, som kun findes på Windows",
)
def test_audio_streamer_imports_on_windows() -> None:
    """På Windows skal audio_streamer-pakken kunne importeres rent."""
    import audio_streamer.streamer
    import audio_streamer.tray_icon  # noqa: F401
