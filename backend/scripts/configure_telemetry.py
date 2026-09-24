"""Provision the app-wide OTLP credential in the encrypted database registry."""

from __future__ import annotations

import argparse
import asyncio
import sys

async def configure(*, receiver: str | None, environment: str | None,
                    ca_file: str | None, token: str | None, disable: bool) -> None:
    """Store a validated credential or disable the configured receiver."""
    if not disable:
        from cwl_telemetry import TelemetryConfig

        TelemetryConfig(
            service="naruon-backend", version="0.1.0", environment=environment,
            source_revision="0" * 40, receiver=receiver, token=token, ca_file=ca_file,
        )
    from db.models import TelemetryDeploymentConfig
    from db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        row = await session.get(TelemetryDeploymentConfig, 1)
        if disable:
            if row is not None:
                row.enabled = False
        elif row is None:
            session.add(TelemetryDeploymentConfig(
                id=1, receiver=receiver, bearer_token=token,
                environment=environment, ca_file=ca_file, enabled=True,
            ))
        else:
            row.receiver = receiver
            row.bearer_token = token
            row.environment = environment
            row.ca_file = ca_file
            row.enabled = True
        await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receiver", help="HTTPS Collector origin")
    parser.add_argument("--environment", help="bounded deployment environment name")
    parser.add_argument("--ca-file", help="optional mounted CA certificate")
    parser.add_argument("--disable", action="store_true")
    args = parser.parse_args()
    if not args.disable and (not args.receiver or not args.environment):
        parser.error("--receiver and --environment are required to enable telemetry")
    token = None if args.disable else sys.stdin.readline(4097).rstrip("\n")
    try:
        asyncio.run(configure(
            receiver=args.receiver, environment=args.environment,
            ca_file=args.ca_file, token=token, disable=args.disable,
        ))
    except Exception:
        raise SystemExit("Telemetry provisioning failed; check configuration and registry access") from None


if __name__ == "__main__":
    main()
