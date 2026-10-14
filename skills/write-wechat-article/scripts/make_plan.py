#!/usr/bin/env python3
"""Turn inline image markers in an article draft into a plan.json for build_layout_js.py.

Convention: put standard Markdown image markers in the master copy where the screenshot
belongs — `![模块导航](images/05-编辑器-模块导航.png)`. This script derives the layout plan
from them, so placement lives in the article (reviewable, diffable) instead of in a
hand-written JSON.

Usage:
  python make_plan.py article.md images/ [--cdn cdn.json] [--out plan.json] [--allow-missing]

  --cdn    harvested upload list, in upload order: [{"src":..,"id":..}, ...]
           zipped with the referenced images sorted by NN prefix. Upload screenshots in
           NN order so the two line up.
  --out    write plan.json here (default: stdout)
  --allow-missing  keep entries with an unresolved anchor instead of failing

Exit codes: 0 ok (may contain warnings), 1 unrecoverable (missing marker file, anchor unresolved)
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from image_meta import EXTS, meta  # noqa: E402

MARKER = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')
PREFIX = re.compile(r'^(\d{1,3})[-_.]')
NON_CANDIDATE = re.compile(r'^\s*(#{1,6}\s|[-*+]\s|\d+\.\s|>|```|\||\s*$)')


def plain(line):
    s = line.strip()
    s = re.sub(r'^#{1,6}\s*', '', s)
    s = re.sub(r'^>\s*', '', s)
    s = re.sub(r'^[-*+]\s+', '', s)
    s = re.sub(r'^\d+\.\s+', '', s)
    s = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', s)
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s)
    s = s.replace('**', '').replace('`', '')
    s = re.sub(r'^[-*_]{3,}\s*$', '', s)
    return s.strip()


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, 'reconfigure'):
            s.reconfigure(encoding='utf-8')

    pos, opts, flags = [], {}, set()
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ('--cdn', '--out'):
            if i + 1 >= len(argv):
                sys.exit('%s 后面要跟一个路径' % a)
            opts[a] = argv[i + 1]
            i += 2
            continue
        if a.startswith('--'):
            flags.add(a)
            i += 1
            continue
        pos.append(a)
        i += 1
    if len(pos) < 2:
        sys.exit(__doc__)
    md_path, img_dir = pos[0], pos[1]
    cdn_path, out_path = opts.get('--cdn'), opts.get('--out')

    raw = open(md_path, encoding='utf-8').read().splitlines()
    plains = [plain(l) for l in raw]
    corpus = '\n'.join(plains)

    # images on disk, in NN order (falling back to file order)
    files = sorted((f for f in os.listdir(img_dir) if f.lower().endswith(EXTS)),
                   key=lambda f: (int(PREFIX.match(f).group(1)) if PREFIX.match(f) else 999, f))

    # markers in document order
    marks = []
    for i, line in enumerate(raw):
        for m in MARKER.finditer(line):
            marks.append((i, os.path.basename(m.group(1))))
    if not marks:
        print('ERROR: %s 里没有任何 ![](images/NN-*.png) 标记，无法自动落位。\n'
              '      在母本里该放图的位置插入 Markdown 图片标记后再跑本脚本，\n'
              '      或手工写 plan.json（字段见 scripts/build_layout_js.py 的说明）。'
              % os.path.basename(md_path), file=sys.stderr)
        print('      磁盘上的图片（共 %d 张）：%s' % (len(files), ', '.join(files)), file=sys.stderr)
        sys.exit(1)

    def anchor_for(line_no):
        """nearest preceding line whose plain text is unique in the document"""
        for back in range(1, 9):
            j = line_no - back
            if j < 0:
                break
            if NON_CANDIDATE.match(raw[j]):
                continue
            t = plains[j]
            if len(t) < 8 or t == plains[line_no]:
                continue
            if corpus.count(t) == 1:
                return t
        return ''

    entries, used, warn = [], set(), []
    for order, (line_no, name) in enumerate(marks):
        if name not in files:
            print('ERROR: 标记引用的文件不在 %s 里：%s' % (img_dir, name), file=sys.stderr)
            sys.exit(1)
        used.add(name)
        a = anchor_for(line_no)
        if not a:
            warn.append('第 %d 行 %s：找不到唯一锚点，需要手填 after' % (line_no + 1, name))
        m = meta(os.path.join(img_dir, name))
        entries.append({'file': name, 'after': a, 'src': '', 'id': '',
                        'w': m['w'], 'ratio': m['ratio']})

    # NN order vs document order
    numbered = [(int(PREFIX.match(e['file']).group(1)) if PREFIX.match(e['file']) else None)
                for e in entries]
    if all(n is not None for n in numbered) and numbered != sorted(numbered):
        warn.append('标记的序号顺序与正文顺序不一致：%s（上传顺序按序号，配对会错位）' % numbered)

    # merge CDN info, zipped by upload order
    if cdn_path:
        cdn = json.load(open(cdn_path, encoding='utf-8'))
        if len(cdn) != len(entries):
            warn.append('cdn.json 有 %d 条，落位表有 %d 条 —— 只配对前 %d 条'
                        % (len(cdn), len(entries), min(len(cdn), len(entries))))
        for e, c in zip(entries, cdn):
            e['src'] = c.get('src', '')
            e['id'] = str(c.get('id', ''))

    plan = {'images': entries}
    text = json.dumps(plan, ensure_ascii=False, indent=1)
    if out_path:
        open(out_path, 'w', encoding='utf-8').write(text + '\n')
        print('OK  写入 %s（%d 条）' % (out_path, len(entries)), file=sys.stderr)
    else:
        print(text)

    missing = [f for f in files if f not in used]
    print('---- 摘要 ----', file=sys.stderr)
    for i, e in enumerate(entries):
        print('  %2d  %-38s ← %s' % (i + 1, e['file'], e['after'] or '(未填)'), file=sys.stderr)
    for w in warn:
        print('  WARN ' + w, file=sys.stderr)
    if missing:
        print('  未使用的图片（%d）：%s' % (len(missing), ', '.join(missing)), file=sys.stderr)
    if cdn_path:
        empty = [e['file'] for e in entries if not e['src']]
        if empty:
            print('  WARN 这些图还没有 CDN 地址（CALL 1 会被拒）：%s' % ', '.join(empty), file=sys.stderr)
    if warn and '--allow-missing' not in flags:
        print('  有未解决的锚点 → 修好母本或手填 plan.json 后重跑（或用 --allow-missing 强行产出）',
              file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
