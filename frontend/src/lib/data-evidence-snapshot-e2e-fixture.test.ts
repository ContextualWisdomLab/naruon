import type { Page, Route } from '@playwright/test';
import { describe, expect, it, vi } from 'vitest';

import { mockDashboardApi } from '../../tests/e2e/helpers';

type RouteHandler = (route: Route) => Promise<void>;

describe('mockDashboardApi Data evidence snapshot', () => {
  it('serves a redacted verifier-ready snapshot instead of falling through to 404', async () => {
    let routeHandler: RouteHandler | undefined;
    const page = {
      route: vi.fn(async (_pattern: string, handler: RouteHandler) => {
        routeHandler = handler;
      }),
    } as unknown as Page;

    await mockDashboardApi(page);
    expect(routeHandler).toBeDefined();

    const fulfill = vi.fn(async () => undefined);
    const route = {
      request: () => ({
        url: () => 'https://naruon.test/api/data/quality-surface/evidence-snapshot',
        method: () => 'GET',
      }),
      fulfill,
    } as unknown as Route;

    await routeHandler!(route);

    expect(fulfill).toHaveBeenCalledTimes(1);
    const response = fulfill.mock.calls[0]?.[0] as {
      status?: number;
      contentType?: string;
      body?: string;
    };
    expect(response.status).toBe(200);
    expect(response.contentType).toBe('application/json');

    const body = JSON.parse(response.body ?? '{}') as Record<string, unknown>;
    expect(body.snapshot_version).toBe('data_quality_evidence_snapshot.v1');
    expect(body.digest_algorithm).toBe('sha256');
    expect(body.snapshot_digest).toMatch(/^[0-9a-f]{64}$/u);
    expect(body.privacy_redaction_policy).toMatchObject({
      raw_content_exposed: false,
      stable_identifiers_exposed: false,
      provider_credentials_exposed: false,
    });
    expect(body.validation_status).toMatchObject({ status_code: 'ready' });
    expect(body.verification_handoff).toMatchObject({
      accepted_input: 'data_quality_evidence_snapshot.v1 JSON',
      digest_algorithm: 'sha256',
      success_exit_code: 0,
    });
  });
});
