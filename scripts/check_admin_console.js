// বাংলা মন্তব্য: অ্যাডমিন সাইটের কনসোল এরর চেক করার জন্য প্লে-রাইট স্ক্রিপ্ট
const { chromium } = require('@playwright/test');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  const consoleErrors = [];
  const consoleWarnings = [];
  const consoleLogs = [];
  const pageErrors = [];
  const failedRequests = [];

  // কনসোল মেসেজ ক্যাপচার
  page.on('console', (msg) => {
    const text = msg.text();
    if (msg.type() === 'error') {
      consoleErrors.push(text);
    } else if (msg.type() === 'warning') {
      consoleWarnings.push(text);
    } else {
      consoleLogs.push(text);
    }
  });

  // পেজ এরর ক্যাপচার
  page.on('pageerror', (err) => {
    pageErrors.push(err.message);
  });

  // ফেইলড রিকোয়েস্ট ক্যাপচার
  page.on('requestfailed', (req) => {
    failedRequests.push({
      url: req.url(),
      failure: req.failure()?.errorText || 'unknown'
    });
  });

  // বাংলা মন্তব্য: সকল নেটওয়ার্ক রেসপন্স ও এরর স্ট্যাটাস ট্র্যাক করা
  page.on('response', (res) => {
    if (res.status() >= 400) {
      consoleErrors.push(`HTTP ${res.status()} from ${res.url()}`);
    }
  });

  // বাংলা মন্তব্য: Firebase হোস্টেড অ্যাডমিন ফ্রন্টএন্ড ও Render-এর ব্যাকেন্ড চেক করা
  console.log('Testing admin frontend at https://supremeai-admin.web.app ...');
  try {
    await page.goto('https://supremeai-admin.web.app', {
      waitUntil: 'domcontentloaded',
      timeout: 15000
    });
    await page.waitForTimeout(3000);
  } catch (err) {
    pageErrors.push(`Navigation to https://supremeai-admin.web.app failed: ${err.message}`);
  }

  // বাংলা মন্তব্য: ব্যাকেন্ড হেলস চেক (supremeai-backend-docker.onrender.com)
  console.log('Testing backend health at https://supremeai-backend-docker.onrender.com/api/v1/health ...');
  try {
    const healthResp = await page.request.get('https://supremeai-backend-docker.onrender.com/api/v1/health');
    if (!healthResp.ok()) {
      pageErrors.push(`Backend health check failed: HTTP ${healthResp.status()}`);
    }
  } catch (err) {
    pageErrors.push(`Backend health check failed: ${err.message}`);
  }

  console.log('=== CONSOLE ERRORS ===');
  consoleErrors.forEach(e => console.log('ERROR:', e));
  
  console.log('\n=== CONSOLE WARNINGS ===');
  consoleWarnings.forEach(w => console.log('WARN:', w));
  
  console.log('\n=== PAGE ERRORS ===');
  pageErrors.forEach(e => console.log('PAGE_ERROR:', e));
  
  console.log('\n=== FAILED REQUESTS ===');
  failedRequests.forEach(r => console.log('FAILED:', r.url, '-', r.failure));

  console.log('\n=== CONSOLE LOGS (first 20) ===');
  consoleLogs.slice(0, 20).forEach(l => console.log('LOG:', l));

  await browser.close();
})();