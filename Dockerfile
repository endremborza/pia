# papercli deployment image: FastAPI + static SPA in one container, with the
# full agent toolchain (tectonic, claude) sandboxed inside it. All Python deps
# come from PyPI (hallubib, paritex included) — the repo is the whole context.
#
# All state lives under /data (volume): papers, claude auth, tectonic cache —
# `docker compose down && up` keeps everything; only `down -v` destroys it.
# Authenticate claude once after first start:  docker compose exec -it papercli claude
# Public deploys: set PAPERCLI_PASSWORD in .env to gate the app with HTTP Basic.

FROM node:24-slim AS frontend
WORKDIR /fe
COPY package.json package-lock.json ./
RUN npm ci
COPY vite.config.ts tsconfig.json svelte.config.js ./
COPY static ./static
COPY src ./src
RUN npm run build


FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl fontconfig git unzip \
    && rm -rf /var/lib/apt/lists/*

# tectonic: static musl binary, wrapped so *every* invocation — paritex's and the
# agent's own `tectonic main.tex` — also searches /opt/texmf-extra.
ARG TECTONIC_VERSION=0.15.0
RUN mkdir -p /usr/local/libexec \
    && curl -fsSL "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
    | tar -xz -C /usr/local/libexec \
    && printf '#!/bin/sh\nexec /usr/local/libexec/tectonic -Z search-path=/opt/texmf-extra "$@"\n' > /usr/local/bin/tectonic \
    && chmod +x /usr/local/bin/tectonic

# Classes outside tectonic's bundle that real papers use (Springer LNCS).
RUN curl -fsSL -o /tmp/llncs.zip https://mirrors.ctan.org/macros/latex/contrib/llncs.zip \
    && unzip -j /tmp/llncs.zip 'llncs/*.cls' 'llncs/*.bst' -d /opt/texmf-extra \
    && rm /tmp/llncs.zip

RUN useradd -m app && mkdir -p /data && chown app:app /data

# Config baked into the image; /data is the single stateful mount.
RUN mkdir -p /etc/papercli \
    && printf 'projects_root = "/data/projects"\n' > /etc/papercli/config.toml
ENV PAPERCLI_CONFIG=/etc/papercli/config.toml \
    CLAUDE_CONFIG_DIR=/data/claude \
    XDG_CACHE_HOME=/data/cache \
    PATH="/home/app/.local/bin:$PATH"

USER app

# claude CLI (native installer, no node needed at runtime); login state lives in
# CLAUDE_CONFIG_DIR on the volume, so authenticating once survives image updates.
# The installer takes stable|latest|X.Y.Z; `stable` by default, set an exact
# version to make a rebuild reproducible.
ARG CLAUDE_VERSION=stable
RUN curl -fsSL https://claude.ai/install.sh | bash -s -- "${CLAUDE_VERSION}"

WORKDIR /app

# Dependencies resolve from the lockfile alone, so they cache across source edits.
COPY --chown=app:app pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --extra server --no-dev --no-install-project

COPY --chown=app:app . .
RUN uv sync --frozen --extra server --no-dev

COPY --chown=app:app --from=frontend /fe/build ./build

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD curl -fs http://127.0.0.1:8000/api/health || exit 1
CMD [".venv/bin/papercli", "serve", "--host", "0.0.0.0", "--port", "8000", "--static", "build"]
