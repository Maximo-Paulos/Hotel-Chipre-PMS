import { expect } from "@playwright/test";
import { readFileSync, rmSync, unlinkSync } from "node:fs";
import os from "node:os";
import path from "node:path";

// Shared helper for the local E2E email outbox (see E2E_EMAIL_OUTBOX_PATH in
// frontend/playwright.config.ts). Every journey that signs up, verifies an
// email, or resets a password reads codes from the same JSONL file.
export const emailOutboxPath = path.join(os.tmpdir(), "hotel-chipre-e2e-email-outbox.jsonl");

export function resetEmailOutbox() {
  rmSync(emailOutboxPath, { force: true });
}

export function cleanupEmailOutbox() {
  try {
    unlinkSync(emailOutboxPath);
  } catch {
    // The file may not exist when the test was interrupted before email delivery.
  }
}

function readLatestCode(email: string, subjectPattern: RegExp): string {
  let raw = "";
  try {
    raw = readFileSync(emailOutboxPath, "utf8");
  } catch {
    return "";
  }
  const messages = raw
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line) as { to?: string[]; subject?: string; body?: string })
    .filter((message) => message.to?.includes(email) && subjectPattern.test(message.subject ?? ""));
  const body = messages.at(-1)?.body ?? "";
  const code = body.match(/\b\d{6}\b/)?.[0];
  return code ?? "";
}

export async function waitForCode(email: string, subjectPattern: RegExp): Promise<string> {
  await expect.poll(() => readLatestCode(email, subjectPattern), { timeout: 10_000 }).toMatch(/^\d{6}$/);
  return readLatestCode(email, subjectPattern);
}
