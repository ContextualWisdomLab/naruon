/* eslint-disable */
const { chromium } = require('playwright');
const fs = require('fs');

const SCREENSHOT_ORIGIN = 'http://127.0.0.1:3000';
const SCREENSHOT_ROUTES = [
  { route: '/', name: 'home' },
  { route: '/mail', name: 'mail' },
  { route: '/calendar', name: 'calendar' },
  { route: '/tasks', name: 'tasks' },
  { route: '/projects', name: 'projects' },
  { route: '/search', name: 'search' },
  { route: '/data', name: 'data' },
  { route: '/ai-hub', name: 'ai-hub' },
  { route: '/security', name: 'security' },
  { route: '/settings', name: 'settings' },
];
const GOTO_OPTIONS = { waitUntil: 'load', timeout: 30000 };

async function gotoScreenshotRoute(page, route) {
  switch (route) {
    case '/':
      return page.goto('http://127.0.0.1:3000/', GOTO_OPTIONS);
    case '/mail':
      return page.goto('http://127.0.0.1:3000/mail', GOTO_OPTIONS);
    case '/calendar':
      return page.goto('http://127.0.0.1:3000/calendar', GOTO_OPTIONS);
    case '/tasks':
      return page.goto('http://127.0.0.1:3000/tasks', GOTO_OPTIONS);
    case '/projects':
      return page.goto('http://127.0.0.1:3000/projects', GOTO_OPTIONS);
    case '/search':
      return page.goto('http://127.0.0.1:3000/search', GOTO_OPTIONS);
    case '/data':
      return page.goto('http://127.0.0.1:3000/data', GOTO_OPTIONS);
    case '/ai-hub':
      return page.goto('http://127.0.0.1:3000/ai-hub', GOTO_OPTIONS);
    case '/security':
      return page.goto('http://127.0.0.1:3000/security', GOTO_OPTIONS);
    case '/settings':
      return page.goto('http://127.0.0.1:3000/settings', GOTO_OPTIONS);
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

  for (const { route, name } of SCREENSHOT_ROUTES) {
    console.log('Taking screenshot for route', route);
    try {
      await gotoScreenshotRoute(page, route);
      await page.waitForTimeout(2000);
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
