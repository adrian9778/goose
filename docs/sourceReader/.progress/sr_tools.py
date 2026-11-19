#!/usr/bin/env python3
"""sr_tools.py — verification tooling for the goose sourceReader doc library.

Subcommands:
  verify DOC...        — check file-path references in docs resolve; flag line-number refs out of bounds.
  locate SYM...        — locate symbol definitions across repo (production first, then tests/scripts).
  outline FILE [--top] — print top-level symbols of a .rs file.
  offset FILE SYM      — print the definition line number of SYM in FILE.

Notation handled in verify:
  `path/file.rs +N`              — file + absolute line number (current docs use this).
  `path/file.rs` · `sym` +N      — file + symbol (+offset) [symbol-level check is manual].
"""
import re, sys, os, subprocess, pathlib

REPO = "/Users/vincent/workspace/16_AI/goose"
DOCDIR = os.path.join(REPO, "docs/sourceReader")

def _resolve(path):
    """Resolve a possibly-relative .rs reference to an absolute file path.
    Try: exact relative to REPO, exact relative to DOCDIR, then basename search
    under crates/ (collecting ALL matches for ambiguity detection)."""
    cands = []
    p = path.strip()
    for base in (REPO, DOCDIR):
        cand = os.path.normpath(os.path.join(base, p))
        if os.path.isfile(cand):
            cands.append(cand)
    if not cands:
        # basename search under crates/
        base = os.path.basename(p)
        d = os.path.dirname(p)
        r = subprocess.run(["find", os.path.join(REPO, "crates"), "-name", base, "-path", f"*{d}*" if d and d != "." else "*"],
                           capture_output=True, text=True)
        for line in r.stdout.splitlines():
            if line.strip():
                cands.append(line.strip())
        if not cands:
            r = subprocess.run(["find", os.path.join(REPO, "crates"), "-name", base],
                               capture_output=True, text=True)
            for line in r.stdout.splitlines():
                if line.strip():
                    cands.append(line.strip())
    return cands

def line_ref_ok(path, n):
    try:
        with open(path) as f:
            total = sum(1 for _ in f)
        return 1 <= n <= total, total
    except OSError:
        return False, 0

def verify(docs):
    file_re = re.compile(r"(?:`([A-Za-z0-9_/.-]+\.rs)`|(?<![\w.`])([A-Za-z0-9_/.-]+\.rs)(?![\w.]))")
    ln_re = re.compile(r"(?:`([A-Za-z0-9_/.-]+\.rs)`|(?<![\w.`])([A-Za-z0-9_/.-]+\.rs)(?![\w.]))\s*\+\s*(\d+)")
    unresolved = {}
    out_of_bounds = {}
    ambiguous = {}
    total_line_refs = 0
    for doc in docs:
        try:
            txt = pathlib.Path(doc).read_text()
        except OSError:
            print(f"[no read] {doc}")
            continue
        for m in ln_re.finditer(txt):
            total_line_refs += 1
            p = m.group(1) or m.group(2)
            n = int(m.group(3))
            cands = _resolve(p)
            if not cands:
                unresolved.setdefault(p, []).append((os.path.basename(doc), n))
            elif len(cands) > 1:
                ambiguous.setdefault(p, cands)
                # Prefer candidate(s) where the line is in-bounds; report only if NONE fits.
                good = [c for c in cands if line_ref_ok(c, n)[0]]
                if not good:
                    for c in cands:
                        ok, total = line_ref_ok(c, n)
                        out_of_bounds.setdefault(p, []).append((os.path.basename(doc), n, c, total))
            else:
                ok, total = line_ref_ok(cands[0], n)
                if not ok:
                    out_of_bounds.setdefault(p, []).append((os.path.basename(doc), n, cands[0], total))
    print(f"line-number references checked: {total_line_refs}")
    if unresolved:
        print(f"\nUNRESOLVED ({len(unresolved)}):")
        for p, occ in sorted(unresolved.items()):
            print(f"  {p}  <- {occ[:3]}")
    if ambiguous:
        print(f"\nAMBIGUOUS basenames ({len(ambiguous)}) — multiple candidate files:")
        for p, cands in sorted(ambiguous.items()):
            print(f"  {p}:")
            for c in cands:
                print(f"    {c}")
    if out_of_bounds:
        print(f"\nOUT-OF-BOUNDS line refs ({len(out_of_bounds)}):")
        for p, occ in sorted(out_of_bounds.items()):
            for doc, n, c, total in occ:
                print(f"  {p} +{n} (file has {total} lines) [{c}] in {doc}")

def locate(syms):
    for sym in syms:
        print(f"== {sym} ==")
        r = subprocess.run(["grep", "-rn", "--include=*.rs", f"\\b{sym}\\b", os.path.join(REPO, "crates")],
                           capture_output=True, text=True)
        lines = [l for l in r.stdout.splitlines() if "fn " in l or "struct " in l or "enum " in l or "trait " in l or "impl " in l]
        for l in lines[:15]:
            print(" ", l)

def offset(file, sym):
    cands = _resolve(file)
    if not cands:
        print(f"[no resolve] {file}")
        return
    c = cands[0]
    r = subprocess.run(["grep", "-n", f"\\b{sym}\\b", c], capture_output=True, text=True)
    for l in r.stdout.splitlines()[:10]:
        print(" ", l)

def main():
    if len(sys.argv) < 2:
        print(__doc__); return 1
    cmd = sys.argv[1]
    if cmd == "verify":
        docs = sys.argv[2:] or sorted(pathlib.Path(DOCDIR).glob("*.md"))
        verify([str(d) for d in docs])
    elif cmd == "locate":
        locate(sys.argv[2:])
    elif cmd == "offset":
        offset(sys.argv[2], sys.argv[3])
    elif cmd == "outline":
        cands = _resolve(sys.argv[2])
        if cands:
            r = subprocess.run(["grep", "-nE", r"^\s*(pub\s+)?(async\s+)?(fn|struct|enum|trait|impl|mod|const|type)\s+\w+", cands[0]],
                               capture_output=True, text=True)
            print(r.stdout[:2000])
    else:
        print(__doc__); return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
