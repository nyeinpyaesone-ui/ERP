# =============================================================================
# ERP SOLUTION - Frontend Dockerfile (Multi-stage, Production-Ready)
# =============================================================================

# Stage 1: Dependencies
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --only=production

# Stage 2: Builder
FROM node:20-alpine AS builder
WORKDIR /app

# Install build dependencies
RUN apk add --no-cache git

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY . .

# Set environment variables
ENV NODE_ENV=production
ENV GENERATE_SOURCEMAP=false

# Build the application
RUN npm run build

# Stage 3: Production (Nginx)
FROM nginx:alpine AS production

# Install security updates
RUN apk update && apk upgrade --no-cache

# Create non-root user
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder stage
COPY --from=builder --chown=appuser:appgroup /app/dist /usr/share/nginx/html

# Add health check endpoint
RUN echo '<!DOCTYPE html><html><body>OK</body></html>' > /usr/share/nginx/html/health.html

# Set proper permissions
RUN chown -R appuser:appgroup /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html && \
    chown -R appuser:appgroup /var/cache/nginx && \
    chown -R appuser:appgroup /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R appuser:appgroup /var/run/nginx.pid

USER appuser

EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/health.html || exit 1

# Labels for container metadata
LABEL maintainer="ERP Solution Team" \
      version="v3.0.0" \
      description="ERP Solution Frontend Application" \
      org.opencontainers.image.source="https://github.com/powerrangeranikg/erp-solution" \
      org.opencontainers.image.title="ERP Solution Frontend" \
      org.opencontainers.image.vendor="ERP Solution"

CMD ["nginx", "-g", "daemon off;"]
