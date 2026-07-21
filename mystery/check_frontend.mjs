import { chromium } from 'playwright';

(async () => {
  const port = process.env.MYSTERY_FRONTEND_PORT || 5179;
  let hasError = false;

  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.type(), msg.text()));
  page.on('pageerror', error => {
    console.log('BROWSER ERROR:', error.message);
    hasError = true;
  });

  await page.goto(`http://localhost:${port}`);
  // Wait for network idle or 3 seconds
  await page.waitForTimeout(3000);
  await browser.close();

  if (hasError) process.exit(1);
})();
