# ─── Nalarbanjir UI — Angular 20 frontend ────────────────────────────────
# Multi-stage:
#   builder  — npm install + ng build --configuration=production
#   runtime  — nginx:alpine serving the compiled bundle

# ── Stage 1: Angular build ────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Cache npm install layer
COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps

# Build production bundle
COPY . .
RUN npx ng build --configuration=production


# ── Stage 2: nginx runtime ────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

# Remove default nginx site
RUN rm /etc/nginx/conf.d/default.conf

# Copy Angular bundle
COPY --from=builder /app/dist/nalarbanjir-ui/browser /usr/share/nginx/html

# Copy nginx site config (injected at compose time from project root)
COPY nginx-ui.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
