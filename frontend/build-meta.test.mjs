import assert from "node:assert/strict";
import test from "node:test";

import { resolveCodeSha } from "./build-meta.mjs";

const sha = "0123456789abcdef0123456789abcdef01234567";

test("uses and normalizes Vercel's immutable commit SHA", () => {
  assert.equal(resolveCodeSha({ VERCEL: "1", VERCEL_GIT_COMMIT_SHA: sha.toUpperCase() }), sha);
});

test("refuses an untraceable Vercel artifact", () => {
  assert.throws(() => resolveCodeSha({ VERCEL: "1" }), /VERCEL_GIT_COMMIT_SHA is required/);
  assert.throws(
    () => resolveCodeSha({ VERCEL: "1", VERCEL_GIT_COMMIT_SHA: "not-a-sha" }),
    /full 40-character hexadecimal Git SHA/
  );
});

test("allows a validated local fallback or an explicit unknown marker", () => {
  assert.equal(resolveCodeSha({ GIT_COMMIT_SHA: sha }), sha);
  assert.equal(resolveCodeSha({}), "unknown");
});
