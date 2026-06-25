# AgentOS 多智能体协作平台 — 测试策略方案

> 端测测 · 2026-06-25  
> 目标项目：`github.com/1942293420/agent1`


## 1. 项目画像速览

| 维度 | 详情 |
|------|------|
| **前端** | React 18 + Vite 5 + React Router 7 + CSS Variables |
| **后端** | Django 5.2 + DRF 3.17 + gunicorn |
| **数据层** | SQLite WAL（11 表） + Redis（Pub/Sub + List Queue） |
| **Agent 引擎** | Hermes CLI + DeepSeek API，python subprocess 子进程隔离 |
| **现有测试** | pytest 46/46 + Playwright smoke 6 case + Vitest 框架已配置 |
| **部署** | systemctl user service × 3（backend :8001 / worker / frontend :5174） |

### 16 个前端页面

```
Dashboard / Tasks+TaskGraph / Agents / Skills / Memory
Sessions / Tokens / Workers / CronJobs / Settings
Monitor / OutputView / ProfileView / AdminView / Fallback
```

### 认证 & 安全

```
登录 → CSRF Cookie → Session → Admin 审批 → 正常使用
所有 fetch 携带 credentials:'include' + X-CSRFToken header
```

### 核心业务流：Plan-first 多 Agent 调度

```
用户消息 → 云枢 PLAN → PlanGraph.parse() → execute_plan_graph()
         → 批次 SPAWN(hermes) → WAIT_ALL → REFLECT → REPLY
         → 每个 SPAWN 生成 子 agent 子进程 + TaskNode 追踪
```


## 2. 测试金字塔总览

```
         ┌─────────┐
         │  E2E    │  10% — 关键用户旅程 15-20 条
         │Playwright│      (登录→对话→任务图→登出 全链路)
         ├─────────┤
         │集成测试  │  20% — API + DB + Redis + Agent mock
         │ pytest  │      60-80 条
         ├─────────┤
         │单元测试  │  70% — Django models/views/utils
         │pytest   │      React 组件/hooks/工具函数
         │Vitest   │      120-150 条
         └─────────┘
```

**不倒金字塔** — 这是一个有复杂后端业务逻辑、多进程协同的系统，单元测试必须占主导。


## 3. 第一层：单元测试（70%）

### 3.1 后端 Django 单元测试（pytest-django，目标 90+ 条）

#### Model 层测试（~25 条）

| 测试对象 | 用例方向 | 优先级 |
|----------|----------|--------|
| `TaskNode` 模型 | 创建/status 状态机流转/Parent-Child 关联/时间戳自动设置 | P0 |
| `User/UserProfile` | 创建/is_staff 权限/昵称字段/审批状态 | P0 |
| `Conversation/Message` | 创建/关联 user/排序/已读状态 | P0 |
| `AgentProfile` | 工厂创建/能力标签/角色分配 | P1 |
| `Skill/Knowledge` | 创建/图标/分类/搜索 | P1 |
| `CronJob` | 创建/调度表达式校验/启用禁用 | P2 |
| `Token` | 创建/过期时间校验/revoke | P2 |

#### 核心引擎层（~25 条，这是最关键的部分）

| 模块 | 测试要点 | 优先级 |
|------|----------|--------|
| `plan_parser.py` | PlanGraph 解析 YAML-like 输入 / 依赖图正确构建 / 并行组识别 / 空计划/格式错误健壮性 | **P0** |
| `yunshu_io.py` | PLAN→SPAWN→WAIT→REFLECT→REPLY 状态机流转 / 超时策略 / 方案B 代码接管 | **P0** |
| `orchestrator.py` | Plan-first 模式 / 回退逻辑 / fallback reply | **P0** |
| `agent_registry.py` | Banni/Basir/云衡 角色工厂 / 未知 Agent 请求 | P0 |
| `context_aggregator.py` | 多源消息聚合 / 去重 / 上限 20 条 / 4000 字符截断 | P1 |
| `pitfall_memory.py` | 记录/召回/过期清理 | P1 |
| `redis_worker.py` | 队列消费 / 背压 / 20 并发 / 优雅关闭 | P1 |

#### View/API 层（~25 条）

