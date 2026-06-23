#!/usr/bin/env python3
"""批量翻译技能 - 修复版：json.loads(resp.read()) + 增加延迟"""
import json, urllib.request, time

API = "http://localhost:8001/api/skills"

TRANS = {
    "dogfood": ("Dogfood：Web 应用系统化 QA 测试", "使用浏览器工具集对 Web 应用进行系统化探索性 QA 测试，导航、交互、抓取证据、生成问题报告。"),
    "songwriting-and-ai-music": ("AI 歌曲创作与音乐生成", "歌曲创作指南和 Suno AI 音乐提示词技巧。艺术创作无定式，规则是用来打破的。"),
    "baoyu-comic": ("知识漫画创作器", "改编自 baoyu-comic，支持教育类、传记类、教程类知识漫画的生成。"),
    "ascii-video": ("ASCII 视频制作流水线", "将视频/音频转换为彩色 ASCII 艺术 MP4/GIF，支持终端风格、字符画动画、复古文字可视化。"),
    "popular-web-designs": ("热门 Web 设计系统", "54 种真实世界设计系统（Stripe、Linear、Vercel 等）作为 HTML/CSS 模板随时可用。"),
    "manim-video": ("Manim 数学动画视频", "使用 Manim CE 生成数学/算法动画视频，3Blue1Brown 风格，支持几何图形和公式推导。"),
    "baoyu-article-illustrator": ("文章配图生成器", "为文章自动生成类型×风格×调色板一致的配图。改编自 baoyu-article-illustrator。"),
    "ascii-art": ("ASCII 艺术字", "多种 ASCII 艺术工具：pyfiglet、cowsay、boxes、图片转 ASCII，无需 API 密钥。"),
    "humanizer": ("Humanizer：去除 AI 写作痕迹", "识别并消除 AI 生成文本的痕迹，让文章听起来自然、有人味。基于维基百科 AI 写作特征指南。"),
    "pixel-art": ("像素艺术", "将任意图片转换为复古像素艺术，支持 NES、Game Boy、PICO-8 等经典配色方案。"),
    "sketch": ("Sketch 快速原型", "用 2-3 个设计变体快速探索 UI/UX 方向，适用于产品原型和设计评审。"),
    "architecture-diagram": ("架构图生成", "生成专业的暗色主题技术架构图，独立 HTML 文件 + 内联 SVG，适合云基础设施和数据流图。"),
    "design-md": ("DESIGN.md 规范", "Google DESIGN.md 开放规范的创作和验证工具，用于定义 AI 编码代理的设计约束。"),
    "excalidraw": ("Excalidraw 手绘风格图", "创建标准 Excalidraw JSON 格式的手绘风格图表（架构图、流程图、时序图），可拖入编辑。"),
    "claude-design": ("Claude Design（CLI/API 版）", "在 CLI/API 环境中执行设计工作，生成落地页、演示文稿、原型等一次性 HTML 工件。"),
    "baoyu-infographic": ("信息图生成器", "支持 21 种布局 × 21 种风格的信息图、可视化图表生成。改编自 baoyu-infographic。"),
    "touchdesigner-mcp": ("TouchDesigner MCP 集成", "通过 MCP 协议控制 TouchDesigner 实时图形引擎，操作 OP 参数和节点。"),
    "pretext": ("Pretext 创意演示", "使用 @chenglou/pretext 轻量 TypeScript 库构建创意浏览器演示，15KB 零依赖。"),
    "p5js": ("p5.js 创意编程", "使用 p5.js 生成创意编码作品、生成艺术、交互可视化、3D 动画和着色器效果。"),
    "comfyui": ("ComfyUI 图像生成", "通过 ComfyUI 生成图像、视频、音频和 3D 内容，支持安装、工作流管理和提示词优化。"),
    "jupyter-live-kernel": ("Jupyter 实时内核", "提供有状态的 Python REPL，变量跨轮次保持，适合迭代式数据探索和分析。"),
    "arxiv": ("arXiv 学术论文检索", "通过 arXiv 免费 REST API 检索学术论文：关键词、作者、分类和 ID 搜索。"),
    "polymarket": ("Polymarket 预测市场数据", "通过公共 REST API 查询 Polymarket 预测市场：市场列表、价格、订单簿、历史记录。"),
    "llm-wiki": ("Karpathy LLM 知识库", "构建和维护持久化知识库，以交联 Markdown 文件形式组织，支持增量查询。"),
    "blogwatcher": ("Blogwatcher 博客监控", "通过 blogwatcher-cli 追踪博客和 RSS/Atom 订阅源更新，支持自动发现和内容监控。"),
    "pokemon-player": ("宝可梦游戏玩家", "通过无头模拟器 + RAM 读取玩宝可梦游戏，实现自动化游戏操作。"),
    "minecraft-modpack-server": ("Minecraft 模组服务器", "搭建基于 CurseForge/Modrinth 的模组 Minecraft 服务器，支持服务包导入。"),
    "django-react-fullstack": ("Django + React 全栈开发", "使用 Django DRF REST API 后端 + React + Vite + Tailwind 前端构建全栈 Web 应用。"),
    "systematic-debugging": ("系统化调试", "四阶段根因调试方法论：先理解 Bug 再修复，避免随意修补引入新问题。"),
    "spike": ("Spike 技术验证", "通过一次性实验快速验证技术想法，在正式开发前确认方案可行性。"),
    "debugging-hermes-tui-commands": ("Hermes TUI 命令调试", "调试 Hermes 终端 UI 斜杠命令，涵盖 Python 注册、Gateway 桥接和 Ink UI 三层。"),
    "simplify-code": ("并行代码审查与清理", "三个并行审查员（安全、质量、风格）审查近期变更，自动修复并统一输出。"),
    "test-driven-development": ("测试驱动开发（TDD）", "红-绿-重构循环：先写测试再写代码。严格遵循测试先行、最小实现的原则。"),
    "subagent-driven-development": ("子代理驱动开发", "通过派发独立子代理执行实现计划，每个任务两阶段审查确保质量。"),
    "writing-plans": ("编写实现计划", "编写全面实现计划，假设零代码上下文，将任务拆分为可执行的步骤。"),
    "plan": ("Plan 模式", "先写可执行的 Markdown 计划到 .hermes/plan，再按计划执行。适用于复杂多步骤任务。"),
    "requesting-code-review": ("代码提交前验证", "自动化验证流水线：安全扫描、代码规范审查、自动修复。"),
    "hermes-s6-container-supervision": ("s6-overlay 容器监控", "修改、调试、扩展 s6-overlay 监控树，管理容器服务生命周期。"),
    "github-pr-workflow": ("GitHub PR 工作流", "完整的 PR 生命周期：分支→提交→PR→CI→审查→合并。gh CLI 优先。"),
    "codebase-inspection": ("pygount 代码库分析", "使用 pygount 分析：代码行数、语言分布、文件数量、代码与注释比。"),
    "github-code-review": ("GitHub 代码审查", "代码审查涵盖：代码风格、安全漏洞、性能问题、测试覆盖率。"),
    "github-auth": ("GitHub 认证配置", "配置 GitHub 认证：HTTPS Token、SSH 密钥、gh CLI 登录。"),
    "github-repo-management": ("GitHub 仓库管理", "克隆、创建、Fork、配置仓库，管理远程和 Release。gh CLI 优先。"),
    "github-issues": ("GitHub Issues 管理", "创建、搜索、分类、管理 Issues，支持标签和里程碑。"),
    "dspy": ("DSPy：声明式语言模型编程", "使用 DSPy 构建声明式 LM 程序，自动优化提示词，构建 RAG 系统。"),
    "weights-and-biases": ("Weights & Biases：ML 实验追踪", "使用 W&B 记录 ML 实验、超参数调优、模型注册、可视化仪表板。"),
    "huggingface-hub": ("HuggingFace CLI (hf) 参考", "hf 命令行完整参考：搜索、下载、上传模型和数据集到 HuggingFace Hub。"),
    "unsloth": ("Unsloth：高效微调", "2-5 倍加速 LoRA/QLoRA 微调，更低显存占用。基于官方文档。"),
    "axolotl": ("Axolotl：LLM 微调框架", "YAML 配置驱动的 LLM 微调，100+ 模型支持，LoRA/QLoRA/DPO 等方法。"),
    "obliteratus": ("OBLITERATUS：模型拒绝消除", "9 种 CLI 方法、28 个分析模块，消除 LLM 安全拒绝响应。"),
    "outlines": ("Outlines：结构化文本生成", "生成符合 JSON Schema/Regex/Pydantic 的结构化 LLM 输出。"),
    "himalaya": ("Himalaya 邮件 CLI", "通过 IMAP/SMTP 管理终端邮件：发送、搜索、读取、通知。"),
    "yuanbao": ("元宝群组互动", "在元宝群组中 @用户、查询群信息/成员，自动通过 Gateway 发送消息。"),
    "native-mcp": ("原生 MCP 客户端", "Hermes 内置 MCP 客户端，自动发现和注册远端 MCP 服务器工具。"),
    "meyo": ("觅游社区（Meyo）", "与 meyo123.com 交互：入驻、心跳、日记、体检、技能便利店下载。"),
    "xurl": ("xurl：X/Twitter CLI", "通过 xurl CLI 操作 X/Twitter：发帖、搜索、私信、媒体上传，v2 API。"),
    "remote-access": ("远程访问配置", "配置远程访问和 VPN 网络，让用户从外部访问 Hermes 主机。"),
    "webhook-subscriptions": ("Webhook 订阅", "创建动态 Webhook 订阅，让 GitHub/GitLab/Stripe/CI 等触发 Agent 运行。"),
    "headless-browser-automation": ("无头浏览器自动化", "在 Ubuntu 上搭建 Selenium + Chromium 无头环境，用于爬虫和 RPA。"),
    "obsidian": ("Obsidian 知识库", "文件系统优先的 Obsidian 操作：读取笔记、搜索内容、创建编辑 Markdown。"),
    "linear": ("Linear：Issue 管理", "通过 GraphQL API 管理 Linear Issue、项目和团队。"),
    "teams-meeting-pipeline": ("Teams 会议流水线", "Microsoft Teams 会议摘要：转录、总结、提取行动项。"),
    "ocr-and-documents": ("PDF 与文档提取", "从 PDF/扫描件提取文本：pymupdf、marker-pdf，保留结构和格式。"),
    "lark-cli-setup": ("lark-cli 配置管理", "多账户配置、OAuth 认证、权限范围、Profile 切换管理。"),
    "google-workspace": ("Google Workspace", "Gmail、Calendar、Drive、Docs、Sheets 操作，OAuth + CLI 封装。"),
    "nano-pdf": ("nano-pdf：自然语言编辑 PDF", "使用自然语言指令修改 PDF 文字、标题。"),
    "airtable": ("Airtable：数据库操作", "通过 REST API 操作 Airtable：记录 CRUD、过滤、批量更新。"),
    "powerpoint": ("PowerPoint 操作", "创建、读取、编辑 .pptx 文件：幻灯片、备注、模板。"),
    "notion": ("Notion", "两种方式操作 Notion：REST API 和 ntn CLI，页面、数据库、Markdown。"),
    "resume-screening": ("简历评估", "五关结构化评估：一票否决→硬性门槛→行业匹配→加分项→软实力→扣分项。"),
    "feishu-doc-create": ("创建飞书云文档", "三种方式创建飞书文档，优先级递减：lark-cli → API → 手动。"),
    "maps": ("地图技能", "基于 OSM/OSRM 的位置情报：地理编码、POI 搜索、路线规划、时区。"),
    "opencode": ("OpenCode CLI", "使用 OpenCode 作为自主编码 Worker，由 Hermes 编排。"),
    "claude-code": ("Claude Code 编排指南", "将编码任务委派给 Claude Code，由 Hermes 通过终端编排。"),
    "kanban-codex-lane": ("Kanban Codex 通道", "Hermes+Codex 双通道约定，Kanban Worker 专用配置。"),
    "codex": ("Codex CLI", "将编码任务委派给 OpenAI Codex CLI，支持功能和 PR 级开发。"),
    "hermes-agent": ("Hermes Agent 框架", "Nous Research 开源的 AI Agent，支持终端/消息平台/工具/技能系统。"),
    "maishou": ("买手 — 全网比价", "通过 maishou88.com 比价淘宝/京东/拼多多/抖音/快手/1688，带优惠券。"),
    "godmode": ("G0DM0D3 越狱技能", "使用 G0DM0D3 等方法绕过 LLM 安全过滤器。"),
    "openhue": ("OpenHue CLI", "通过终端控制 Philips Hue 灯光：开关、亮度、颜色、场景。"),
    "youtube-content": ("YouTube 内容工具", "字幕提取、摘要生成、主题分析。"),
    "songsee": ("songsee：音频可视化", "生成频谱图和多面板音频特征：Mel 频谱、色度图、MFCC。"),
    "gif-search": ("GIF 搜索（Tenor）", "通过 Tenor API 搜索和下载 GIF 动图。"),
    "spotify": ("Spotify", "控制 Spotify：播放、搜索、队列、播放列表管理。" ),
    "heartmula": ("HeartMuLa：开源音乐生成", "基于开源模型根据歌词+标签生成音乐，Apache-2.0。"),
    "python-debugpy": ("Python 调试器", "三种方式：pdb REPL、debugpy 远程 DAP、Node.js inspect。按场景选择。"),
    "hermes-agent-skill-authoring": ("编写 Skills（仓库内）", "在仓库内写 SKILL.md：frontmatter、验证器、结构规范。"),
    "node-inspect-debugger": ("Node.js Inspect 调试", "程序化驱动 V8 Inspector 协议进行 Node.js 调试。"),
}

