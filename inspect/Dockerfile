FROM node:18-bullseye-slim

ENV NODE_ENV=production
WORKDIR /app

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN npm install --omit=dev csgofloat \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["node", "node_modules/csgofloat/index.js"]
