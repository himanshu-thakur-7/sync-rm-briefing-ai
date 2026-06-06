FROM node:22-slim AS build

WORKDIR /app
RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY lib ./lib
COPY artifacts/sync-dashboard ./artifacts/sync-dashboard

RUN pnpm install --frozen-lockfile
RUN PORT=3000 BASE_PATH=/ pnpm --filter @workspace/sync-dashboard build

FROM node:22-slim

WORKDIR /app
RUN npm install -g serve

COPY --from=build /app/artifacts/sync-dashboard/dist/public ./public

EXPOSE 3000
CMD ["serve", "-s", "public", "-l", "3000"]
