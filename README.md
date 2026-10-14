# write-wechat-article

> 让 AI agent 帮你把公众号推文从零做到后台草稿：实测产品 → 写正文 → 截图配图 → 排进图文编辑器 → 校验保存。
>
> An agent skill that turns raw material into a ready-to-publish WeChat Official Account draft — copy, screenshots, layout and all.

跨工具通用：**Qoder / Claude Code / Codex / OpenCode** 都能用。技能本身与具体 agent 工具解耦，唯一要求是有一个"能在浏览器里执行 JS 并上传文件"的驱动。

---

## 它解决什么问题

用 agent 写公众号文章的常见断点，从来不是"写不出来"，而是：

- 写出来的内容**没实测过**，是模型脑补的功能描述；
- 截图躺在本地，**手动一张张拖进编辑器**、一张张调位置；
- 稿子灌进编辑器后**被改得面目全非**，没人知道原始文本是否完整；
- 每次写都要重新交代"我的账号是什么类型、有什么限制、别用什么词"。

这个技能把整条链路固化下来，并针对公众号编辑器（ProseMirror）踩过的坑写了一套确定性的操作配方：

| 阶段 | 做什么 |
|---|---|
| Phase 0 | 读账号配置，确认平台约束（主体类型决定能写什么） |
| Phase 1 | 用测试账号**亲自跑一遍产品**，边跑边截图，记录真实 bug 与付费边界 |
| Phase 2 | 选风格 preset 写正文母本（Markdown），过一遍去 AI 味清单 |
| Phase 3 | 整篇灌进公众号图文编辑器，写标题与摘要，先存一次草稿 |
| Phase 4 | 截图批量上传进微信素材库（走编辑器隐藏的本地文件 input） |
| Phase 5 | 由脚本生成"图片落位计划"，把图**按锚点**排进正文，校验文本零改动 |
| Phase 6 | 目视检查 + 历史版本确认，交付草稿 URL |
| Phase 7 | 出 900×383 封面（模板 + 多方案让用户挑） |

## 为什么不用官方 API

公众号的**素材 / 草稿接口只对已认证主体开放**。个人号、未认证订阅号拿不到这些接口，只有浏览器里有登录态。所以本技能走的是浏览器自动化路线 —— 这也是它存在的原因，而不是重复造轮子。

如果你的账号已认证，技能里也明确写了：**优先走官方 API**，别用浏览器。

## 前置条件

- 一个检测到的浏览器驱动（任选其一）：
  - `chrome-devtools-mcp` 系 MCP（Qoder / Claude Code 里常见）
  - Playwright MCP
  - 自写的 Node + Playwright / Puppeteer 脚本
  - 判据和接法见 `skills/write-wechat-article/references/browser-driver-adapter.md`
- Python 3.8+，脚本只依赖 `Pillow`（`pip install pillow`）
- 公众号后台**已登录**的浏览器会话

## 安装

```bash
git clone <this-repo> wechat-article-skill
cd wechat-article-skill/skills/write-wechat-article
python scripts/install.py                  # 装到所有检测到的工具
```

常用变体：

```bash
python scripts/install.py --tools claude,codex   # 只装指定工具
python scripts/install.py --local                # 装到当前项目（./.claude/skills 等）
python scripts/install.py --dry-run              # 只看会装到哪，不动文件
python scripts/install.py --force                # 覆盖已存在的副本
```

装完让工具重新加载：Qoder 运行 `/skills reload`；Claude Code 重启会话或用 `/skills`；Codex 重启。

## 快速上手

```bash
# 1. 在你的文章工作目录里放一份账号配置
cp <skill>/assets/account.config.template.json ./wechat-article.config.json
#    填上账号类型、产品链接、关键词回复、措辞禁忌

# 2. 正常写文章，截图存成 images/NN-模块-说明.png（NN 是两位序号 = 阅读顺序）
#    在母本正文里，图片位置直接写 Markdown 图片标记：
#    ![模块导航](images/05-编辑器-模块导航.png)

# 3. 产出落位计划
python <skill>/scripts/make_plan.py article-你的文章.md images/ > plan.json
python <skill>/scripts/build_layout_js.py plan.json > layout.txt
#    把 layout.txt 里的 CALL 1 / 2 / 3 分别执行（配方见 references/mp-editor-automation.md）
```

