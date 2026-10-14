# 跨工具浏览器驱动适配

本 skill 的自动化配方是**页面内 JS**，不绑定任何一家工具。换工具时只需把下面四个"原语"换成对应驱动的叫法。

## 先判断驱动够不够用

三条全满足才能跑完整流程：

1. **能在已登录的公众号后台页面里执行任意 JS**（必需 —— 正文写入、图片排布、校验全靠它）
2. **能给 `<input type=file>` 塞本地文件路径**（上传截图必需）
3. **能导航到指定 URL**（重开会话必需）

第 1 条不满足就别硬做：退化成"让用户手动粘贴"的成本比换驱动高得多。

## 原语对照表

| 原语 | chrome-devtools 系 MCP | Playwright MCP | 无 MCP：Node + Playwright |
|---|---|---|---|
| 执行页面 JS | `evaluate_script` | `browser_evaluate` | `await page.evaluate(fn)` |
| 页面结构快照 | `take_snapshot` | `browser_snapshot` | `page.accessibility.snapshot()` |
| 截图 | `take_screenshot` | `browser_take_screenshot` | `await page.screenshot({path})` |
| 上传文件 | `upload_file`（先取快照拿元素 id） | `browser_file_upload` | `await input.setInputFiles(path)` |
| 导航 | `navigate_page` | `browser_navigate` | `await page.goto(url)` |
| 点击元素 | `click` | `browser_click` | `await locator.click()` |
| 按键 | `press_key` | `browser_press_key` | `await page.keyboard.press(key)` |
| 等待 | `wait_for` | `browser_wait_for` | `await page.waitForTimeout(ms)` |

> 本 skill 的配方文字按 **chrome-devtools 系** 写（`evaluate_script` / `take_snapshot` / `upload_file`）。Playwright MCP 各家版本工具名略有差异，装好后以实际暴露的名字为准，语义一一对应。

## 各工具的接法

- **Qoder / Claude Code**：装 chrome-devtools 或 Playwright 的 MCP server 即可，配方可直接照抄。
- **Codex**：同样走 MCP；若版本不支持浏览器 MCP，用下面的纯脚本路径。
- **纯脚本路径**（任何能跑 Node 的工具都行）：

```bash
# 方案 A：连到用户已经登录好的 Chrome（推荐）
# 让用户用调试端口启动一次（Chrome 完全退出后执行）：
#   chrome.exe --remote-debugging-port=9222
npx playwright@latest run-server --cdp-endpoint http://127.0.0.1:9222

# 方案 B：独立 profile，需要用户扫码登录一次，之后复用
npx playwright@latest open --channel chrome --user-data-dir ./.mp-profile https://mp.weixin.qq.com
```

方案 A 不改用户的登录状态，是首选。方案 B 首次要扫码，但更稳（不受用户手动关页面影响）。

## 与工具无关的部分

这些**不要**因为换工具而改写：

- `scripts/image_meta.py`、`scripts/make_plan.py`、`scripts/build_layout_js.py`（纯本地，输出的是页面 JS）
- `references/mp-editor-automation.md` 里的 JS 配方本体、DOM 选择器、只读锁诊断
- `references/platform-rules.md`、`references/writing-guide.md`、风格 preset

## 工具特有的坑

- **浏览器窗口必须在前台可见**（宿主内嵌浏览器最容易忽略）。`document.visibilityState === "hidden"` 时：截图报 `NATIVE_BROWSER_VIEWPORT_UNAVAILABLE`；ProseMirror **根本不初始化**，快照里 `.ProseMirror` 数量为 `0`。两种表现都会被误判成"驱动坏了"或"粘贴姿势不对"，然后一头扎进 §6 只读锁的排查。**动手前先读一次 `document.visibilityState`，非 `visible` 就请用户把浏览器面板切到前台**，不要开始试别的插入方法。
- **`evaluate_script` 类接口普遍只接受一个 `function` 参数**：多传 `uid` 等键会被拒（`params must NOT have additional properties`）。需要传参就写进函数体，或先挂到 `window` 上再在下次调用里读。
- **超时是硬限制（本环境 15s）**：被放弃的异步脚本**会继续在页面里跑并改文档**。所以一次调用只做一件事，超时后先确认页面静默再动手。
- **不同驱动的返回值序列化不同**：有的把 `DOMRect` 字段变成 `0`（需 `Number()` 转换），有的不支持返回 DOM 节点。**返回值只用字符串/数字/布尔的普通对象**，用 `JSON.stringify` 包一层最省事。
- **快照大小**：页面结构读取接口在长文页面会返回几百行。给正文容器设 `visibility:hidden` 可裁掉（`aria-hidden` 无效），用完还原。
