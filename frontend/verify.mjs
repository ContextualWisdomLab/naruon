import { chromium } from '@playwright/test';

async function run_cuj(page) {
    await page.goto("http://localhost:3000/mail");
    await page.waitForTimeout(500);
    // Let's ensure a mail is clicked, else right panel is hidden in some states?
    // Wait for the UI
    await page.waitForTimeout(1000);
    await page.screenshot({ path: "/home/jules/verification/screenshots/verification2.png" });
    await page.waitForTimeout(1000);
}

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ recordVideo: { dir: "/home/jules/verification/videos" } });
    const page = await context.newPage();
    try {
        await run_cuj(page);
    } catch (e) {
        console.error("Error during cuj", e);
    } finally {
        await context.close();
        await browser.close();
    }
})();