| 端点 | 测试场景 | 优先级 |
|------|----------|--------|
| `POST /api/auth/login/` | 正确凭证 / 错误密码 / 未审批用户 / 空 body / SQL 注入防护 | P0 |
| `GET /api/auth/whoami/` | 已登录 / 未登录 / 过期 session | P0 |
| `POST /api/auth/register/` | 正常注册 / 重复用户名 / 弱密码 / 空字段 | P0 |
| `GET/POST /api/admin/users/` | admin 权限 / 非 admin 403 / 审批/重置密码 | P0 |
| `GET /api/parent-tasks/{id}/graph/` | 有 TaskNode / 无 TaskNode / 权限 | P0 |
| `POST /api/parent-tasks/{id}/stop/` | 正常停止 / 已停止 / 不存在的任务 | P0 |
| `GET /api/tasks/` | 分页 / 排序 / 筛选 | P1 |
| `GET /api/agents/` | 列表返回 / 分页 | P1 |
| `GET /api/system/workers/` | Worker 状态 | P2 |

#### 工具函数层（~15 条）

- Hermes CLI 参数构建
- 超时时间计算
- 子进程管理（mock subprocess.Popen）
- SSE 流解析

### 3.2 前端 Vitest 单元测试（目标 30+ 条）

#### 组件测试（React Testing Library + jsdom）

| 组件 | 测试要点 | 优先级 |
|------|----------|--------|
| `ErrorBoundary` | 正常渲染 / 子组件崩溃后显示 fallback | P0 |
| `Modal` | 打开/关闭 / 关闭回调 / 内容渲染 | P1 |
| `DetailPanel` | 数据展示 / 关闭按钮 / 空数据 | P1 |
| `Toast` | 消息显示 / 自动消失 | P2 |
| `PageLoader` | 加载中状态渲染 | P2 |

#### Hooks 测试

| Hook | 测试要点 | 优先级 |
|------|----------|--------|
| `useEventSource` | 连接 / 接收消息 / 断开重连 / 清理 | P0 |

#### 工具函数测试

| 函数 | 测试要点 |
|------|----------|
| `api.js` — `getCSRFToken()` | cookie 存在/不存在 |
| `api.js` — `request()` | GET/POST/PATCH/DELETE / CSRF header 自动添加 / credentials / 非 2xx 抛异常 |


## 4. 第二层：集成测试（20%）

### 4.1 API 集成测试（pytest-django + 真实 SQLite/Redis，~40 条）

#### 认证全链路（~10 条）

```
1. 注册 → whoami(未审批) → admin 审批 → login → whoami(已登录) → logout → whoami(401)
2. CSRF token 有效期校验
3. 跨 session 安全：Session A 不能访问 Session B 的数据
4. 密码修改后旧 token 失效
```

#### 任务生命周期全链路（~15 条）

```
1. 创建任务 → 查询 → TaskNode 状态跟踪 → 停止 → 查询（确认已停止）
2. PlanGraph 生成 → API 返回 nodes + edges → JSON 结构校验
3. 子任务超时 → 父任务状态正确 → fallback reply
4. 并发创建多个任务 → Worker 背压
```

#### Redis 集成（~10 条）

```
1. Pub/Sub 消息发布订阅正常
2. List Queue 入列出列顺序
3. Worker 消费后 ACK
4. Redis 断开后 Worker 重连
```

#### 跨端上下文集成（~5 条）

```
1. 飞书消息 + Web 消息聚合
2. 去重逻辑
3. 上限截断
```

### 4.2 前端集成测试（Vitest + MSW mock，~15 条）

```
1. AppShell 渲染 → API 调用 → 各状态正确落在 Context
2. AuthContext.Provider → login → user 状态 → logout 重定向
3. 各 API 失败时页面不白屏（Loading → Error 状态）
4. Dashboard 数据聚合（6 个 API 并行请求）
```


## 5. 第三层：E2E 测试（10%）

### 5.1 现有测试评估

项目已有 6 条 Playwright smoke 测试，覆盖了基础渲染和导航。**但缺少最重要的：认证流程和核心业务流。**

### 5.2 新增 E2E 用例（目标 15-20 条）

#### 认证流程（P0 — 必须覆盖）

