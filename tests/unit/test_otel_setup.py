"""Unit tests for optional OTEL setup (disabled / missing packages)."""

from unittest.mock import MagicMock, patch

import pytest

from utils.otel import current_trace_id, setup_otel


@pytest.mark.unit
def test_setup_otel_noop_when_disabled():
    app = MagicMock()
    with patch("utils.otel.settings.otel.enabled", False):
        assert setup_otel(app) is False


@pytest.mark.unit
def test_setup_otel_false_when_import_fails():
    app = MagicMock()
    with patch("utils.otel.settings.otel.enabled", True):
        with patch.dict(
            "sys.modules",
            {
                "opentelemetry": None,
                "opentelemetry.trace": None,
                "opentelemetry.sdk.resources": None,
                "opentelemetry.sdk.trace": None,
                "opentelemetry.sdk.trace.export": None,
                "opentelemetry.instrumentation.fastapi": None,
            },
        ):
            # Re-import path: patch the names used inside setup_otel
            import builtins

            real_import = builtins.__import__

            def _import(name, globals=None, locals=None, fromlist=(), level=0):
                if name == "opentelemetry" or name.startswith("opentelemetry."):
                    raise ImportError("otel not installed")
                return real_import(name, globals, locals, fromlist, level)

            with patch("builtins.__import__", side_effect=_import):
                assert setup_otel(app) is False


@pytest.mark.unit
def test_current_trace_id_safe_without_sdk():
    # Should not raise when OTEL is absent
    tid = current_trace_id()
    assert tid is None or isinstance(tid, str)
