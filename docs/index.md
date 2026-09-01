# Naruon

Naruon is an AI email workspace that connects mail, attachments, calendars, tasks, and customer-owned file systems into a single context-aware place for judgment and action.

[Ask DeepWiki](https://deepwiki.com/ContextualWisdomLab/naruon) · [Repository](https://github.com/ContextualWisdomLab/naruon) · [Releases](https://github.com/ContextualWisdomLab/naruon/releases)

## Start here

- [README and five-minute local path](../README.md)
- [Architecture](architecture/)
- [Architecture decisions](adr/README.md)
- [Topic-intelligence documentation](topic-intelligence/README.md)
- [Contributing](../CONTRIBUTING.md)
- [Security policy](../SECURITY.md)

## Product boundary

Naruon is a workspace and control plane, not a replacement mail, calendar, contact, or file server. Customer-owned providers remain authoritative. Naruon adds bounded metadata, indexing, preferences, provenance, auditable action intent, and policy-aware orchestration around those systems.

The product combines a FastAPI backend and Next.js frontend with vector search, AI-assisted summaries, hardened email threading, and relay/proxy contracts for external mail, CalDAV/CardDAV, and WebDAV systems. Provider writes are explicit and capability-aware rather than silently assumed.

## Architecture at a glance

The repository keeps product boundaries and technical decisions in versioned documentation. Start with the [architecture directory](architecture/) for system structure and the [ADR index](adr/README.md) for durable decisions. The README records the current north-star scope and the local development path.

## Releases

Published releases are the source of truth for versioned delivery evidence. The latest published release is available from the repository's [Releases](https://github.com/ContextualWisdomLab/naruon/releases) page; development continues on the protected `develop` branch under the repository's required checks and review policy.

## Documentation status

This page is intentionally a small public landing surface. Detailed operational, security, architecture, and product contracts remain in the repository so they evolve with the code and can be reviewed through the same governance path.
