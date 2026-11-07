import fs from "node:fs";
import path from "node:path";

const FULL_GIT_SHA = /^[0-9a-f]{40}$/i;

const validatedSha = (value, variableName) => {
  const candidate = value?.trim();
  if (!candidate || !FULL_GIT_SHA.test(candidate)) {
    throw new Error(`${variableName} must be a full 40-character hexadecimal Git SHA.`);
  }
  return candidate.toLowerCase();
};

export function resolveCodeSha(env = process.env) {
  const vercelSha = env.VERCEL_GIT_COMMIT_SHA?.trim();
  if (vercelSha) return validatedSha(vercelSha, "VERCEL_GIT_COMMIT_SHA");

  // A Vercel artifact without Vercel's own immutable commit identifier cannot
  // be proven to correspond to a deployment, so fail the build instead of
  // publishing ambiguous metadata. Local builds may use an explicit fallback.
  if (env.VERCEL === "1") {
    throw new Error("VERCEL_GIT_COMMIT_SHA is required for Vercel builds.");
  }

  const localSha = env.GIT_COMMIT_SHA?.trim();
  return localSha ? validatedSha(localSha, "GIT_COMMIT_SHA") : "unknown";
}

export function buildMetaPlugin(env = process.env) {
  const codeSha = resolveCodeSha(env);
  let outDir = "dist";
  return {
    name: "hotel-chipre-build-meta",
    configResolved(config) {
      outDir = config.build.outDir;
    },
    config() {
      return { define: { __APP_BUILD_SHA__: JSON.stringify(codeSha) } };
    },
    generateBundle() {
      this.emitFile({
        type: "asset",
        fileName: "build-meta.json",
        source: `${JSON.stringify({ code_sha: codeSha })}\n`
      });
    },
    closeBundle() {
      const workerPath = path.resolve(outDir, "sw.js");
      if (!fs.existsSync(workerPath)) return;
      const source = fs.readFileSync(workerPath, "utf8");
      if (!source.includes("__APP_BUILD_SHA__")) {
        throw new Error("Service worker is missing its build SHA placeholder.");
      }
      fs.writeFileSync(workerPath, source.replaceAll("__APP_BUILD_SHA__", codeSha));
    }
  };
}
