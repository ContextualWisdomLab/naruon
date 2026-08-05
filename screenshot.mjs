import { chromium } from '@playwright/test';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 1024 } });
  await page.goto('http://localhost:3000');
  // Wait for network idle or a specific element
  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'frontend/test-results/manual-screenshot.png', fullPage: true });
  await browser.close();
  console.log('Screenshot saved to frontend/test-results/manual-screenshot.png');
})();
