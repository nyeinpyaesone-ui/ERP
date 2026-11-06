# node:20 is EOL (April 2026) and its runtime advisories are what Trivy
# flags in the image; node 24 matches the version local dev and CI build
# with (v24.21.0), so the image stops drifting from the test environment.
FROM node:26-alpine AS builder

WORKDIR /app
# Copy the lockfile alongside the manifest so `npm ci` installs exactly the
# versions CI resolves. The previous `COPY package.json .` + `npm install`
# resolved fresh from the registry, so image contents could drift from the
# lockfile that backend/frontend-react/package-lock.json pins.
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

