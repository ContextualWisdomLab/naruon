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
const NAVIGATION_OPTIONS = { waitUntil: 'load', timeout: 30000 };

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

async function navigateToRoute(page, route) {
  switch (route) {
    case '/':
      return page.goto('http://127.0.0.1:3000/', NAVIGATION_OPTIONS);
    case '/mail':
      return page.goto('http://127.0.0.1:3000/mail', NAVIGATION_OPTIONS);
    case '/calendar':
      return page.goto('http://127.0.0.1:3000/calendar', NAVIGATION_OPTIONS);
    case '/tasks':
      return page.goto('http://127.0.0.1:3000/tasks', NAVIGATION_OPTIONS);
    case '/projects':
      return page.goto('http://127.0.0.1:3000/projects', NAVIGATION_OPTIONS);
    case '/search':
      return page.goto('http://127.0.0.1:3000/search', NAVIGATION_OPTIONS);
    case '/data':
      return page.goto('http://127.0.0.1:3000/data', NAVIGATION_OPTIONS);
    case '/ai-hub':
      return page.goto('http://127.0.0.1:3000/ai-hub', NAVIGATION_OPTIONS);
    case '/security':
      return page.goto('http://127.0.0.1:3000/security', NAVIGATION_OPTIONS);
    case '/settings':
      return page.goto('http://127.0.0.1:3000/settings', NAVIGATION_OPTIONS);
    default:
      throw new Error(`Unsupported screenshot route: ${route}`);
  }
}

(async () => {
  if (!fs.existsSync('test-results')) {
    fs.mkdirSync('test-results');
  }
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 1024 } });

  for (const route of SCREENSHOT_ROUTES) {
    routeUrl(route);
    console.log('Taking screenshot for route', route);
    try {
      await navigateToRoute(page, route);
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
