/* eslint-disable */
const { chromium } = require('playwright');
const fs = require('fs');

const NAVIGATION_OPTIONS = { waitUntil: 'load', timeout: 30000 };
const SCREENSHOT_TARGETS = [
  { route: '/', name: 'home', navigate: (page) => page.goto('http://127.0.0.1:3000/', NAVIGATION_OPTIONS) },
  { route: '/mail', name: 'mail', navigate: (page) => page.goto('http://127.0.0.1:3000/mail', NAVIGATION_OPTIONS) },
  { route: '/calendar', name: 'calendar', navigate: (page) => page.goto('http://127.0.0.1:3000/calendar', NAVIGATION_OPTIONS) },
  { route: '/tasks', name: 'tasks', navigate: (page) => page.goto('http://127.0.0.1:3000/tasks', NAVIGATION_OPTIONS) },
  { route: '/projects', name: 'projects', navigate: (page) => page.goto('http://127.0.0.1:3000/projects', NAVIGATION_OPTIONS) },
  { route: '/search', name: 'search', navigate: (page) => page.goto('http://127.0.0.1:3000/search', NAVIGATION_OPTIONS) },
  { route: '/data', name: 'data', navigate: (page) => page.goto('http://127.0.0.1:3000/data', NAVIGATION_OPTIONS) },
  { route: '/ai-hub', name: 'ai-hub', navigate: (page) => page.goto('http://127.0.0.1:3000/ai-hub', NAVIGATION_OPTIONS) },
  { route: '/security', name: 'security', navigate: (page) => page.goto('http://127.0.0.1:3000/security', NAVIGATION_OPTIONS) },
  { route: '/settings', name: 'settings', navigate: (page) => page.goto('http://127.0.0.1:3000/settings', NAVIGATION_OPTIONS) },
];

(async () => {
  if (!fs.existsSync('test-results')) {
    fs.mkdirSync('test-results');
  }
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 1024 } });

  for (const target of SCREENSHOT_TARGETS) {
    const { route, name } = target;
    console.log('Taking screenshot for route', route);
    try {
      await target.navigate(page);
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
