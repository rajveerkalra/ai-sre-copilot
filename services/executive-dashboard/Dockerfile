# Build
FROM node:22-alpine AS build
WORKDIR /app
COPY services/executive-dashboard/package.json ./
RUN npm install
COPY services/executive-dashboard/ ./
RUN npm run build

# Serve
FROM nginx:1.27-alpine
COPY services/executive-dashboard/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8050
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD wget -qO- http://127.0.0.1:8050/health || exit 1
