FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm install --frozen-lockfile 2>/dev/null || npm install
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
# public/ 是 optional，不存在時跳過
RUN mkdir -p ./public
COPY --from=builder /app/public/ ./public/

EXPOSE 3000
ENV HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
