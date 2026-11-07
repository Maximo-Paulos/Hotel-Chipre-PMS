import test from "node:test";
import assert from "node:assert/strict";

import { isStaleBundleLoadError } from "./src/utils/routeLoadError.mjs";

test("recognizes Vite dynamic import failures caused by stale browser bundles", () => {
  assert.equal(
    isStaleBundleLoadError(
      new TypeError("Failed to fetch dynamically imported module: /assets/GuestsPage-old.js")
    ),
    true
  );
  assert.equal(isStaleBundleLoadError(new Error("Importing a module script failed.")), true);
  assert.equal(isStaleBundleLoadError(new Error("Loading chunk 42 failed.")), true);
});

test("does not classify ordinary route failures as stale bundle errors", () => {
  assert.equal(isStaleBundleLoadError(new Error("Request timed out")), false);
  assert.equal(isStaleBundleLoadError({ status: 403, statusText: "Forbidden" }), false);
  assert.equal(isStaleBundleLoadError(null), false);
});
