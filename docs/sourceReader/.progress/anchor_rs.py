#!/usr/bin/env python3
"""anchor_rs.py — build symbol anchor table for .rs files and resolve file+line refs to symbol+offset.

Approach: for each referenced .rs file, scan top-level items and impl-block methods via
brace matching (handles // and /* */ comments, "..." and '...' literals, raw strings).
Then for a target line N, find the innermost item whose body contains N, and compute
offset = N - def_line. Outputs `Symbol +offset` (or `Class.method +offset`).

Usage:
  anchor_rs.py build <file> [<file>...]   # print item table
  anchor_rs.py resolve <file> <line>      # resolve one line to Symbol+offset
  anchor_rs.py convert <mapfile>          # read "file|line" lines, print "file|Symbol +offset"
"""
import re, sys, os

REPO = "/Users/vincent/workspace/16_AI/goose"

# Item definition patterns. group(1)=kind, group(2)=name
DEF_RE = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?"
    r"(?:fn\s+([A-Za-z_][A-Za-z0-9_]*)|struct\s+([A-Za-z_][A-Za-z0-9_]*)|enum\s+([A-Za-z_][A-Za-z0-9_]*)|"
    r"trait\s+([A-Za-z_][A-Za-z0-9_]*)|mod\s+([A-Za-z_][A-Za-z0-9_]*)|"
    r"const\s+([A-Za-z_][A-Za-z0-9_]*)|static\s+([A-Za-z_][A-Za-z0-9_]*)|type\s+([A-Za-z_][A-Za-z0-9_]*))"
)

# `impl` blocks: name the target type (the `for X` or the sole type after impl).
IMPL_RE = re.compile(
    r"^\s*impl(?:\s*<[^>]*>)?\s+(?:[A-Za-z_][A-Za-z0-9_:<>]*\s+)?(?:for\s+)?([A-Za-z_][A-Za-z0-9_:<>]*)"
)

