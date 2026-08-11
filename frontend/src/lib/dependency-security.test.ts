import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const frontendRoot = fileURLToPath(new URL('../..', import.meta.url));
const packageManifest = JSON.parse(
  readFileSync(`${frontendRoot}/package.json`, 'utf8'),
) as {
  overrides?: Record<string, string>;
  resolutions?: Record<string, string>;
};
const lockfile = readFileSync(`${frontendRoot}/pnpm-lock.yaml`, 'utf8');
const workspaceConfig = readFileSync(`${frontendRoot}/pnpm-workspace.yaml`, 'utf8');

describe('frontend dependency security contract', () => {
  it('keeps every nanoid resolution at or above the OSV fixed version', () => {
    const fixedVersion = [5, 1, 16] as const;
    const compareVersions = (left: string, right: readonly number[]) => {
      const parts = left.split('.').map(Number);
      return parts[0] - right[0] || parts[1] - right[1] || parts[2] - right[2];
    };

    expect(packageManifest.overrides?.nanoid).toBe('5.1.16');
    expect(packageManifest.resolutions?.nanoid).toBe('5.1.16');
    expect(workspaceConfig).toContain('  nanoid: "5.1.16"\n');
    expect(compareVersions(packageManifest.overrides?.nanoid ?? '0.0.0', fixedVersion)).toBeGreaterThanOrEqual(0);
    expect(lockfile).toContain('  nanoid: 5.1.16\n');
    expect(lockfile).toContain('  nanoid@5.1.16:');
    expect(lockfile).not.toContain('nanoid@5.1.6');
  });
});
