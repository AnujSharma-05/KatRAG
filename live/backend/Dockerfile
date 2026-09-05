# Builder Stage
FROM golang:1.22-bookworm AS builder

# Enable CGO for confluent-kafka-go
ENV CGO_ENABLED=1

WORKDIR /app

# Copy go mod and sum files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build the Go API Gateway binary
RUN go build -o api-gateway ./cmd/api/main.go

# Runner Stage
FROM debian:bookworm-slim

# Install ca-certificates for TLS/SSL
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the compiled binary from the builder stage
COPY --from=builder /app/api-gateway .

# Expose port 8080
EXPOSE 8080

# Run the binary
CMD ["./api-gateway"]