```
✅ auth-01: 未登录访问 '/' → 重定向到登录页
✅ auth-02: 登录成功 → 跳转 Dashboard → whoami 返回正确用户
✅ auth-03: 错误密码 → 显示错误提示 → 停留在登录页
✅ auth-04: 注册 → 显示"等待审批"提示
✅ auth-05: 登出 → 清除 session → 重定向到登录页
✅ auth-06: 直接访问 /admin → 非 admin 用户被拒绝
```

#### 核心业务流（P0）

```
✅ task-01: 登录 → /tasks → 任务列表渲染 → 点击任务 → TaskGraph 可视化
✅ task-02: 创建新任务 → 选择 Agent → 发送消息 → 等待回复 → 输出面板显示
✅ task-03: TaskGraph 节点状态实时更新（通过 polling/SSE）
✅ task-04: 停止运行中任务 → 确认状态变为 stopped
```

#### 导航 + UI（P1）

```
✅ nav-01: 侧边栏 16 个路由全部可访问
✅ nav-02: 移动端汉堡菜单打开/关闭
✅ ui-01: 深色主题一致性（截图对比关键页面）
✅ ui-02: 404 路由 fallback 到 Dashboard
```

#### 异常场景（P1）

```
✅ error-01: API 500 → Toast 提示 → 页面不崩溃
✅ error-02: 网络断开 → 显示错误状态
✅ error-03: 长时间无操作 → session 过期 → 下次操作重定向登录
```

#### 可访问性（P1）— 自动化 scan

```
✅ a11y-01: axe-core 扫描登录页（WCAG 2.1 AA）
✅ a11y-02: axe-core 扫描 Dashboard
✅ a11y-03: 键盘 Tab 导航所有交互元素
✅ a11y-04: focus 可见性检查
```

### 5.3 Playwright 配置增强建议

```js
// 当前配置不足之处：
// 1. 只有 chromium 单浏览器 → 建议加上 firefox + mobile Chrome
// 2. 没有 webServer 自动启动配置
// 3. 没有 globalSetup 做登录态复用

// 建议改进：
export default defineConfig({
  testDir: './e2e',
  timeout: 60000,
  retries: 2,                         // CI 中增加重试
  workers: 1,                         // 避免并行干扰
  globalSetup: './e2e/global-setup.js', // 登录态复用
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:5174',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
  },
  webServer: {                        // 自动启停
    command: 'npm run preview',
    url: 'http://localhost:5174',
    reuseExistingServer: true,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox',  use: { ...devices['Desktop Firefox'] } },
    { name: 'mobile',   use: { ...devices['Pixel 5'] } },
  ],
});
```


## 6. 专项测试

### 6.1 性能测试

| 场景 | 工具 | 指标 | 频率 |
|------|------|------|------|
| 前端 Lighthouse | Playwright + Lighthouse | FCP < 1.5s, LCP < 2.5s, TBT < 200ms | 每次构建 |
| API 响应时间 | pytest + time 断言 | 关键 API P95 < 500ms | CI 门禁 |
| Worker 背压 | 模拟 50 并发任务 | 队列不爆炸，内存不泄漏 | 发版前 |
| 子进程泄漏 | 跑 100 轮 Agent 后 ps aux | 无僵尸进程 | 发版前 |

### 6.2 安全测试（建议用专业工具）

| 项 | 工具 | 优先级 |
|----|------|--------|
| CSRF 防护验证 | pytest + 手动构造 | P0 |
| Session 固定攻击 | Burp Suite / ZAP | P1 |
| XSS 注入 | Burp Suite / ZAP | P1 |
| SQL 注入 | sqlmap | P1 |
| 依赖漏洞扫描 | `pip-audit` / `npm audit` | P1 |
| 代码安全扫描 | `bandit`（已有） | P0 |

### 6.3 视觉回归测试

| 页面 | 视口 | 工具 |
|------|------|------|
| 登录页 | Desktop / Mobile | Playwright screenshot + pixelmatch |
| Dashboard | Desktop | Playwright screenshot |
| TaskGraph | Desktop | Playwright screenshot |
| AdminView | Desktop | Playwright screenshot |

### 6.4 可访问性测试

- **目标**：WCAG 2.1 AA
- **工具**：axe-core（集成到 Playwright test）
- **覆盖**：登录页 / Dashboard / 任务页 / 对话页
- **检查项**：颜色对比度、键盘导航、ARIA 标签、屏幕阅读器友好


