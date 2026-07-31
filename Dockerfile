# ---- Stage 1: Install dependencies ----
FROM node:20-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# ---- Stage 2: Build the Next.js application ----
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ---- Stage 3: Production runtime ----
FROM node:20-alpine AS runner

RUN addgroup --system nodejs && adduser --system --no-create-home nextjs --ingroup nodejs

WORKDIR /app

# Copy only the production artifacts
COPY --from=deps   /app/node_modules ./node_modules
COPY --from=builder /app/.next          ./.next
COPY --from=builder /app/public         ./public
COPY --from=builder /app/package.json   ./package.json
COPY --from=builder /app/next.config.ts ./next.config.ts

# Next.js reads these at build time via next.config.ts; runtime env vars
# prefixed NEXT_PUBLIC_ are inlined at build time, so pass them during build.
# For non-NEXT_PUBLIC_ vars set them at container start.

USER nextjs
EXPOSE 3000

ENV NODE_ENV=production
CMD ["npx", "next", "start", "--port", "3000"]