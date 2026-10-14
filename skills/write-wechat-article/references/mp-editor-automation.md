# 公众号图文编辑器自动化手册

微信公众平台后台的**驱动无关**配方：下面的选择器和 JS 在任何能执行页面 JS 的浏览器驱动里都成立。驱动怎么选、原语怎么换名见 `browser-driver-adapter.md`。

正文和图片写入是**脆弱操作**，严格按顺序执行。

## 0. 会话与页面

**新建图文**：`https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2&action=edit&isNew=1&type=77&token=<TOKEN>&lang=zh_CN`

**打开已存草稿**：必须带保存后返回的**完整参数**（含 `token`、`timestamp`、`appmsgid`）。自己拼 `?t=media/appmsg_edit&action=edit&type=77&appmsgid=xxx` → 「系统错误(200004)」

```
https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit&action=edit&reprint_confirm=0&timestamp=<ms>&type=77&appmsgid=<id>&token=<token>&lang=zh_CN
```

**离开页面**：MP 有未保存拦截。先注册 capture 阶段 `beforeunload` 并 `stopImmediatePropagation()`，再 `navigate_page`。

**`token` 会变**：菜单/回复页与图文页的 token 不同，从当前 URL 里取，不要复用旧值。

## 1. DOM 定位（固定）

| 目标 | 选择器 |
|---|---|
| 标题 | `.ProseMirror`[0]（`data-placeholder="请在这里输入标题"`），上限 **64 字** |
| 正文 | `.ProseMirror`[1] |
| 摘要 | `textarea#js_description`，`max-length="120"`，上限 **120 字**；留空则抓正文开头 |
| 作者 | 普通 input，原生 value setter + `input`/`change` 即可 |
| 图片上传 input | `.js_img_dropdown_menu input[type=file]`，`accept` = gif/jpeg/jpg/png/svg/webp |
| 封面区 | `.js_cover_btn_area`（文本「拖拽或选择封面」） |

## 2. 写入正文（唯一可靠原语）

ProseMirror 只认 paste 事件。`fill` 会把 `\n` 压成空格；合成 `beforeinput`、`execCommand('insertText')` 被忽略；`KeyboardEvent('keydown', Enter)` 只产生空段落。

```js
// 整篇替换：focus → 全选（不 collapse）→ dispatch paste
pm.focus();
await sleep(500);
const rg = document.createRange(); rg.selectNodeContents(pm);
const s = getSelection(); s.removeAllRanges(); s.addRange(rg);
await sleep(400);
const dt = new DataTransfer();
dt.setData('text/html', html);            // 富文本走 text/html
dt.setData('text/plain', 'rebuild');
const consumed = !pm.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
```

- **顺序致命**：必须 `focus()` 在**前**、`addRange()` 在**后**。反了选区会被重置到文末，paste 变成追加 → 内容重复插入。
- `consumed` 为 `false` 才代表被编辑器消费；返回 `true` = 没生效（见 §6 只读锁）。
- 追加到文末：`rg.selectNodeContents(pm); rg.collapse(false)`；插到开头 `collapse(true)`。
- Markdown 转 HTML 后再粘。已验证保留：`h2/h3/p/strong/em/blockquote/ul/ol/table`。
- 整篇重建是可靠兜底：先粘一小段占位 HTML（整体替换），再按 chunk 依次 `collapse(false)` 追加。
- 删多余段落：`rg.selectNode(el)` + `document.execCommand('delete')` —— 在 MP 里**有效**（`insertText` 无效），同样要求 `pm.contentEditable === "true"`。

**标题/摘要**不是 ProseMirror 粘贴问题：标题 `.ProseMirror`[0] 用同样的 paste 配方（`text/plain`）；摘要用原生 value setter + `input`/`change`。

## 3. 上传截图进图片空间

工具栏的 本地上传 input 藏在 `ul.tpl_dropdown_menu.js_img_dropdown_menu{display:none}` 里，**快照中不存在**。把它整条祖先链强制可见后才会以 `button "选择文件"` 出现：

```js
const inp = document.querySelector('.js_img_dropdown_menu input[type=file]') || document.querySelector('input[type=file][name=file]');
let p = inp;
while (p && p !== document.body) {
  const cs = getComputedStyle(p);
  if (cs.display === 'none') p.style.setProperty('display', 'block', 'important');
  if (cs.visibility === 'hidden') p.style.setProperty('visibility', 'visible', 'important');
  if (parseFloat(cs.opacity) < 1) p.style.setProperty('opacity', '1', 'important');
  p = p.parentElement;
}
const s = inp.style;
s.setProperty('display', 'block', 'important'); s.setProperty('opacity', '1', 'important');
s.position = 'fixed'; s.left = '10px'; s.top = '150px'; s.zIndex = '999999'; s.width = '260px'; s.height = '32px';
```

