FROM node:22.17.0-alpine

WORKDIR /app
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run typecheck && npm run build \
    && chown -R node:node /app

USER node
EXPOSE 3000
CMD ["npm", "start"]