示例可以从 `examples/` 开始：那里的文章带完整图片标记，可以整条脚本链路跑通。

## 目录结构

```
skills/write-wechat-article/
├── SKILL.md                       # 技能入口（agent 读的第一个文件）
├── references/
│   ├── platform-rules.md          # 微信平台硬限制（与账号无关）
│   ├── writing-guide.md           # 通用文章骨架、口吻、排版细则
│   ├── styles/
│   │   ├── tool-review.md         # preset：工具深度评测 / 完整教程
│   │   └── tips-list.md           # preset：效率技巧 / 清单合集
│   ├── humanizer-zh.md            # 去 AI 味检查清单
│   ├── browser-driver-adapter.md  # 跨工具适配层（驱动怎么接）
│   └── mp-editor-automation.md    # 编辑器自动化全量配方（踩坑记录）
├── assets/
│   ├── cover-template.html        # 900×383 封面模板（占位符可直接替换）
│   └── account.config.template.json
└── scripts/
    ├── image_meta.py              # 批量取图片宽高 / ratio（依赖 Pillow）
    ├── make_plan.py               # 由 Markdown 图片标记生成落位计划
    ├── build_layout_js.py         # 由落位计划生成可执行 JS（含锚点校验）
    └── install.py                 # 安装 / 同步脚本
```

## 几个关键设计

**跨工具的最小公约数。** `SKILL.md` 的 frontmatter 只有 `name` + `description` —— 这是 Qoder、Claude Code、Codex 都能吃下的最小集合。额外的字段（`when_to_use`、`allowed-tools`）会在某些工具里解析失败，所以刻意不用。

**驱动解耦。** 所有自动化细节都抽象成四个原语：执行页面 JS、上传本地文件、导航、点击。技能不假设你用的是哪个 MCP，`browser-driver-adapter.md` 给每个驱动系列列了接法。

**图随文走（Markdown 图片标记）。** 母本里的图片位置直接写成标准 Markdown 图片标记，脚本从标记处顺着往上找**全文唯一**的段落当锚点。锚点不唯一或顺序不对时脚本**拒绝执行**并告诉你哪里错了，而不是猜一个位置把图硬塞进去。

**文本零改动校验。** 排图前后会用一段 JS 比对正文块数、文本长度、标题数和表格数 —— 全部不变、只有图片数增加，才算排布成功。不一致时提供 one-shot 回滚。

**账号数据不进技能。** 账号名、主体类型、产品链接、措辞禁忌都放在用户工作目录的 `wechat-article.config.json` 里。技能本身不含任何具体账号信息，可以直接开源。

## 已知限制

- **封面弹窗只对真人点击响应**：合成点击与 CDP 的受信任点击都无法唤出封面上传弹窗（实测）。封面必须人工点一下，技能里也明确写了这一点，不要反复重试。
- **发布前置条件**：账号未实名 + 未设置头像名称时，草稿**保存得了但发布不了**，原创开关也无法点击。这是平台限制，不是自动化问题。
- **脚本执行环境有硬超时**：实测约 15s（不同驱动可能不同）。所以配方强制"一次调用只做一件事"—— 超时被放弃的异步脚本会继续改页面，合并调用会很难排查。
- **配方绑的是当前编辑器实现**：ProseMirror 结构、`mmbiz` 图片粘贴格式、隐藏 input 的位置都可能随平台改版变化。遇到失效先看 `mp-editor-automation.md` 的定位表，再决定要不要重新探。

## 故障排查

先看 `skills/write-wechat-article/SKILL.md` 的失败模式速查表，以下是最高频的几条：

| 症状 | 原因 | 处置 |
|---|---|---|
| paste 不被消费、焦点不对、删除无效 | 版本冲突弹窗后会话变只读 | 拦 `beforeunload` 后重开编辑器 URL |
| 图片粘进去消失了 | 粘的是 `<section>` 标签 | 改成 `<p><img …></p>` |
| 内容重复 / 位置漂到文末 | `focus()` 在 `addRange()` 之后 | 交换顺序 |
| 排图脚本返回 `REJECTED` | 锚点文本在全文中不唯一 | 改母本或 `plan.json`，不要绕过校验 |
| 打开草稿报「系统错误(200004)」 | URL 参数不全 | 用保存时返回的完整 URL |

## License

MIT —— 见 [LICENSE](LICENSE)。
