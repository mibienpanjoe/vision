FROM node:24.12.0-bookworm-slim@sha256:7326fb2dbdce998edd72140946851be64ef4a643e8715e138ca467e8e9d92c99
RUN corepack enable && corepack prepare pnpm@10.28.0 --activate
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
COPY packages/contracts/package.json packages/contracts/
RUN pnpm install --frozen-lockfile --ignore-scripts --filter @vision/web...
COPY packages/contracts packages/contracts
COPY assets/brand assets/brand
COPY assets/illustrations assets/illustrations
COPY apps/web apps/web
# The proxy destination is fixed at build time: the compose `api` service on the stack's private network.
ARG VISION_API_ORIGIN=http://api:8000
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm --dir apps/web build && chown -R node /repo/apps/web/.next
ARG VISION_REVISION=unknown
LABEL org.opencontainers.image.revision=$VISION_REVISION
USER node
WORKDIR /repo/apps/web
# All interfaces inside the container; compose publishes the port on host loopback only. No package manager
# runs at start, so nothing is downloaded.
CMD ["./node_modules/.bin/next", "start", "--hostname", "0.0.0.0", "--port", "3000"]
