const puppeteer = require('puppeteer');
const path = require('path');

// ==========================================
// FinModPro 自动截图脚本 (自动化采集指南)
// ==========================================
// 注意：本脚本假设你的前端运行在 http://localhost:5173
// 并且你的后端已经包含了能够演示的真实数据。
// 在运行前，请先安装依赖: npm install puppeteer

const BASE_URL = 'http://localhost:5173';
const OUTPUT_DIR = __dirname;

const delay = ms => new Promise(res => setTimeout(res, ms));

(async () => {
  console.log('🚀 正在启动 Puppeteer...');
  const browser = await puppeteer.launch({
    headless: "new",
    defaultViewport: { width: 1440, height: 900 }
  });
  
  const page = await browser.newPage();
  
  try {
    // 1. 登录页截图
    console.log('📸 截取登录页...');
    await page.goto(BASE_URL, { waitUntil: 'networkidle0' });
    await page.screenshot({ path: path.join(OUTPUT_DIR, '01-login-page.png') });
    
    // 自动登录 (假设 demo_admin / secret123，按需修改)
    console.log('🔑 尝试自动登录...');
    // 等待用户名输入框出现
    await page.waitForSelector('input[type="text"]', { timeout: 5000 });
    const inputs = await page.$$('input');
    if (inputs.length >= 2) {
      await inputs[0].type('demo_admin'); // username
      await inputs[1].type('secret123'); // password
      
      // 点击登录按钮
      const buttons = await page.$$('button');
      for (const btn of buttons) {
        const text = await page.evaluate(el => el.textContent, btn);
        if (text && text.includes('登录')) {
          await btn.click();
          break;
        }
      }
      
      await page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 10000 }).catch(() => {});
      await delay(2000); // 额外等待渲染完成
    } else {
      console.log('⚠️ 找不到登录输入框，跳过自动登录流程');
      return;
    }

    // 2. 工作台/运维大盘截图
    console.log('📸 截取工作台/大盘页...');
    // 假设登录后直接进入工作台
    await page.screenshot({ path: path.join(OUTPUT_DIR, '02-workbench-dashboard.png') });

    // 3. 知识库管理截图
    console.log('📸 截取知识库页...');
    // 点击导航栏的知识库管理
    const navItems = await page.$$('.nav-item');
    for (const item of navItems) {
      const text = await page.evaluate(el => el.textContent, item);
      if (text && text.includes('知识库管理')) {
        await item.click();
        await delay(2000);
        await page.screenshot({ path: path.join(OUTPUT_DIR, '03-knowledge-base.png') });
        break;
      }
    }

    // 4. 金融问答截图
    console.log('📸 截取问答页...');
    for (const item of navItems) {
      const text = await page.evaluate(el => el.textContent, item);
      if (text && text.includes('金融问答')) {
        await item.click();
        await delay(2000);
        // 如果有需要可以自动发送一条消息并等待结果，这里仅展示界面
        await page.screenshot({ path: path.join(OUTPUT_DIR, '04-qa-result.png') });
        break;
      }
    }

    // 5. 风险事件审核截图
    console.log('📸 截取风险事件审核页...');
    for (const item of navItems) {
      const text = await page.evaluate(el => el.textContent, item);
      if (text && text.includes('风险与摘要')) {
        await item.click();
        await delay(2000);
        // 默认显示事件审核 Tab
        await page.screenshot({ path: path.join(OUTPUT_DIR, '05-risk-review.png') });
        break;
      }
    }

    // 6. 风险报告生成截图
    console.log('📸 截取风险报告页...');
    // 寻找"风险报告生成" Tab 按钮并点击
    const tabBtns = await page.$$('.tab-btn');
    for (const btn of tabBtns) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text && text.includes('风险报告生成')) {
        await btn.click();
        await delay(2000);
        await page.screenshot({ path: path.join(OUTPUT_DIR, '06-risk-report.png') });
        break;
      }
    }

    console.log('✅ 所有截图采集指令已执行完成！请检查当前目录。');

  } catch (err) {
    console.error('❌ 执行过程发生错误:', err);
    console.log('提示：当前系统可能是无头环境，若需完美截图请在带有界面的本地开发机上运行本脚本。');
  } finally {
    await browser.close();
  }
})();
