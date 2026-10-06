import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const sourceRoot = path.join(frontendRoot, "src");
const pluralSuffixes = ["zero", "one", "two", "few", "many", "other"];

async function listTsxFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return listTsxFiles(entryPath);
    return entry.isFile() && entry.name.endsWith(".tsx") ? [entryPath] : [];
  }));
  return nested.flat();
}

function flattenKeys(value, prefix = "") {
  return Object.entries(value).flatMap(([key, nested]) => {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    return nested && typeof nested === "object" ? flattenKeys(nested, fullKey) : [fullKey];
  });
}

function hasTranslation(localeKeys, key) {
  if (localeKeys.has(key)) return true;
  return pluralSuffixes.some((suffix) => localeKeys.has(`${key}_${suffix}`));
}

test("literal translation keys exist in both locales for single-namespace TSX files", async () => {
  const files = await listTsxFiles(sourceRoot);
  const localeKeysByNamespace = new Map();
  const violations = [];

  async function loadKeys(language, namespace) {
    const cacheKey = `${language}/${namespace}`;
    if (!localeKeysByNamespace.has(cacheKey)) {
      const jsonPath = path.join(sourceRoot, "locales", language, `${namespace}.json`);
      const locale = JSON.parse(await readFile(jsonPath, "utf8"));
      localeKeysByNamespace.set(cacheKey, new Set(flattenKeys(locale)));
    }
    return localeKeysByNamespace.get(cacheKey);
  }

  for (const filePath of files) {
    const source = await readFile(filePath, "utf8");
    const translationHooks = [...source.matchAll(/useTranslation\(\s*(?:(["'])([^"']+)\1\s*)?\)/gu)];
    if (!translationHooks.length) continue;

    // Some files contain separate components with different namespaces. Keep
    // this guard narrow and let their existing namespace-specific tests cover
    // them rather than guessing which hook owns each call.
    const namespaces = new Set(translationHooks.map((match) => match[2] || "common"));
    if (namespaces.size !== 1) continue;
    const defaultNamespace = [...namespaces][0];

    for (const match of source.matchAll(/\bt\(\s*(["'`])([^"'`]+)\1/gu)) {
      const [, , rawKey] = match;
      if (rawKey.includes("${")) continue;

      const callTail = source.slice(match.index + match[0].length, match.index + match[0].length + 240);
      if (/^\s*\+/u.test(callTail)) continue;
      const namespaceOption = callTail.match(/\bns\s*:\s*(["'])([^"']+)\1/u)?.[2];
      const separatorIndex = rawKey.indexOf(":");
      const namespace = namespaceOption || (separatorIndex > 0 ? rawKey.slice(0, separatorIndex) : defaultNamespace);
      const key = separatorIndex > 0 && !namespaceOption ? rawKey.slice(separatorIndex + 1) : rawKey;

      for (const language of ["es", "en"]) {
        try {
          const localeKeys = await loadKeys(language, namespace);
          if (!hasTranslation(localeKeys, key)) {
            violations.push(`${path.relative(frontendRoot, filePath)}: ${language}/${namespace}:${key}`);
          }
        } catch (error) {
          violations.push(`${path.relative(frontendRoot, filePath)}: missing ${language}/${namespace}.json (${error.message})`);
        }
      }
    }
  }

  assert.deepEqual(violations, [], `Missing translation keys:\n${violations.join("\n")}`);
});
