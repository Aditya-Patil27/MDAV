FROM node:20-alpine AS dependencies

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder

WORKDIR /app
ARG BACKEND_INTERNAL_URL=http://backend:8000
ENV BACKEND_INTERNAL_URL=${BACKEND_INTERNAL_URL}
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000

COPY --from=dependencies /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/next.config.js ./next.config.js
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000
CMD ["npm", "start"]
