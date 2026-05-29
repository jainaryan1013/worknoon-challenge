# Frontend image — multi-stage build, served by nginx. See docs/components/07-infra.md §4.
FROM node:20-alpine AS build
WORKDIR /app
COPY apps/frontend/package.json ./
RUN npm install
COPY apps/frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY infra/nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
