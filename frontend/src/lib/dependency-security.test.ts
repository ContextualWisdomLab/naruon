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

type NanoidLockSection = 'packages' | 'snapshots';

const compareVersions = (left: string, right: readonly number[]) => {
  const parts = left.split('.').map(Number);
  return parts[0] - right[0] || parts[1] - right[1] || parts[2] - right[2];
};

const isAffectedNanoidVersion = (version: string) =>
  compareVersions(version, [3, 3, 16]) < 0 ||
  (compareVersions(version, [4, 0, 0]) >= 0 &&
    compareVersions(version, [5, 1, 16]) < 0);

const lockedNanoidVersions = (): Record<NanoidLockSection, string[]> => {
  const versions: Record<NanoidLockSection, string[]> = {
    packages: [],
    snapshots: [],
  };
  let section: NanoidLockSection | null = null;

  for (const line of lockfile.split('\n')) {
    if (line === 'packages:') {
      section = 'packages';
      continue;
    }
    if (line === 'snapshots:') {
      section = 'snapshots';
      continue;
    }
    if (/^[A-Za-z][A-Za-z0-9_-]*:$/.test(line)) {
      section = null;
      continue;
    }
    if (section === null) {
      continue;
    }

    const match = /^  nanoid@(\d+\.\d+\.\d+):/.exec(line);
    if (match) {
      versions[section].push(match[1]);
    }
  }

  return versions;
};

describe('frontend dependency security contract', () => {
  it.each(['3.3.15', '4.0.0', '5.1.15'])(
    'recognizes affected nanoid version %s',
    (version) => {
      expect(isAffectedNanoidVersion(version)).toBe(true);
    },
  );

  it.each(['3.3.16', '3.3.99', '5.1.16', '6.0.0'])(
    'recognizes patched nanoid version %s',
    (version) => {
      expect(isAffectedNanoidVersion(version)).toBe(false);
    },
  );

  it('keeps each locked nanoid version outside the advisory ranges', () => {
    expect(packageManifest.overrides?.nanoid).toBe('5.1.16');
    expect(packageManifest.resolutions?.nanoid).toBe('5.1.16');
    expect(workspaceConfig).toContain('  nanoid: "5.1.16"\n');
    expect(lockfile).toContain('  nanoid: 5.1.16\n');

    const versions = lockedNanoidVersions();
    for (const section of ['packages', 'snapshots'] as const) {
      expect(versions[section]).toEqual(['5.1.16']);
      for (const version of versions[section]) {
        expect(isAffectedNanoidVersion(version)).toBe(false);
      }
    }
  });
});
