import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const promptStudioSource = readFileSync(
  fileURLToPath(new URL("./page.tsx", import.meta.url)),
  "utf8",
);

describe("Prompt Studio model label lookup contract", () => {
  it("keeps the first label when model values collide", () => {
    expect(promptStudioSource).toContain("if (!map.has(model.value)) map.set(model.value, model.label);");
    expect(promptStudioSource).not.toContain("new Map(MODEL_OPTIONS.map");
  });
});
