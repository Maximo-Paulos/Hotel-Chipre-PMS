import { createHmac } from "node:crypto";

const DEFAULT_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP";

function decodeBase32(secret: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const bits = [...secret.replace(/=+$/g, "").toUpperCase()]
    .map((character) => {
      const value = alphabet.indexOf(character);
      if (value < 0) throw new Error("E2E TOTP secret must be base32");
      return value.toString(2).padStart(5, "0");
    })
    .join("");
  const bytes = bits.match(/.{8}/g) ?? [];
  if (!bytes.length) throw new Error("E2E TOTP secret is too short");
  return Buffer.from(bytes.map((byte) => parseInt(byte, 2)));
}

const secretBytes = () => decodeBase32(process.env.E2E_STEP_UP_OWNER_TOTP_SECRET || DEFAULT_SECRET);

export function totpAtStep(step: number): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const digest = createHmac("sha1", secretBytes()).update(counter).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  return String((digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

export async function nextTotpAfter(lastUsedStep: number): Promise<{ step: number; code: string }> {
  // pyotp validates the current 30-second counter plus one step of clock skew.
  // A code from the next counter is safe to use early, which avoids flaky
  // waits at a boundary while preserving the server's replay protection.
  let step = Math.max(Math.floor(Date.now() / 30_000), lastUsedStep + 1);
  while (step > Math.floor(Date.now() / 30_000) + 1) {
    await new Promise((resolve) => setTimeout(resolve, 100));
    step = Math.max(Math.floor(Date.now() / 30_000), lastUsedStep + 1);
  }
  return { step, code: totpAtStep(step) };
}
