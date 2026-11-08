import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { allocationAssignmentStatusKey } from "./src/components/allocationAssignmentStatus.mjs";

test("an applied assignment with the same source and target is shown as retained", () => {
  assert.equal(allocationAssignmentStatusKey("applied", 3, 3), "retained");
});

test("an applied assignment that changed rooms remains shown as applied", () => {
  assert.equal(allocationAssignmentStatusKey("applied", 3, 4), "applied");
});

test("an initial assignment from no room remains shown as applied", () => {
  assert.equal(allocationAssignmentStatusKey("applied", null, 4), "applied");
});

test("non-applied statuses are not relabeled as retained", () => {
  assert.equal(allocationAssignmentStatusKey("proposed", 3, 3), "proposed");
});

test("the Spanish and English assignment labels distinguish retained from applied", async () => {
  const [spanish, english] = await Promise.all([
    readFile(new URL("./src/locales/es/allocation.json", import.meta.url), "utf8").then(JSON.parse),
    readFile(new URL("./src/locales/en/allocation.json", import.meta.url), "utf8").then(JSON.parse)
  ]);

  assert.equal(spanish.proposal.assignmentStatus.retained, "Conservada");
  assert.equal(spanish.proposal.assignmentStatus.applied, "Aplicada");
  assert.equal(english.proposal.assignmentStatus.retained, "Retained");
  assert.equal(english.proposal.assignmentStatus.applied, "Applied");
});
