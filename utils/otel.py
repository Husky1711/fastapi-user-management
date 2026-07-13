"""
Optional OpenTelemetry instrumentation.

Enable with OTEL__ENABLED=true and:
  pip install -r requirements-otel.txt

Does nothing when disabled or when OTEL packages are not installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from config.settings import settings

if TYPE_CHECKING:
    from fastapi import FastAPI


def setup_otel(app: "FastAPI") -> bool:
    """Instrument the FastAPI app. Returns True if instrumentation attached."""
    if not settings.otel.enabled:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        from utils.loggers import app_logger

        app_logger.warning(
            "OTEL__ENABLED=true but OpenTelemetry packages missing; "
            "install requirements-otel.txt",
            event_type="otel_import_missing",
        )
        return False

    resource = Resource.create({"service.name": settings.otel.service_name})
    provider = TracerProvider(resource=resource)

    endpoint = (
        settings.otel.exporter_otlp_endpoint
        or __import__("os").getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    )
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        except Exception as exc:  # noqa: BLE001
            from utils.loggers import app_logger

            app_logger.warning(
                f"OTLP exporter not configured: {exc}",
                error=str(exc),
                event_type="otel_exporter_unavailable",
            )

    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)

    from utils.loggers import app_logger

    app_logger.info(
        "OpenTelemetry FastAPI instrumentation enabled",
        service_name=settings.otel.service_name,
        event_type="otel_enabled",
    )
    return True


def current_trace_id() -> str | None:
    """Return the active W3C trace id hex, if any."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx and ctx.is_valid:
            return format(ctx.trace_id, "032x")
    except Exception:
        return None
    return None
