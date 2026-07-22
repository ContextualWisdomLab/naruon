#!/bin/bash
git checkout frontend/package.json
git checkout frontend/pnpm-lock.yaml

cat << 'YAML' > pnpm-workspace.yaml
packages:
  - 'frontend'
  - 'backend'
  - 'tests'

overrides:
  sharp: 0.34.4
YAML

cat << 'JSON' > package.json
{
  "name": "naruon",
  "version": "0.14.4",
  "private": true,
  "packageManager": "pnpm@11.5.3"
}
JSON

rm pnpm-lock.yaml || true
pnpm install