## 7. CI/CD 集成建议

```
┌──────────────────────────────────────────────────┐
│                    GitHub Actions                  │
│                                                    │
│  PR 提交                                           │
│  ├── lint (ESLint + flake8)                       │
│  ├── pytest (单元 + 集成，含 coverage 报告)         │
│  ├── vitest (前端单元)                              │
│  ├── bandit + pip-audit + npm audit               │
│  └── Playwright E2E (仅 chromium，关键路径 5 条)    │
│                                                    │
│  merge to main                                     │
│  ├── 全量 Playwright (3 browsers)                  │
│  ├── Lighthouse 性能门禁                            │
│  └── 视觉回归截图对比                                │
└──────────────────────────────────────────────────┘
```

**门禁标准**：
- 单元测试覆盖率 ≥ 80%
- E2E 0 失败
- Lighthouse Performance ≥ 80
- bandit 0 HIGH/CRITICAL


## 8. 测试数据管理

| 策略 | 详情 |
|------|------|
| **测试数据库** | 使用 SQLite `:memory:` 或 dedicated test db |
| **Factory** | 用 `factory_boy`（已有依赖）代替 fixture 手写数据 |
| **Redis** | 测试用独立 Redis DB number（如 db=15） |
| **Hermes/DeepSeek mock** | 单元/集成测试中用 unittest.mock 替换 hermes 调用，E2E 中用 Playwright route 拦截 |
| **数据清理** | 每个 test class 前后 `setUp`/`tearDown` 清理 |


## 9. 分阶段落地路线图

### Phase 0 — 立即补齐（本周，零成本）

```
□ 修复 Playwright 已有 smoke 测试中的 selector 问题
  （部分测试依赖 .chat-sidebar / .view-title 可能已变更）
□ 补充 auth E2E 6 条（登录/注册/登出/权限）
□ 跑一次 dependency audit（pip-audit + npm audit）
```

### Phase 1 — 核心覆盖（2 周）

```
□ 后端 Model 单元测试 25 条
□ plan_parser + orchestrator 单元测试 15 条
□ 认证 API 集成测试 10 条
□ 前端 ErrorBoundary + api.js 单元测试
□ 关键路径 E2E 补充到 15 条
```

### Phase 2 — 全面加固（第 3-4 周）

```
□ View/API 层测试补齐
□ Redis Worker 集成测试
□ 前端组件测试补齐
□ a11y 扫描自动化
□ 视觉回归基线建立
□ CI pipeline 搭建
```

### Phase 3 — 性能 & 安全（第 5-6 周）

```
□ Lighthouse 性能门禁
□ Worker 背压测试
□ 子进程泄漏测试
□ ZAP/Burp 安全审计（外援）
```


## 10. 对现有测试的评估

| 现有项 | 评价 | 
|--------|------|
| pytest 46/46 通过 | ✅ 不错的基础，但需确认覆盖了核心引擎 |
| Playwright smoke 6 条 | ⚠️ 偏 UI 渲染验证，缺少认证和业务流 |
| Vitest 框架已配置 | ⚠️ 未见实际测试文件（src/test 目录为空） |
| pytest markers 分类 | ✅ slow/integration/smoke 标签合理 |
| bandit 安全扫描 | ✅ 已集成 |
| coverage.py | ✅ 已集成 pytest-cov |

**关键缺口**：
1. **认证流程 E2E 为零** — 这是最高风险的缺失
2. **核心引擎 plan_parser/orchestrator 测试需确认覆盖度**
3. **前端单元测试空白**
4. **无 CI pipeline**
5. **无可访问性测试**
6. **Redis Worker 集成测试未知**


## 11. 风险提示

| 风险 | 应对 |
|------|------|
| Hermes CLI / DeepSeek API 不稳定 | 测试中用 mock，E2E 用 route 拦截 |
| 子进程僵尸进程 | 压测中监控 ps aux |
| Worker 20 并发瓶颈 | 背压测试验证 |
| CSRF/Session 安全 | Django 测试 client 严格校验 |
| SQLite 并发写锁 | 集成测试中模拟并发请求 |

---

*本方案由端测测基于项目代码结构分析制定，具体用例代码实现可随时启动。*
