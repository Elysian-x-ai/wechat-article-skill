---
name: write-wechat-article
description: 撰写微信公众号推文并自动化录入后台草稿：实跑产品取截图、按选定风格写正文、灌进图文编辑器、把截图上传进素材库并按锚点排进正文、校验零改文后保存草稿。当用户要求写公众号推文、把文章录入微信公众平台编辑器、给文章配图、做封面/摘要/标题，或提到公众号草稿、图文消息时使用。
---

# 写公众号推文

## Overview

产出一篇带配图的公众号草稿：实测产品 → 选风格写母本 → 截图 → 灌进图文编辑器 → 上传并排布图片 → 校验 → 保存草稿。

跨工具可用（Qoder / Claude Code / Codex / OpenCode）。**唯一外部依赖是"能在已登录的公众号后台页面里执行 JS 并上传文件"的浏览器驱动**，具体用哪个见 `references/browser-driver-adapter.md`；其余步骤都与工具无关。

图片写入和正文写入都是**脆弱操作**（ProseMirror 只认 paste 事件、有只读锁、脚本有 15s 硬超时），必须照 `references/mp-editor-automation.md` 的顺序执行，不要临场发挥。

## Phase 0 · 准备

1. **读账号配置**：在工作目录找 `wechat-article.config.json`（模板见 `assets/account.config.template.json`）。没有就先问用户，或用模板在项目里生成一份。
   - 里面放**账号相关的易变数据**：账号名、主体类型（个人/企业、是否认证）、关键词回复表、产品与链接、常见措辞禁忌。**不要把账号细节硬编码进本 skill。**
2. **确认约束**：按主体类型套 `references/platform-rules.md`。个人未认证订阅号的边界最窄（正文不能放站外链接、无小程序、无网页授权、发表前必须实名+头像名称），这一条直接决定文章怎么写。
3. **确认本期任务**：写哪个产品/主题、有没有测试账号、读者看完要做什么动作。
4. **确认浏览器**：后台已登录、拿到当前 URL 里的 `token`（token 会变，别复用旧值）。
   - 若账号是**已认证**主体，先查官方 API 能不能走草稿箱/素材接口 —— 能走就别用浏览器自动化。

## Phase 1 · 亲自跑一遍产品（不可跳过）

用用户提供的测试账号实际操作，按**用户真实使用顺序**走完整流程：注册/登录 → 主流程 → 产出物 → 边界情况。

- 每一步截图存到 `images/NN-模块-说明.png`（两位数前缀即阅读顺序）。
- 记录实测到的 bug、限制、付费边界 —— 这些是文章差异化的唯一来源。
- **未验证的功能一律不写**；付费边界要当场核对。
- 敏感凭据（测试密码等）不要写进任何文件、代码或总结。

## Phase 2 · 选风格，写母本

1. 按内容形态从 `references/styles/` 选一个 preset：
   - **工具深度评测 / 完整教程** → `styles/tool-review.md`（长文，3000–6000 字，按操作顺序分步）
   - **效率技巧 / 清单合集** → `styles/tips-list.md`（中短篇，条目式，可扫读）
   - 都不合适就用 `references/writing-guide.md` 里的通用骨架，并考虑新增一个 preset。
2. 写 `article-<slug>.md`：骨架、口吻、标题（≤64 字）、摘要（≤120 字）、排版细则见所选 preset 与 `writing-guide.md`。
3. 写完过一遍 `references/humanizer-zh.md` 的去 AI 味清单 —— 这一步不能省，中文长文最容易露机器味。

## Phase 3 · 灌入编辑器

按 `references/mp-editor-automation.md` §1–§2：打开/新建图文页 → Markdown 转 HTML → 整篇 `selectNodeContents` + paste 替换写入正文 → 写标题与摘要。

配方里最致命的顺序：**`focus()` 必须在 `addRange()` 之前**，反了会变成"追加"而不是"替换"。

写完立即 `保存为草稿`，记下返回 URL 里的 `appmsgid` 和**完整参数**（打开已存草稿必须带全，自己拼会报 200004）。

## Phase 4 · 上传截图

暴露隐藏的 本地上传 input → 逐张上传 → 删掉被 append 到正文末尾的图 → harvest 出每张图的 `src / data-imgfileid / data-w / data-ratio` 存成 `cdn.json`。步骤见 §3。

`data-imgfileid` 单调递增，用它确认上传顺序；**不要**解析 URL token（前缀有两种）。

## Phase 5 · 把图排进正文

