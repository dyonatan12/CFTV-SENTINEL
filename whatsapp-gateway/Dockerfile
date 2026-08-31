FROM node:20-slim

ENV NODE_ENV=production
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

WORKDIR /app

# Instala Chromium e fontes para o Puppeteer
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-freefont-ttf \
    libnss3 \
    libatk-bridge2.0-0 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libgbm1 \
    libasound2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm ci --only=production || npm install --production

COPY . .

RUN mkdir -p /app/.wwebjs_auth /app/.wwebjs_cache

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["node", "server.js"]
