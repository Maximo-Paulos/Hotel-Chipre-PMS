import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { MARKETING_ROUTES, renderRouteHtml } from "./marketing-html.mjs";

const indexHtml = readFileSync(new URL("./index.html", import.meta.url), "utf8");
const vercel = JSON.parse(readFileSync(new URL("./vercel.json", import.meta.url), "utf8"));

test("every marketing route has a Vercel rewrite pointing at its own file", () => {
  for (const route of MARKETING_ROUTES) {
    const rewrite = vercel.rewrites.find((entry) => entry.source === route.path);
    assert.ok(rewrite, `no rewrite for ${route.path}`);
    assert.equal(rewrite.destination, route.file);
  }
});

test("the SPA catch-all stays last so it never shadows a marketing route", () => {
  assert.equal(vercel.rewrites.at(-1).source, "/(.*)");
});

test("each route bakes its own title, description and canonical", () => {
  for (const route of MARKETING_ROUTES) {
    const html = renderRouteHtml(indexHtml, route);
    assert.match(html, new RegExp(`<title>${route.title.replace(/[|]/g, "\\|")}</title>`));
    assert.ok(html.includes(`content="${route.description}"`), `${route.path} lost its description`);
    assert.ok(
      html.includes(`<link rel="canonical" href="https://hotels-pms.com${route.path}" />`),
      `${route.path} lost its canonical`
    );
    assert.ok(
      html.includes(`<meta property="og:url" content="https://hotels-pms.com${route.path}" />`),
      `${route.path} lost its og:url`
    );
  }
});

test("the og:image is absolute, because unfurlers do not resolve relative paths", () => {
  const html = renderRouteHtml(indexHtml, MARKETING_ROUTES[0]);
  assert.ok(html.includes('content="https://hotels-pms.com/brand/og-default.png"'));
});

test("the pre-hydration script no longer overwrites a baked marketing title", () => {
  // It must bail before touching the document unless the page is noindexed.
  assert.match(indexHtml, /if \(!shouldNoindex\) return;/);
});
