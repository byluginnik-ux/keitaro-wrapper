FROM node:22-bookworm-slim AS build
RUN corepack enable
WORKDIR /srv
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile --ignore-scripts
COPY . .
RUN pnpm rebuild esbuild && pnpm nuxt prepare && pnpm build

FROM node:22-bookworm-slim
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
WORKDIR /srv
COPY --from=build /srv/.output ./.output
USER node
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
