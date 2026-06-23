import { test, expect } from '@playwright/test';

test.describe('Agent Platform E2E Smoke', () => {

  test('首页正常渲染', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar')).toBeVisible();
    await expect(page.locator('.main-content')).toBeVisible();
  });

  test('侧边栏导航可用', async ({ page }) => {
    await page.goto('/');
    // 点击 Agent 管理
    await page.click('.nav-item:has-text("Agent")');
    await expect(page.locator('.view-title')).toContainText('Agent');
  });

  test('仪表盘指标卡片可见', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.metrics-grid')).toBeVisible();
    const cards = page.locator('.metric-card');
    await expect(cards.first()).toBeVisible();
  });

  test('会话中心可访问', async ({ page }) => {
    await page.goto('/');
    await page.click('.nav-item:has-text("会话中心")');
    await expect(page.locator('.view-title')).toContainText('会话中心');
  });

  test('全屏对话页渲染', async ({ page }) => {
    await page.goto('/chat');
    // 应显示对话侧边栏或空状态
    const sidebar = page.locator('.chat-sidebar');
    const emptyHint = page.locator('text=选择一个对话');
    const visible = (await sidebar.isVisible().catch(() => false)) || (await emptyHint.isVisible().catch(() => false));
    expect(visible).toBe(true);
  });

  test('API不可用时前端不崩溃', async ({ page }) => {
    // Mock API 失败
    await page.route('**/api/**', route => route.abort());
    await page.goto('/');
    await page.waitForTimeout(3000);
    // 页面应仍然渲染（可能显示错误但不白屏）
    await expect(page.locator('.sidebar, .main-content, #root > *').first()).toBeVisible();
  });
});
