# syntax=docker/dockerfile:1
###############################################################################
# ERP SOLUTION — frontend image (static Vite build served by nginx)
#
# The build stage is architecture-aware; the final image contains only the
# generated static bundle and nginx. Upgrade Alpine packages in the final
# stage so security fixes released after the upstream base image are included.
###############################################################################
FROM node:22-alpine3.24 AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:stable-alpine3.24

RUN apk update \
    && apk upgrade --no-cache \
    && rm -rf /var/cache/apk/*

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
