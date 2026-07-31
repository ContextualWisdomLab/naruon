import { describe, expect, it } from "vitest";
import { rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import {
  createPilotArtifactDirectory,
  createPilotServerLaunchSpec,
  resolvePilotArtifactPath,
  resolvePilotBaseUrl,
  resolvePilotChromePath,
} from "./pilot-ui-smoke.mjs";

describe("pilot UI smoke base URL guard", () => {
  it("allows localhost pilot smoke targets", () => {
    expect(resolvePilotBaseUrl("http://127.0.0.1:3001").hostname).toBe("127.0.0.1");
    expect(resolvePilotBaseUrl("http://localhost:3001").hostname).toBe("localhost");
    expect(resolvePilotBaseUrl("http://[::1]:3001").hostname).toBe("[::1]");
  });

  it("rejects non-localhost targets", () => {
    expect(() => resolvePilotBaseUrl("https://staging.example.com")).toThrow("localhost targets");
    expect(() => resolvePilotBaseUrl("https://naruon.example.com")).toThrow("localhost targets");
    expect(() => resolvePilotBaseUrl("http://127.0.0.1:3000")).toThrow("localhost targets");
    expect(() => resolvePilotBaseUrl("https://127.0.0.1:3001")).toThrow("localhost targets");
    expect(() => resolvePilotBaseUrl("http://127.0.0.1:3001/admin")).toThrow("localhost targets");
    expect(() => resolvePilotBaseUrl("http://127.0.0.1:3001?target=internal")).toThrow("localhost targets");
    expect(() => resolvePilotBaseUrl("http://user@127.0.0.1:3001")).toThrow("localhost targets");
    expect(() => resolvePilotBaseUrl("http://2130706433:3001")).toThrow("localhost targets");
  });

  it("creates a private unique artifact directory and contains fixed screenshot names", async () => {
    const artifactDirectory = await createPilotArtifactDirectory(
      "/tmp/naruon-pilot-mail.png",
      "/tmp/naruon-pilot-search.png",
    );
    try {
      const relativePath = path.relative(tmpdir(), artifactDirectory);
      expect(relativePath).not.toMatch(/^\.\.(?:[/\\]|$)/u);
      expect(path.isAbsolute(relativePath)).toBe(false);
      expect((await stat(artifactDirectory)).mode & 0o077).toBe(0);
      expect(resolvePilotArtifactPath(artifactDirectory, "mail.png")).toBe(path.join(artifactDirectory, "mail.png"));
      expect(() => resolvePilotArtifactPath(artifactDirectory, "../escape.png")).toThrow("safe file name");
      expect(() => resolvePilotArtifactPath(artifactDirectory, "nested/escape.png")).toThrow("safe file name");
      await expect(
        createPilotArtifactDirectory("/tmp/../etc/pilot.png", "/tmp/naruon-pilot-search.png"),
      ).rejects.toThrow("approved artifact profile");
    } finally {
      await rm(artifactDirectory, { recursive: true, force: true });
    }
  });

  it("allows only fixed system Chrome fallback executables", () => {
    expect(resolvePilotChromePath("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")).toBe(
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    );
    expect(resolvePilotChromePath("/usr/bin/chromium")).toBe("/usr/bin/chromium");
    expect(() => resolvePilotChromePath("/tmp/attacker-controlled-chrome")).toThrow("approved Chrome executable");
    expect(() => resolvePilotChromePath("../../bin/chrome")).toThrow("approved Chrome executable");
  });

  it("launches Next through the current Node executable with fixed argv", () => {
    const launchSpec = createPilotServerLaunchSpec("http://localhost:3001");
    expect(launchSpec.executable).toBe(process.execPath);
    expect(launchSpec.args.slice(-6)).toEqual([
      "dev",
      "--webpack",
      "--hostname",
      "localhost",
      "--port",
      "3001",
    ]);
    expect(() => createPilotServerLaunchSpec("http://localhost:3001;touch /tmp/pwned")).toThrow(
      "localhost targets",
    );
  });
});
