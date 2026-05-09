#!/usr/bin/env bash
# Container entrypoint: wires gh CLI auth into git's credential helper at
# every container start, then execs the requested command.
#
# Why this runs every start (not once at build): `gh auth setup-git` writes
# /root/.gitconfig, which is ephemeral in `docker compose run --rm` containers
# and would otherwise be lost. The hsb-gh-auth named volume persists the gh
# token (/root/.config/gh/hosts.yml); this script re-derives the gitconfig
# helper from that token on each start. Idempotent.

set -e

if gh auth status --hostname github.com >/dev/null 2>&1; then
  gh auth setup-git --hostname github.com 2>/dev/null || true
fi

exec "$@"
