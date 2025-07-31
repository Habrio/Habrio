from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from models import db


def init_tracing(app):
    """Initialize OpenTelemetry tracing for the Flask app."""
    service_name = app.config.get("OTEL_SERVICE_NAME", "habrio-backend")
    endpoint = app.config.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if app.config.get("TESTING"):
        processor = BatchSpanProcessor(ConsoleSpanExporter())
    else:
        processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    set_global_textmap(TraceContextTextMapPropagator())

    FlaskInstrumentor().instrument_app(app)
    RequestsInstrumentor().instrument()
    with app.app_context():
        SQLAlchemyInstrumentor().instrument(engine=db.engine)


