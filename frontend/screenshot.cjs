/* eslint-disable */
const { chromium } = require('playwright');
const fs = require('fs');

const SCREENSHOT_ORIGIN = 'http://127.0.0.1:3000';
const SCREENSHOT_ROUTES = [
  '/',
  '/mail',
  '/calendar',
  '/tasks',
  '/projects',
  '/search',
  '/data',
  '/ai-hub',
  '/security',
  '/settings',
];
const ALLOWED_ROUTES = new Set(SCREENSHOT_ROUTES);

function routeUrl(route) {
  if (!ALLOWED_ROUTES.has(route)) {
    throw new Error(`Unsupported screenshot route: ${route}`);
  }
  const url = new URL(route, SCREENSHOT_ORIGIN);
  if (url.origin !== SCREENSHOT_ORIGIN || url.pathname !== route || url.search || url.hash) {
    throw new Error(`Unsafe screenshot route: ${route}`);
  }
  return url.toString();
}

(async () => {
  if (!fs.existsSync('test-results')) {
    fs.mkdirSync('test-results');
  }
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 1024 } });

  for (const route of SCREENSHOT_ROUTES) {
    const url = routeUrl(route);
    console.log('Taking screenshot for route', route);
    try {
      await page.goto(url, { waitUntil: 'load', timeout: 30000 });
      await page.waitForTimeout(2000);
      const name = route === '/' ? 'home' : route.slice(1);
      await page.screenshot({ path: `test-results/${name}-screenshot.png`, fullPage: true });
      console.log(`Saved test-results/${name}-screenshot.png`);
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : String(e);
      console.error('Failed to capture route', { route, error: errorMessage });
    }
  }

  await browser.close();
  console.log('All screenshots completed.');
})();
