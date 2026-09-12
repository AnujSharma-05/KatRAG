"""
core_backend/src/telemetry.py
─────────────────────────────
Initializes the OpenTelemetry SDK with an OTLP/gRPC exporter pointing at Jaeger
(or any compatible OTLP collector).

Architectural Law: Tracing must be RESILIENT and NON-BLOCKING.
If the collector is unreachable, all tracing calls silently become no-ops.
User queries must never fail due to telemetry infrastructure issues.
"""
import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.trace import NoOpTracerProvider

logger = logging.getLogger(__name__)

_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "katrag-core-engine")
_OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

def _init_otlp_provider() -> None:
    """Attempt to configure the OTLP gRPC exporter. Falls back to NoOp silently."""
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        exporter = OTLPSpanExporter(endpoint=_OTEL_ENDPOINT, insecure=True)

        resource = Resource.create({SERVICE_NAME: _SERVICE_NAME})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        logger.info(f"[OTEL] TracerProvider initialized. Exporting to {_OTEL_ENDPOINT} as '{_SERVICE_NAME}'")
    except Exception as exc:  # pragma: no cover
        # If opentelemetry-exporter-otlp-proto-grpc is not installed or Jaeger is
        # unreachable, fall back to a no-op provider so the service continues normally.
        logger.warning(f"[OTEL] WARNING: OTLP exporter unavailable ({exc}). Tracing disabled (NoOp).")
        trace.set_tracer_provider(NoOpTracerProvider())

# Execute once at module import time.
_init_otlp_provider()

def get_tracer(name: str = "katrag.query_service"):
    """Return a tracer bound to the globally-configured provider."""
    return trace.get_tracer(name)
