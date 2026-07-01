# Dev stage
FROM golang:1.22-alpine AS dev
WORKDIR /app
RUN go install github.com/air-verse/air@v1.52.2
COPY go.mod go.sum ./
RUN go mod download
CMD ["air", "--cmd", "go run ./cmd/server", "--", "-d"]

# Production stage
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go mod tidy
RUN CGO_ENABLED=0 GOOS=linux go build -o main ./cmd/server
EXPOSE 8080
CMD ["./main"]
