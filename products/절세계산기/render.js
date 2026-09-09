const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const p = await b.newPage({ viewport: { width: 1080, height: 1080 } });
  await p.setContent(require('fs').readFileSync('thumb.html','utf8'));
  await p.waitForTimeout(300);
  await (await p.$('.card')).screenshot({ path: 'thumbnail.png' });
  await b.close(); console.log('rendered');
})();
