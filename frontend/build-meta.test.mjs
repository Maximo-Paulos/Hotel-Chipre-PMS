import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { buildMetaPlugin } from "./build-meta.mjs";

const sha = "a94c1209a8aeb2aee80b348799acef54aef34e14";

test("build SHA is embedded in the frontend runtime and service worker cache key", () => {
  const plugin = buildMetaPlugin({ VERCEL_GIT_COMMIT_SHA: sha });
  assert.equal(plugin.config().define.__APP_BUILD_SHA__, JSON.stringify(sha));

  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "hcpms-build-meta-"));
  try {
    fs.writeFileSync(path.join(outDir, "sw.js"), 'const BUILD_SHA = "__APP_BUILD_SHA__";');
    plugin.configResolved({ build: { outDir } });
    plugin.closeBundle();
    assert.equal(fs.readFileSync(path.join(outDir, "sw.js"), "utf8"), `const BUILD_SHA = "${sha}";`);
  } finally {
    fs.rmSync(outDir, { recursive: true, force: true });
  }
});
