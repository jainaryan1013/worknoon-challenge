# Frontend test-runner image — typecheck (tsc) + unit tests (vitest), in Docker.
# Source is bind-mounted by docker-compose.test.yml; an anonymous volume keeps
# the image's node_modules from being shadowed by the mount.
FROM node:20-slim
WORKDIR /app
COPY apps/frontend/package.json ./
RUN npm install
COPY apps/frontend/ ./
CMD ["sh", "-c", "npm run lint && npm test"]