def strip_comments_and_strings(line):
    """Remove // comments, /* */ block fragments, and string/char literal contents
    so brace counting isn't fooled. Processes left-to-right so a `//` comment wins
    over a later `/*` (e.g. a doc comment containing '*/')."""
    out = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == '/' and i + 1 < n and line[i+1] == '/':
            break  # rest is comment
        if c == '/' and i + 1 < n and line[i+1] == '*':
            j = line.find('*/', i+2)
            if j == -1:
                i = n  # comment continues; caller tracks state
            else:
                i = j + 2
            continue
        if c == '"':
            i += 1
            while i < n:
                if line[i] == '\\':
                    i += 2
                    continue
                if line[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        if c == '\'':
            if i + 1 < n and line[i+1] == '\\':
                i += 4 if i + 3 < n else n
                continue
            if i + 2 < n and line[i+2] == '\'':
                i += 3
                continue
            i += 1
            continue
        out.append(c)
        i += 1
    return ''.join(out)

def read_items(path):
    """Return list of (name, def_line, body_start, body_end). body_start/end are 1-based."""
    try:
        lines = open(path).read().split('\n')
    except OSError:
        return []
    items = []
    # We track block comment state across lines.
    in_block_comment = False
    # Stack of open braces with their (kind,name,def_line) at the time the brace opened.
    # We need to associate a brace with the item it starts. Simplify: track item candidates
    # and their opening brace line.
    pending = None  # (kind, name, def_line) awaiting its '{'
    stack = []  # each entry: {'brace_line': int, 'item': (kind,name,def_line) or None}
    for idx, raw in enumerate(lines):
        lineno = idx + 1
        # strip block comment portions
        if in_block_comment:
            if '*/' in raw:
                raw = raw[raw.index('*/')+2:]
                in_block_comment = False
            else:
                continue  # whole line inside block comment
        # detect a block comment that opens and stays open (only count /* not inside a // comment)
        if '/*' in raw:
            # strip // comments first so a doc comment like `/// ... /*.md` isn't mistaken
            no_line_comment = raw.split('//')[0] if '//' in raw else raw
            if no_line_comment.count('/*') > no_line_comment.count('*/'):
                cut = no_line_comment.index('/*')
                raw = raw[:cut]
                in_block_comment = True
        clean = strip_comments_and_strings(raw)
        # detect item definition
        m = DEF_RE.match(clean)
        if m:
            name = next((g for g in m.groups() if g), None)
            if name:
                pending = (m.lastindex - 1, name, lineno)
        else:
            im = IMPL_RE.match(clean)
            if im:
                name = im.group(1)
                # name may be generic like Foo<T>; strip to bare ident for readability
                name = re.sub(r"<.*>", "", name)
                if name:
                    pending = (100, name, lineno)  # kind 100 = impl block
        # count braces
        for ch in clean:
            if ch == '{':
                if pending is not None:
                    stack.append({'item': pending, 'brace_line': lineno})
                    pending = None
                else:
                    stack.append({'item': None, 'brace_line': lineno})
            elif ch == '}':
                if stack:
                    top = stack.pop()
                    if top['item'] is not None:
                        kind_idx, name, def_line = top['item']
                        items.append((name, def_line, top['brace_line'], lineno))
        # `;`-terminated items (const, type alias, tuple/unit struct): no body block
        if pending is not None and ';' in clean:
            kind_idx, name, def_line = pending
            items.append((name, def_line, def_line, def_line))
            pending = None
    # unclosed items (shouldn't happen for well-formed) — ignore
    return items

def resolve(path, line):
    items = read_items(path)
    if not items:
        return None, None
    # innermost item whose body [body_start, body_end] contains line,
    # OR whose signature region [def_line, body_start) contains line (def + signature lines).
    best = None
    for (name, def_line, bs, be) in items:
        if bs <= line <= be:
            if best is None or (bs >= best[2]):  # prefer innermost (largest body_start)
                best = (name, def_line, bs, be)
        elif def_line <= line < bs:
            # signature/def line: map to this symbol with offset from def
            if best is None or def_line >= best[1]:
                best = (name, def_line, bs, be)
    if best is None:
        # If line is an attribute/derive line immediately above a def, map to that def at +0
        # (the attribute belongs to the symbol). Else nearest def_line at or above.
        try:
            raw = open(path).read().split('\n')[line-1]
        except (OSError, IndexError):
            raw = ""
        is_attr = raw.lstrip().startswith('#') or raw.lstrip().startswith('//') or raw.lstrip().startswith('///')
        below = [(n, d) for (n, d, bs, be) in items if d >= line and d - line <= 3]
        if below:
            name, d = min(below, key=lambda x: x[1])
            return name, 0 if is_attr else line - d
        cands = [(n, d) for (n, d, bs, be) in items if d <= line]
        if not cands:
            return None, None
        name, d = max(cands, key=lambda x: x[1])
        return name, line - d
    name, def_line, bs, be = best
    return name, line - def_line

def main():
    if len(sys.argv) < 2:
        print(__doc__); return 1
    cmd = sys.argv[1]
    if cmd == "build":
        for f in sys.argv[2:]:
            path = f if os.path.isabs(f) else os.path.join(REPO, f)
            items = read_items(path)
            print(f"== {f} ({len(items)} items) ==")
            for (name, d, bs, be) in items:
                print(f"  {name:40s} def={d} body={bs}..{be}")
    elif cmd == "resolve":
        f, line = sys.argv[2], int(sys.argv[3])
        path = f if os.path.isabs(f) else os.path.join(REPO, f)
        name, off = resolve(path, line)
        print(f"{name}+{off}" if name else "NONE")
    elif cmd == "convert":
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            parts = line.rsplit('|', 1)
            f, ln = parts[0], int(parts[1])
            path = f if os.path.isabs(f) else os.path.join(REPO, f)
            name, off = resolve(path, ln)
            print(f"{f}|{name}+{off}" if name else f"{f}|???")
    return 0

if __name__ == "__main__":
    sys.exit(main())