然后 `take_snapshot` → 找 `button "选择文件"` 的 uid → `upload_file({uid, filePath})`，**一张一次调用**。

- uid 每次快照重置（`1_x`/`2_x`）；报「No snapshot found」就重新快照取新 uid。
- 上传成功后编辑器会把图 **append 到正文末尾**，必须清掉：

```js
const first = [...pm.children].find(c => c.tagName === 'SECTION' && c.querySelector('img'));
pm.focus(); await sleep(200);
const rg = document.createRange(); rg.setStartBefore(first); rg.setEndAfter(pm.lastElementChild);
const s = getSelection(); s.removeAllRanges(); s.addRange(rg);
document.execCommand('delete', false, null);
```

- 用 `data-imgfileid` 判断上传顺序（从最小值单调递增），**不要**解析 URL 里的 token。

## 4. 把图排进正文（用 `scripts/build_layout_js.py`，不要手写）

**粘贴形态必须是 `<p><img …></p>`**：直接粘 `<section nodeleaf><img></section>` 会被 schema **静默丢弃**。编辑器会自己把 `<p>` 规范化成 `<section nodeleaf><img class="rich_pages wxw-img" contenteditable="false">`。

```html
<p><img src="https://mmbiz.qpic.cn/.../0?wx_fmt=png&from=appmsg" data-imgfileid="100000002" data-ratio="0.7745098039" data-w="918" data-type="png"></p>
```

`data-ratio = h / w`，`data-w` = 原图宽。用 `scripts/image_meta.py <images_dir>` 批量取。

一次落位的做法（文字零改动，已实测 11 张图、textLen 前后一致）：
1. 备份 `pm.innerHTML`；
2. 拷进离屏 div，删掉所有含 img 的顶层块 + `img.ProseMirror-separator` + `br.ProseMirror-trailingBreak`；
3. 按**锚点段落文本**在离屏副本里 `anc.after(<p><img></p>)`；
4. 整篇 `selectNodeContents` + paste 替换。

`scripts/build_layout_js.py plan.json` 会生成 CALL 1（构建）/ CALL 2（粘贴）/ CALL 3（校验）/ ROLLBACK 四段 JS，逐段作为独立的 `evaluate_script` 调用执行。锚点文本必须**全文唯一**，脚本化生成时会校验缺失和歧义并拒绝执行。

CDN URL 前缀有 `sz_mmbiz_png` 与 `mmbiz_png` 两种，别假设固定。

## 5. 保存与校验

点「保存为草稿」后 URL 会出现 `appmsgid=xxxx`，据此确认成功；「历史版本」里能看到 `10-14 19:57 … 手动保存`。

每次改动后跑 CALL 3，对比 `textLen / h2 / h3 / table / imgs / ids`。文字基线由 CALL 1 打印在 `expected` 里。

## 6. 只读锁（最大的坑）

弹出 `version_fail_dialog`（「当前编辑的草稿不是最新版本」）后，`pm.contentEditable` 变 `"false"`：
- paste dispatch 返回 `true`（未被消费）
- `pm.focus()` 后 `document.activeElement` 仍是 BODY
- `execCommand('delete')` 返回 false

**唯一解法**：注册 `beforeunload` 拦截 → `navigate_page` 回完整编辑 URL 重开会话 → 重新执行。这期间所有「粘贴没生效」都不是姿势问题，别去试别的插入位置。

## 7. 接口约束（各家驱动通用的坑）

- **执行 JS 的接口普遍只接受 `{function}` 一个键**，多传 `uid` 等参数报 「params must NOT have additional properties」。
- **超时是硬限制**（本环境 15s）。被放弃的 async 脚本会继续在页面里跑并改文档（已因此产生过重复插图）。**一次调用一件事**，不写重试循环；超时后先等页面静默、重读状态再动手。
- **返回值只用字符串/数字/布尔的普通对象**。`DOMRect` 字段过 JSON 桥会序列化成 `0`，需 `Number()` 转换；`JSON.stringify` 包一层最省事。
- 批量扫块用 `textContent`，不要用 `innerText`（布局抖动会超时）。
- 快照太大：给正文 `.ProseMirror` 设 `style.setProperty('visibility','hidden')` 可裁掉（约 500 → 60 行），用完 `removeProperty`。`aria-hidden="true"` **无效**。
- 不要点纯文本节点的元素 id（报 `this.scrollIntoView is not a function`）；用 JS 驱动或点真实按钮节点。

## 8. 封面：目前无法自动化

`.js_cover_btn_area` 对 `click()` 和完整合成 `pointerdown/mousedown/pointerup/mouseup/click` 序列都无反应；可信 `click` 报「Element is not visible or does not accept pointer input」。**需要真人点一次**，再在弹窗里选图。大图封面 **900×383**。
