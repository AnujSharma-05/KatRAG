package telemetry

import (
	"context"
	"log"
	"os"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// InitTracer bootstraps the OpenTelemetry OTLP gRPC exporter and registers the
// global TracerProvider. Returns a shutdown function that must be deferred by
// the caller to flush in-flight spans.
// If the exporter cannot connect (Jaeger down), it logs a warning and sets up a
// no-op provider so the service continues without tracing.
func InitTracer(ctx context.Context) (shutdown func(context.Context) error) {
	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		endpoint = "localhost:4317"
	}
	serviceName := os.Getenv("OTEL_SERVICE_NAME")
	if serviceName == "" {
		serviceName = "katrag-api-gateway"
	}

	// Dial with a short timeout so a missing Jaeger does not block startup.
	dialCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	conn, err := grpc.DialContext(
		dialCtx,
		endpoint,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithBlock(),
	)
	if err != nil {
		log.Printf("[OTEL] WARNING: Cannot reach OTLP endpoint %s (%v). Tracing disabled.", endpoint, err)
		// Install a no-op provider — all tracing calls become silent no-ops.
		otel.SetTracerProvider(otel.GetTracerProvider())
		otel.SetTextMapPropagator(propagation.TraceContext{})
		return func(context.Context) error { return nil }
	}

	exporter, err := otlptracegrpc.New(ctx, otlptracegrpc.WithGRPCConn(conn))
	if err != nil {
		log.Printf("[OTEL] WARNING: Failed to create OTLP exporter: %v. Tracing disabled.", err)
		return func(context.Context) error { return nil }
	}

	res := resource.NewWithAttributes(
		semconv.SchemaURL,
		semconv.ServiceNameKey.String(serviceName),
	)

	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(res),
	)

	// Register as the global provider — all otel.Tracer() calls use this.
	otel.SetTracerProvider(tp)
	// W3C TraceContext propagation (traceparent / tracestate headers).
	otel.SetTextMapPropagator(propagation.TraceContext{})

	log.Printf("[OTEL] TracerProvider initialized. Exporting to %s as service '%s'", endpoint, serviceName)

	return tp.Shutdown
}
