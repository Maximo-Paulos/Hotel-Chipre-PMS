import { expect, type Locator } from "@playwright/test";

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
