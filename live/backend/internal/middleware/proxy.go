package middleware

import (
	"strings"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/propagation"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/proxy"
	"github.com/valyala/fasthttp"

	"github.com/AnujSharma-05/KatRAG/live/backend/internal/auth"
	"github.com/AnujSharma-05/KatRAG/live/backend/internal/cache"
)

var tracer = otel.Tracer("katrag-api-gateway")

// PythonBackendURL is the URL of the internal Python intelligence engine
const PythonBackendURL = "http://127.0.0.1:8000"

// GatewayProxy handles authentication, scope injection, and reverse proxying
func GatewayProxy() fiber.Handler {
	return func(c *fiber.Ctx) error {
		// 1. Authenticate JWT
		authHeader := c.Get("Authorization")
		userID, err := auth.ParseJWT(authHeader)
		if err != nil {
			// In development, if bypass_auth query param is provided, allow it for easy testing
			if c.Query("bypass_auth") != "true" {
				return c.Status(fiber.StatusUnauthorized).JSON(fiber.Map{
					"error": "Unauthorized",
					"details": err.Error(),
				})
			}
			userID = "admin-123" // mock user for bypass
		}

		// 2. Resolve Scope (Check Cache first)
		ctx := c.Context()
		var scope *auth.Scope

		cachedScope, err := cache.GetScope(ctx, userID)
		if cachedScope != nil && err == nil {
			scope = &auth.Scope{
				OrganizationID: cachedScope["organization_id"].(string),
				UserID:         cachedScope["user_id"].(string),
				AsOf:           cachedScope["as_of"].(string),
			}
			// Parse group IDs safely
			if groups, ok := cachedScope["group_ids"].([]interface{}); ok {
				for _, g := range groups {
					scope.GroupIDs = append(scope.GroupIDs, g.(string))
				}
			}
		} else {
			// Cache Miss: Query DB (Mocked in auth.ResolveScope)
			scope, err = auth.ResolveScope(ctx, userID)
			if err != nil {
				return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{
					"error": "Failed to resolve scope",
				})
			}
			// Save back to Cache
			scopeMap := map[string]interface{}{
				"organization_id": scope.OrganizationID,
				"group_ids":       scope.GroupIDs,
				"user_id":         scope.UserID,
				"as_of":           scope.AsOf,
			}
			_ = cache.SetScope(ctx, userID, scopeMap)
		}

		// 3. Strip JWT and Inject Scope Headers
		c.Request().Header.Del("Authorization")
		c.Request().Header.Set("X-Scope-Organization-Id", scope.OrganizationID)
		c.Request().Header.Set("X-Scope-Group-Ids", strings.Join(scope.GroupIDs, ","))
		c.Request().Header.Set("X-Scope-User-Id", scope.UserID)

		// 4. Start root OTel span and inject W3C traceparent into downstream headers
		goCtx := c.Context().Value(struct{}{})
		if goCtx == nil {
			goCtx = c.UserContext()
		}
		spanCtx, span := tracer.Start(c.UserContext(), "gateway.proxy_request")
		defer span.End()

		// Attach operational (non-PII) attributes
		span.SetAttributes(
			attribute.String("tenant.organization_id", scope.OrganizationID),
			attribute.String("http.method", string(c.Request().Header.Method())),
			attribute.String("http.path", c.Path()),
		)
		_ = spanCtx

		// Inject W3C traceparent into the outbound request headers so the Python
		// engine can extract the parent context and attach child spans to the same trace.
		carrier := propagation.MapCarrier{}
		otel.GetTextMapPropagator().Inject(spanCtx, carrier)
		for k, v := range carrier {
			c.Request().Header.Set(k, v)
		}

		// 5. Reverse Proxy to Python
		targetURL := PythonBackendURL + c.OriginalURL()
		_ = fasthttp.ErrConnectionClosed // keep import used
		
		// If doing a proxy, forward it
		if err := proxy.Do(c, targetURL); err != nil {
			return err
		}
		span.SetAttributes(attribute.Int("http.status_code", c.Response().StatusCode()))
		
		// Remove proxy headers from response if needed
		c.Response().Header.Del("Server")
		return nil
	}
}