脚本路径相对本 skill 目录。

1. `python scripts/image_meta.py images/` 打印每张图的 `w` / `ratio`（`data-ratio = h/w`）。
2. `python scripts/make_plan.py article-<slug>.md images/ > plan.json` 按 `NN-` 前缀自动配对章节，产出草稿落位计划。
3. **人工核对 `plan.json` 的 `after` 锚点**：必须是母本里**全文唯一**的段落文字；自动配对只在图片文件名能对上标题时可靠。
4. `python scripts/build_layout_js.py plan.json > layout.txt`，把 CALL 1 / 2 / 3 **分别**作为独立的"执行页面 JS"调用执行（一次一段，绝不合并 —— 15s 硬超时，被放弃的脚本会继续改文档）。
5. CALL 1 返回 `REJECTED missing=…/ambiguous=…` 时改 `plan.json` 重跑，**不要绕过校验**。
6. CALL 3 必须与 CALL 1 打印的 `expected` 基线一致（`textLen/h2/h3/table` 不变、`imgs` 增加）。不一致就执行 ROLLBACK 段。

## Phase 6 · 校验与保存

跑一次 CALL 3 记录终态，再目视检查渲染。确认无误后 `保存为草稿`，在「历史版本」里看到「手动保存」时间戳才算成功。

**默认不点发表、不声明原创**，除非用户明确要求且平台前置条件（实名/头像/名称）已满足。

## Phase 7 · 封面与交付

1. 用 `assets/cover-template.html` 出封面：**900×383**，替换占位符即可，然后截图/导出成 PNG。
2. **出 2–3 个变体**（换标题措辞或换配色）让用户挑，比只给一张省一轮返工。
3. 封面弹窗**只对真人点击响应**（见 §8）—— 告诉用户"封面要你点一下封面区域再选图"，不要反复重试。
4. 交付报告：草稿 URL（完整参数）、文章骨架、**图片落位表**（哪张图在哪个小节后）、没用上的截图及原因、还卡在哪（实名/头像名称/封面）。

## 失败模式速查

| 症状 | 原因 | 处置 |
|---|---|---|
| paste 返回未消费、`focus()` 后焦点不在编辑器、删除无效 | 版本冲突弹窗后会话变只读 | 拦 `beforeunload` → 重新导航到完整编辑 URL 重开会话 |
| 图片粘进去没了 | 粘的是 `<section>` | 改成 `<p><img …></p>` |
| 内容重复 / 位置漂到文末 | `focus()` 在 `addRange()` 之后 | 交换顺序；必要时整篇重建 |
| 脚本超时 | 一次调用做了多件事 | 一次一段；超时后等页面静默、重读状态再动手 |
| 上传报「No snapshot found」/ uid 失效 | uid 来自旧快照 | 重新取页面结构/快照拿新 uid |
| 打开草稿报「系统错误(200004)」 | URL 少参数 | 用保存后返回的完整 URL |
| 页面结构读取过大 | 正文全在可访问性树里 | 正文 `visibility:hidden`（`aria-hidden` 无效），用完还原 |

## Resources

- `references/platform-rules.md` — 微信平台硬限制（与账号无关），含个人未认证号的边界
- `references/writing-guide.md` — 通用文章骨架、口吻、标题/摘要规则、排版细则、产出物清单
- `references/styles/tool-review.md` — 风格 preset：工具深度评测 / 完整教程
- `references/styles/tips-list.md` — 风格 preset：效率技巧 / 清单合集
- `references/humanizer-zh.md` — 去 AI 味检查清单（写完必过）
- `references/browser-driver-adapter.md` — 跨工具适配：用哪种浏览器驱动执行页面 JS / 传文件
- `references/mp-editor-automation.md` — 编辑器自动化全量配方（URL、DOM 定位、paste 原语、上传、图片排布、只读锁、工具约束）
- `assets/cover-template.html` — 900×383 封面模板（占位符可直接替换）
- `assets/account.config.template.json` — 账号配置模板，复制到工作目录改名 `wechat-article.config.json`
- `scripts/image_meta.py` — 批量取 `data-w` / `data-ratio`（依赖 Pillow）
- `scripts/make_plan.py` — 按 `NN-` 前缀把截图配对到母本章节，产出草稿 `plan.json`
- `scripts/build_layout_js.py` — 由 `plan.json` 生成 CALL 1/2/3 + ROLLBACK，含锚点缺失与歧义校验
- `scripts/install.py` — 把本 skill 分发安装到各工具的技能目录
