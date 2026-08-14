import { chromium } from '@playwright/test';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  try {
    // Navigate straight to a known layout component containing EmailDetail if possible, or force the inbox view
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });

    // Click the "메일" button in the GNB to go to the inbox
    const mailTab = page.locator('button').filter({ hasText: '메일' }).first();
    if (await mailTab.isVisible()) {
      await mailTab.click();
      await page.waitForTimeout(1000);
    }

    // Attempt to click the first email in the list
    const firstEmail = page.locator('.group').first();
    if (await firstEmail.isVisible()) {
      await firstEmail.click();
    }

    // Wait for the EmailDetail side panel elements
    await page.waitForTimeout(1500); // Give it time to render the layout
    await page.screenshot({ path: '/home/jules/verification/email_detail_panel.png' });
    console.log("Screenshot saved");
  } catch (err) {
    console.error("Error:", err);
  } finally {
    await browser.close();
  }
})();
