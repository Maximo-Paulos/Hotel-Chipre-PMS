import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import test from "node:test";

const wizardSource = await readFile(
  new URL("./src/views/onboarding/OnboardingWizard.tsx", import.meta.url),
  "utf8"
);
const availabilityExpression = wizardSource.match(/const trialAvailable = ([^;]+);/)?.[1];

test("trial is available only when the API explicitly returns true", () => {
  assert.ok(availabilityExpression, "onboarding must define the trial availability guard");

  const isAvailable = (currentSubscription) =>
    vm.runInNewContext(availabilityExpression, { currentSubscription });

  assert.equal(isAvailable(undefined), false);
  assert.equal(isAvailable(null), false);
  assert.equal(isAvailable({}), false);
  assert.equal(isAvailable({ trial_available: undefined }), false);
  assert.equal(isAvailable({ trial_available: false }), false);
  assert.equal(isAvailable({ trial_available: true }), true);
});
