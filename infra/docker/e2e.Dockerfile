# Dev-only Playwright runner. The image tag MUST match @playwright/test in
# apps/e2e/package.json (browser binaries are version-locked).
FROM mcr.microsoft.com/playwright:v1.49.0-jammy
WORKDIR /e2e
COPY apps/e2e/package.json ./
RUN npm install
COPY apps/e2e/ ./
CMD ["npx", "playwright", "test"]