def update_skill(slug, name, desc):
    data = {"name": name, "description": desc}
    req = urllib.request.Request(f"{API}/{slug}/", method="PATCH")
    req.add_header("Content-Type", "application/json")
    req.data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"error": f"HTTP {e.code}: {body[:120]}"}
    except Exception as e:
        return {"error": str(e)[:120]}

updated = 0
skipped = 0
not_found = []
total = len(TRANS)

for i, (slug, (name, desc)) in enumerate(TRANS.items()):
    result = update_skill(slug, name, desc)
    if "error" in result:
        err = result["error"]
        if "429" in err or "限流" in err:
            wait = 5
            print(f"  ⏳ 限流，等{wait}秒...", flush=True)
            time.sleep(wait)
            result = update_skill(slug, name, desc)
            if "error" in result:
                print(f"  ✗ {slug}: {result['error'][:80]}")
                skipped += 1
                if "404" in result['error']:
                    not_found.append(slug)
            else:
                updated += 1
        elif "404" in err:
            not_found.append(slug)
            skipped += 1
        else:
            print(f"  ✗ {slug}: {err[:80]}")
            skipped += 1
    else:
        updated += 1
    
    if (i+1) % 20 == 0:
        print(f"  进度: {i+1}/{total} (✓{updated} ✗{skipped})")
    
    time.sleep(1.5)  # 1.5秒间隔避免限流

print(f"\n{'='*50}")
print(f"完成！成功 {updated}/{total}，跳过 {skipped}")
if not_found:
    print(f"404 (slug不存在): {', '.join(not_found)}")
