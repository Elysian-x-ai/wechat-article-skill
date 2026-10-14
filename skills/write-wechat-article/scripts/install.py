#!/usr/bin/env python3
"""Install this skill into an agent tool's skills directory, or sync it into a repo.

Two directions:

  end user   克隆/解压后，把本 skill 装进自己所用的 agent 工具
              python install.py                      # 装到所有检测到的工具
              python install.py --tools claude,codex
              python install.py --local              # 装到 ./.claude/skills 等（项目级）

  maintainer 把这里的改动同步回仓库（repo/skills/<name>/）
              python install.py --repo ../wechat-article-skill --force
              （--repo 单用只同步仓库；要顺带装工具就显式写 --tools）

  通用参数：--dry-run 只看不做；--force 覆盖已存在的副本。
  装完要让工具重新加载：Qoder 用 /skills reload；Claude Code 重启会话或用 /skills；
  Codex 重启（或 codex skill reload）。
"""
import os
import shutil
import sys

# 工具 → (用户级技能目录, 项目级技能目录)，相对 ~ 或 CWD
TOOLS = {
    'qoder':  ('.qoder-cn/skills', '.qoder/skills'),
    'claude': ('.claude/skills',   '.claude/skills'),
    'codex':  ('.codex/skills',    '.codex/skills'),
    'agents': ('.agents/skills',   '.agents/skills'),
}
IGNORE = shutil.ignore_patterns('__pycache__', '*.pyc', '.git', '.DS_Store',
                                'plan.json', 'cdn.json', 'layout.txt')


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, 'reconfigure'):
            s.reconfigure(encoding='utf-8')

    pos, opts, flags = [], {}, set()
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ('--tools', '--repo'):
            if i + 1 >= len(argv):
                sys.exit('%s 后面要跟一个值' % a)
            opts[a] = argv[i + 1]
            i += 2
            continue
        if a.startswith('--'):
            flags.add(a)
            i += 1
            continue
        pos.append(a)
        i += 1

    src = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    name = os.path.basename(src)
    home = os.path.expanduser('~')
    local = '--local' in flags
    dry = '--dry-run' in flags
    force = '--force' in flags

    if not os.path.exists(os.path.join(src, 'SKILL.md')):
        sys.exit('没找到 SKILL.md —— 本脚本要放在 <skill>/scripts/ 下运行')

    # 目标列表：(标签, 目标父目录)
    # --repo 单用 = 只同步仓库；要顺带装工具就显式写 --tools
    targets = []
    if opts.get('--repo'):
        targets.append(('repo', os.path.join(os.path.abspath(opts['--repo']), 'skills')))
    if opts.get('--tools'):
        tools = opts['--tools'].split(',')
    elif opts.get('--repo'):
        tools = []
    else:
        tools = list(TOOLS)
    for tool in tools:
        if tool not in TOOLS:
            print('  跳过 %-7s 未知工具（可选：%s）' % (tool, ', '.join(TOOLS)))
            continue
        user_rel, proj_rel = TOOLS[tool]
        rel = proj_rel if local else user_rel
        targets.append((tool, os.path.abspath(rel) if local else os.path.join(home, *rel.split('/'))))

    if not targets:
        sys.exit(__doc__)

    print('源：%s' % src)
    rc = 0
    for label, base in targets:
        dest = os.path.join(base, name)
        if os.path.abspath(dest) == src:
            print('  %-7s 就是本目录，跳过' % label)
            continue
        existing = os.path.isdir(dest)
        if existing and not force:
            print('  %-7s 已存在，未改动：%s   （加 --force 覆盖）' % (label, dest))
            continue
        if label == 'repo':
            os.makedirs(base, exist_ok=True)
        elif not os.path.isdir(base):
            print('  %-7s 技能目录不存在，跳过：%s' % (label, base))
            continue
        action = '覆盖' if existing else '写入'
        if dry:
            print('  %-7s [dry-run] 会%s到 %s' % (label, action, dest))
            continue
        try:
            if existing:
                shutil.rmtree(dest)
            shutil.copytree(src, dest, ignore=IGNORE)
            print('  %-7s %s → %s' % (label, action, dest))
        except Exception as e:
            print('  %-7s 失败：%s' % (label, e))
            rc = 1
    if not dry and '--repo' not in opts:
        print('\n装完让各工具重新加载：Qoder 运行 /skills reload；Claude Code 重启会话或用 /skills；'
              'Codex 重启（或 codex skill reload）。')
    return rc


if __name__ == '__main__':
    sys.exit(main())
