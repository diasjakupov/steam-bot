FROM node:20-alpine AS base

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY config.js ./config.js
COPY start.js ./start.js

EXPOSE 5000

CMD ["npm", "start"]
