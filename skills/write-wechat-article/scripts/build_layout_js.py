#!/usr/bin/env python3
"""Emit the exact browser JS payloads that lay screenshots into a WeChat MP article draft.

Usage:
  python build_layout_js.py plan.json > layout.txt      # then read layout.txt and copy each CALL block

plan.json:
  { "images": [
      { "file": "14-home.png",
        "after": "打开 https://example.com ，右上角「免费注册」。",   // unique text of the paragraph to insert after
        "src":  "https://mmbiz.qpic.cn/.../0?wx_fmt=png&from=appmsg", // CDN url harvested from the editor
        "id":   "100000002",                                          // data-imgfileid
        "w":    918,
        "ratio": 0.7745098039 }                                        // h / w
  ] }

The payloads must be run one CALL per evaluate_script invocation (15s hard timeout, and a
timed-out script keeps mutating the page). CALL 2 replaces the whole document.
"""
import json
import sys

CALL1 = r"""() => {
  const pm = document.querySelectorAll('.ProseMirror')[1];
  if (!pm) return 'NO_PM: open the appmsg editor page first';
  if (pm.contentEditable !== 'true') return 'READ_ONLY: version dialog dismissed -> reload the editor URL';
  const plan = __PLAN__;
  window.__backup = pm.innerHTML;
  window.__baseline = JSON.stringify({blocks: pm.children.length, textLen: pm.textContent.length,
    h2: pm.querySelectorAll('h2').length, h3: pm.querySelectorAll('h3').length, table: !!pm.querySelector('table')});
  const clone = document.createElement('div');
  clone.innerHTML = pm.innerHTML;
  [...clone.children].forEach(c => { if (c.querySelector && c.querySelector('img')) c.remove(); });
  clone.querySelectorAll('img.ProseMirror-separator').forEach(e => e.remove());
  clone.querySelectorAll('br.ProseMirror-trailingBreak').forEach(e => e.remove());
  const missing = [], dup = [];
  for (const p of plan) {
    const hits = [...clone.children].filter(c => (c.textContent || '').indexOf(p.after) >= 0);
    if (!hits.length) { missing.push(p.after.slice(0, 40)); continue; }
    if (hits.length > 1) dup.push(p.after.slice(0, 40));
    const el = document.createElement('p');
    el.innerHTML = '<img src="' + p.src + '" data-imgfileid="' + p.id + '" data-ratio="' + p.ratio
      + '" data-w="' + p.w + '" data-type="png">';
    hits[0].after(el);
  }
  if (missing.length || dup.length) return 'REJECTED missing=' + JSON.stringify(missing) + ' ambiguous=' + JSON.stringify(dup);
  window.__rebuild = clone.innerHTML;
  return 'CALL1 OK plan=' + plan.length + ' baseline=' + window.__baseline;
}"""

CALL2 = r"""async () => {
  const pm = document.querySelectorAll('.ProseMirror')[1];
  if (!window.__rebuild) return 'NO_REBUILD: run CALL 1 first';
  if (pm.contentEditable !== 'true') return 'READ_ONLY: reload the editor URL, run CALL 1 again';
  pm.focus();
  await new Promise(r => setTimeout(r, 500));
  const rg = document.createRange();
  rg.selectNodeContents(pm);                 // whole-doc selection => paste REPLACES the body
  const s = getSelection();
  s.removeAllRanges();
  s.addRange(rg);
  await new Promise(r => setTimeout(r, 400));
  const dt = new DataTransfer();
  dt.setData('text/html', window.__rebuild);
  dt.setData('text/plain', 'rebuild');
  const consumed = !pm.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
  return 'CALL2 consumed=' + consumed;
}"""

CALL3 = r"""() => {
  const pm = document.querySelectorAll('.ProseMirror')[1];
  const imgs = [...pm.querySelectorAll('img')].filter(i => (i.getAttribute('src') || '').indexOf('mmbiz') >= 0);
  return JSON.stringify({
    editable: pm.contentEditable,
    blocks: pm.children.length,
    imgs: imgs.length,
    ids: imgs.map(i => i.getAttribute('data-imgfileid')).join(' '),
    h2: pm.querySelectorAll('h2').length,
    h3: pm.querySelectorAll('h3').length,
    table: !!pm.querySelector('table'),
    textLen: pm.textContent.length,
    expected: window.__baseline
  });
}"""

ROLLBACK = r"""async () => {
  const pm = document.querySelectorAll('.ProseMirror')[1];
  if (!window.__backup) return 'NO_BACKUP';
  pm.focus();
  await new Promise(r => setTimeout(r, 500));
  const rg = document.createRange(); rg.selectNodeContents(pm);
  const s = getSelection(); s.removeAllRanges(); s.addRange(rg);
  await new Promise(r => setTimeout(r, 400));
  const dt = new DataTransfer();
  dt.setData('text/html', window.__backup);
  dt.setData('text/plain', 'rollback');
  return 'ROLLBACK consumed=' + !pm.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
}"""

HARVEST = r"""() => {
  const pm = document.querySelectorAll('.ProseMirror')[1];
  const imgs = [...pm.querySelectorAll('img')]
    .map(i => ({src: i.getAttribute('src'), id: i.getAttribute('data-imgfileid'),
                w: Number(i.getAttribute('data-w')), ratio: i.getAttribute('data-ratio')}))
    .filter(x => x.src && x.src.indexOf('mmbiz') >= 0);
  imgs.sort((a, b) => Number(a.id) - Number(b.id));   // id ascends with upload order
  return JSON.stringify(imgs, null, 1);
}"""


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')      # Chinese anchors; Windows defaults to cp936
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    try:
        plan = json.load(open(sys.argv[1], encoding='utf-8'))
    except SystemExit:
        raise
    except Exception as e:
        sys.exit('cannot read plan.json: %s' % e)
    imgs = plan['images'] if isinstance(plan, dict) else plan
    for it in imgs:
        for k in ('after', 'src', 'id', 'w', 'ratio'):
            if k not in it:
                sys.exit('plan entry %r missing key %r' % (it.get('file'), k))
        if not it['after']:
            sys.exit('plan entry %r has an empty anchor ("after")' % it.get('file'))
    js = json.dumps(imgs, ensure_ascii=False)
    out = sys.stdout
    out.write('### CALL 1 - build the rebuild buffer (does not touch the doc)\n')
    out.write(CALL1.replace('__PLAN__', js) + '\n\n')
    out.write('### CALL 2 - paste it (REPLACES the whole body; run only after CALL 1 returned OK)\n')
    out.write(CALL2 + '\n\n')
    out.write('### CALL 3 - verify (textLen/h2/h3/table must equal the printed baseline)\n')
    out.write(CALL3 + '\n\n')
    out.write('### only if CALL 3 mismatches: restore\n')
    out.write(ROLLBACK + '\n\n')
    out.write('### run right after uploading, to harvest src/id/w/ratio into cdn.json\n')
    out.write(HARVEST + '\n')


if __name__ == '__main__':
    main()
