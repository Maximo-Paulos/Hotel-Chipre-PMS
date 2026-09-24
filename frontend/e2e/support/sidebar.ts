import { expect, type Locator, type Page } from "@playwright/test";

// B6.1: routes outside the daily nav row sit inside a collapsed sidebar
// <details> group, and closed content isn't clickable, so open its <summary>
// first. The link only renders once the session's permissions have loaded:
// deciding before that skips the group and leaves the link inside a closed
// <details>, which then times out on click.
export async function revealCollapsedNavLink(link: Locator) {
  await expect(link).toHaveCount(1);
  const group = link.locator("xpath=ancestor::details[1]");
  if ((await group.count()) > 0 && !(await group.evaluate((el) => (el as HTMLDetailsElement).open))) {
    await group.locator("summary").first().click();
  }
}

// The sidebar shows from Tailwind's md breakpoint (768px); below it the nav
// lives in the slide-over panel behind the menu button. Choosing by viewport
// keeps navigation deterministic while the shell is still loading.
export async function navigateFromShell(page: Page, path: string) {
  const isDesktop = (page.viewportSize()?.width ?? 1280) >= 768;
  if (!isDesktop) await page.getByTestId("mobile-menu-button").click();
  const nav = isDesktop ? "aside nav" : 'nav[aria-label="Navegación móvil"]';
  const link = page.locator(`${nav} a[href="${path}"]`);
  await revealCollapsedNavLink(link);
  await link.click();
  await expect(page).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
}
