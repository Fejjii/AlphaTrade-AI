# Production frontend image for Docker Compose.
# Browser calls the API at NEXT_PUBLIC_API_URL (host-reachable URL).

FROM node:20-alpine AS builder

WORKDIR /app

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_APP_NAME=AlphaTrade AI
ARG NEXT_PUBLIC_EXECUTION_MODE=paper
ARG NEXT_PUBLIC_PROVIDER_MODE=mock
ARG NEXT_PUBLIC_AUTH_COOKIE_MODE=false

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_APP_NAME=$NEXT_PUBLIC_APP_NAME \
    NEXT_PUBLIC_EXECUTION_MODE=$NEXT_PUBLIC_EXECUTION_MODE \
    NEXT_PUBLIC_PROVIDER_MODE=$NEXT_PUBLIC_PROVIDER_MODE \
    NEXT_PUBLIC_AUTH_COOKIE_MODE=$NEXT_PUBLIC_AUTH_COOKIE_MODE

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build


FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN apk add --no-cache curl \
    && addgroup --system --gid 1001 nextjs \
    && adduser --system --uid 1001 --ingroup nextjs nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/login" >/dev/null || exit 1

CMD ["node", "server.js"]
