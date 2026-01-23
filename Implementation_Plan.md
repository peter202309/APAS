# APAS 项目实施计划 (Implementation Plan)

## 🎯 项目目标
构建生产级的航空价格自动化采集与分析系统，重点针对 ITA Matrix 平台进行 MU（东航）价格分析。

## 👥 角色指派 (Virtual Team)
- **Agent Manager**: Antigravity (负责任务编排与集成)
- **Agent A (Scraper)**: Browser Sub-agent (负责 Playwright 采集内核)
- **Agent B (Backend)**: Antigravity (负责 FastAPI & 数据模型)
- **Agent C (Frontend)**: Antigravity (负责 React 可视化界面)

## 📊 任务进度追踪

### 第一阶段：采集内核与基础后端 (进行中)
- [x] **Task 1: ITA Matrix 站点侦察与原型验证** (Assigned to: Agent A)
    - 验证 Playwright 在 ITA Matrix 的填表、搜索和日历加载。
    - 提取第一个月的价格数据。 (已完成: 成功抓取 Feb 2026 数据)
- [x] **Task 2: 后端基础设施建设** (Assigned to: Agent B)
    - 初始化 FastAPI 结构。 (已完成)
    - 定义 API 接口协议与数据存储 Schema。 (已完成)
    - 搭建基础项目骨架。 (已完成)
    - 集成 CORS 支持与正式爬虫引擎。 (已完成)

### 第二阶段：UI 开发与系统集成 (进行中)
- [x] **Task 3: React 仪表盘开发** (Assigned to: Agent C)
    - 初始化 Vite + React + Tailwind 项目。 (已完成)
    - 设计高感度侧边栏与 Dashboard 骨架。 (已完成)
    - 实现任务发布表单与 API 联调。 (已完成)
    - 实现基于终端风格的实时日志轮询。 (已完成)
- [ ] **Task 4: 分布式任务队列配置**

### 第三阶段：AI 分析与日志审计
- [ ] **Task 5: AI 策略分析模块集成**
- [ ] **Task 6: 操作日志与备份功 能**

---

## 🛠️ 当前状态日志
- **2026-01-21**: 确认实施方案，创建实施计划。正式启动 Task 1。
- **2026-01-21**: Task 1 完成。成功探索 ITA Matrix 交互逻辑（Click->ESC->Type），并验证了日历数据提取能力。开始 Task 2。
- **2026-01-22**: 爬虫稳定性优化 - 实现 CDP 持久化连接
  - 创建 `start_chrome_debug.bat` 用于启动调试模式 Chrome（端口 9223）
  - 修改 `ita_engine.py` 从 `launch_persistent_context` 改为 `connect_over_cdp`
  - 优化表单填写顺序：Routing Codes 移至 Origin/Destination 之后
  - 实现 Tab Navigation 策略（Extension Codes → Tab → Routing Codes）
  - 添加 Human-in-the-Loop 机制：自动失败时等待 15 秒人工介入
- **2026-01-23**: 待优化 - 减少 Routing Codes 自动重试次数，更快触发人工介入

## 🔧 关键技术决策
### 浏览器连接策略
- **问题**：临时浏览器窗口无法保存登录状态和 UI 偏好设置
- **解决**：使用 CDP (Chrome DevTools Protocol) 连接到用户预先启动的 Chrome 实例
- **优势**：保留登录状态、记住 "Advanced Controls" 展开状态、更稳定的自动化

### Routing Codes 输入策略演进
1. ~~直接选择器定位~~ → 滚动不稳定
2. ~~可见性检测 + 点击~~ → 仍有定位问题
3. **Tab Navigation** → 点击 Extension Codes 后按 Tab 键聚焦
4. **Human-in-the-Loop** → 失败时请求人工协助

## 📝 下次会话待办
- [ ] 减少 Routing Codes 自动尝试时间（15s → 3-5s）
- [ ] 测试完整的单程/往返流程稳定性
- [ ] 优化数据提取的月份过滤逻辑
