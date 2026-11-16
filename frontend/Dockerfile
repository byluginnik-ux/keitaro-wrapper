# Build context is the repository root: the frontend depends on ../contracts.
FROM node:22-bookworm-slim AS build
RUN corepack enable
COPY contracts /srv/contracts
WORKDIR /srv/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile --ignore-scripts
COPY frontend .
RUN pnpm rebuild esbuild && pnpm nuxt prepare && pnpm build

FROM node:22-bookworm-slim
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
WORKDIR /srv
COPY --from=build /srv/frontend/.output ./.output
USER node
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
