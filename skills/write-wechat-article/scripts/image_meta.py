#!/usr/bin/env python3
"""Print image dimensions and the data-ratio / data-w values the WeChat MP editor needs.

Usage:
  python image_meta.py <images_dir> [file1.png file2.png ...]
  python image_meta.py <images_dir>            # all png/jpg in the dir

Output is one JSON object per image, on stdout, plus a compact table on stderr.
"""
import json
import os
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required: python -m pip install pillow")

EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def meta(path):
    with Image.open(path) as im:
        w, h = im.size
    return {
        "file": os.path.basename(path),
        "w": w,
        "h": h,
        "ratio": round(h / w, 10),
        "ok_cover_900x383": abs(w - 900) < 1 and abs(h - 383) < 1,
    }


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")   # filenames are Chinese; Windows defaults to cp936
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    d = sys.argv[1]
    names = sys.argv[2:] or sorted(
        n for n in os.listdir(d) if n.lower().endswith(EXTS)
    )
    rows = []
    for n in names:
        p = n if os.path.isabs(n) else os.path.join(d, n)
        if not os.path.exists(p):
            print(json.dumps({"file": n, "error": "not found"}, ensure_ascii=False))
            continue
        m = meta(p)
        rows.append(m)
        print(json.dumps(m, ensure_ascii=False))
    print("---- data-w / data-ratio for paste markup ----", file=sys.stderr)
    for m in rows:
        if "error" in m:
            print("  MISSING %s" % m["file"], file=sys.stderr)
        else:
            print('  %-40s data-w="%d" data-ratio="%s"'
                  % (m["file"], m["w"], m["ratio"]), file=sys.stderr)


if __name__ == "__main__":
    main()
