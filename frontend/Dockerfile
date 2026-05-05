# frontend/Dockerfile

# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# VITE_API_URL is injected at build time via GitHub Actions secret/variable
# e.g. http://ec2-xx-xx-xx-xx.ap-south-1.compute.amazonaws.com
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ── Stage 2: Serve ────────────────────────────────────────────────────────────
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx config to handle React Router (all routes → index.html)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]