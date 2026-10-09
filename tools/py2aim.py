#!/usr/bin/env python3
"""
py2aim.py — Convert indentation-based Python to AIMacro brace syntax.

CPython tests (and most .py scripts) use suites after `:`. AIMacro wants
C-style `{ }`. This is the analog of the test262 preprocessor that rewrites
source before the JS harness sees a file.

Usage:
    python3 tools/py2aim.py input.py [output.aim]
    python3 tools/py2aim.py --stdin < input.py

Not a full Python-to-AIMacro transpiler: it only inserts braces. Keywords
AIMacro does not have (`yield`, `async`, `@decorator`) pass through and
will fail later at parse — same as unsupported test262 features.

Copyright (c) 2026 Sean Collins, 2 Paws Machine and Engineering. SCSL.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys

CONTINUE_SUITE = ("else", "elif", "except", "finally")
import re

_CASE_RE = re.compile(r"^(\s*)case\s+(.+?)\s*:\s*(.*)$")
_MATCH_RE = re.compile(r"^(\s*)match\s+(.+?)\s*:\s*(#.*)?$")


def _take_as_binds(pat: str, indent: str, tmp: str):
    """Pull nested `as name` out of a match pattern (or-patterns, mappings)."""
    binds: list[str] = []

    def repl(m):
        binds.append(f"{indent}    {m.group(1)} = {tmp}\n")
        return ""

    pat2 = re.sub(r"\s+as\s+([A-Za-z_][A-Za-z0-9_]*)", repl, pat)
    return pat2.strip(), binds


def _split_case_line(raw: str):
    """Split `case <pattern>: [trailing]` at the suite colon (depth 0).

    `{0: 0}:` must not use the dict colon. `_CASE_RE` is non-greedy and did.
    """
    m = re.match(r"^(\s*)case\s+", raw)
    if not m:
        return None
    indent = m.group(1)
    rest = raw[m.end() :]
    idx = _suite_colon_index(rest)
    if idx == -1:
        return None
    pattern = rest[:idx].strip()
    trailing = rest[idx + 1 :].strip()
    return indent, pattern, trailing


def desugar_match(src: str) -> str:
    lines = src.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    n = len(lines)
    match_counter = 0
    while i < n:
        line = lines[i]
        m = _MATCH_RE.match(line.rstrip("\n"))
        if not m:
            out.append(line)
            i += 1
            continue
        indent, subject = m.group(1), m.group(2).strip()
        ind_w = len(indent.expandtabs(4))
        match_counter += 1
        tmp = f"_aim_match_{match_counter}"
        out.append(f"{indent}{tmp} = {subject}\n")
        i += 1
        first_case = True
        while i < n:
            raw = lines[i]
            stripped = raw.strip()
            if stripped == "":
                out.append(raw)
                i += 1
                continue
            if stripped.startswith("#"):
                ws = raw[: len(raw) - len(raw.lstrip())]
                if len(ws.expandtabs(4)) <= ind_w:
                    break
                out.append(raw)
                i += 1
                continue
            parsed_case = _split_case_line(raw.rstrip("\n"))
            if not parsed_case:
                ws = raw[: len(raw) - len(raw.lstrip())]
                if len(ws.expandtabs(4)) <= ind_w:
                    break
                out.append(raw)
                i += 1
                continue
            c_indent, pattern, trailing = parsed_case
            c_w = len(c_indent.expandtabs(4))
            if c_w <= ind_w:
                break
            body_lines: list[str] = []
            if trailing:
                body_lines.append(f"{c_indent}    {trailing}\n")
            i += 1
            while i < n:
                b = lines[i]
                if b.strip() == "":
                    body_lines.append(b)
                    i += 1
                    continue
                b_ws = b[: len(b) - len(b.lstrip())]
                if len(b_ws.expandtabs(4)) <= c_w:
                    break
                body_lines.append(b)
                i += 1
            guard = None
            pat = pattern
            if " if " in pattern:
                left, _, right = pattern.rpartition(" if ")
                pat, guard = left.strip(), right.strip()
            binds: list[str] = []
            cond: str
            capture = None
            if pat == "_":
                cond = "True"
            elif pat == "None":
                cond = f"{tmp} is None"
            else:
                tm = re.match(
                    r"^([\w.]+)\(([A-Za-z_][A-Za-z0-9_]*)\)$",
                    pat,
                )
                if tm:
                    typ, name = tm.group(1), tm.group(2)
                    cond = f"isinstance({tmp}, {typ})"
                    capture = name
                    binds.append(f"{indent}    {name} = {tmp}\n")
                elif re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", pat):
                    cond = "True"
                    capture = pat
                    binds.append(f"{indent}    {pat} = {tmp}\n")
                else:
                    am = re.match(
                        r"^(.+?)\s+as\s+([A-Za-z_][A-Za-z0-9_]*)$",
                        pat,
                    )
                    if am:
                        inner, name = am.group(1).strip(), am.group(2)
                        inner, extra = _take_as_binds(inner, indent, tmp)
                        binds.extend(extra)
                        cond = f"({tmp}) == ({inner})"
                        capture = name
                        binds.append(f"{indent}    {name} = {tmp}\n")
                    else:
                        pat2, extra = _take_as_binds(pat, indent, tmp)
                        binds.extend(extra)
                        cond = f"({tmp}) == ({pat2})"
            if guard:
                g = guard
                if capture:
                    # rewrite capture name → tmp so guard can run before bind
                    g = re.sub(rf"\b{re.escape(capture)}\b", tmp, g)
                if cond == "True":
                    cond = f"({g})"
                else:
                    cond = f"({cond}) and ({g})"
            if pat == "_" and guard is None and not first_case:
                out.append(f"{indent}else:\n")
            else:
                kw = "if" if first_case else "elif"
                out.append(f"{indent}{kw} {cond}:\n")
            first_case = False
            out.extend(binds)
            # reindent body from case-indent to match-indent+4
            # body currently at case_indent+4; we want match_indent+4 (+ binds already)
            # Keep body as-is (it was under case) — case indent is match+4, body is match+8.
            # After `if` at match indent, body should be match+4. So shift left by (c_w - ind_w).
            shift = c_w - ind_w
            for bl in body_lines:
                if bl.strip() == "":
                    out.append(bl)
                    continue
                # remove `shift` spaces from the start (approx)
                # body uses spaces; expand tabs
                expanded = bl.expandtabs(4)
                if expanded.startswith(" " * shift):
                    out.append(expanded[shift:])
                else:
                    out.append(bl)
        # end match cases
    return "".join(out)


def desugar_tuple_unpack(src: str) -> str:
    """Rewrite tuple/list assign targets into temp + index assigns.

    AIMacro/codegen does not bind tuple targets. Nested forms like
    `func, (origin, args) = super().__reduce__()` (typing._UnionGenericAlias)
    must expand or codegen emits illegal idents (\\x04).
    Reuses _for_unpack_assigns for nested Name/Tuple/List elts.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    counter_box = [0]

    class _Unpack(ast.NodeTransformer):
        def visit_Assign(self, node: ast.Assign):
            self.generic_visit(node)
            if len(node.targets) != 1:
                return node
            t = node.targets[0]
            if not isinstance(t, (ast.Tuple, ast.List)):
                return node
            counter_box[0] += 1
            tmp = f"_aim_unpack_{counter_box[0]}"
            binds = _for_unpack_assigns(tmp, t, counter_box)
            if not binds:
                return node
            stmts: list[ast.stmt] = [
                ast.Assign(
                    targets=[ast.Name(id=tmp, ctx=ast.Store())],
                    value=node.value,
                )
            ]
            stmts.extend(binds)
            return stmts

    new_tree = _Unpack().visit(tree)
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree) + "\n"
    except Exception:
        return src



def desugar_from_import_as(src: str) -> str:
    """Rewrite `from M import X as Y` so the bound name is Y.

    AIMacro Parse_FromImport skips the alias and keeps X; codegen then marks
    X while the body uses Y → Variable not found (html `_html5`).
    Collapse to `from M import Y` (compile stubs ignore the real export name).
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src

    class _FromAs(ast.NodeTransformer):
        def visit_ImportFrom(self, node: ast.ImportFrom):
            self.generic_visit(node)
            changed = False
            names = []
            for a in node.names:
                if a.asname:
                    names.append(ast.alias(name=a.asname, asname=None))
                    changed = True
                else:
                    names.append(a)
            if not changed:
                return node
            return ast.ImportFrom(module=node.module, names=names, level=node.level)

    new_tree = _FromAs().visit(tree)
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree) + "\n"
    except Exception:
        return src


def _for_unpack_assigns(tmp: str, target: ast.expr, counter_box: list[int]) -> list[ast.stmt]:
    """Expand a for-target (possibly nested tuple/list) into index assigns."""
    if isinstance(target, ast.Name):
        return [
            ast.Assign(
                targets=[ast.Name(id=target.id, ctx=ast.Store())],
                value=ast.Name(id=tmp, ctx=ast.Load()),
            )
        ]
    if isinstance(target, (ast.Tuple, ast.List)):
        stmts: list[ast.stmt] = []
        for idx, elt in enumerate(target.elts):
            if isinstance(elt, ast.Starred):
                # for a, b, *rest in xs — star-last rest slice.
                if idx != len(target.elts) - 1:
                    return []
                inner = elt.value
                if not isinstance(inner, ast.Name):
                    return []
                stmts.append(
                    ast.Assign(
                        targets=[ast.Name(id=inner.id, ctx=ast.Store())],
                        value=ast.Subscript(
                            value=ast.Name(id=tmp, ctx=ast.Load()),
                            slice=ast.Slice(
                                lower=ast.Constant(value=idx),
                                upper=None,
                                step=None,
                            ),
                            ctx=ast.Load(),
                        ),
                    )
                )
                continue
            if isinstance(elt, ast.Name):
                stmts.append(
                    ast.Assign(
                        targets=[ast.Name(id=elt.id, ctx=ast.Store())],
                        value=ast.Subscript(
                            value=ast.Name(id=tmp, ctx=ast.Load()),
                            slice=ast.Constant(value=idx),
                            ctx=ast.Load(),
                        ),
                    )
                )
            elif isinstance(elt, (ast.Tuple, ast.List)):
                counter_box[0] += 1
                sub = f"_aim_funpack_{counter_box[0]}"
                stmts.append(
                    ast.Assign(
                        targets=[ast.Name(id=sub, ctx=ast.Store())],
                        value=ast.Subscript(
                            value=ast.Name(id=tmp, ctx=ast.Load()),
                            slice=ast.Constant(value=idx),
                            ctx=ast.Load(),
                        ),
                    )
                )
                nested = _for_unpack_assigns(sub, elt, counter_box)
                if not nested:
                    return []
                stmts.extend(nested)
            else:
                return []
        return stmts
    return []


def desugar_for_unpack(src: str) -> str:
    """Rewrite `for a, b in xs` / `for i, (x, y) in xs` into temp + index binds.

    Codegen only binds the outer iter item; nested/multi targets leave names
    unbound (string `conversion`, textwrap `y`).
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    counter_box = [0]

    class _ForUnpack(ast.NodeTransformer):
        def visit_For(self, node: ast.For):
            self.generic_visit(node)
            t = node.target
            if not isinstance(t, (ast.Tuple, ast.List)):
                return node
            counter_box[0] += 1
            tmp = f"_aim_funpack_{counter_box[0]}"
            binds = _for_unpack_assigns(tmp, t, counter_box)
            if not binds:
                return node
            new_body = binds + list(node.body)
            return ast.For(
                target=ast.Name(id=tmp, ctx=ast.Store()),
                iter=node.iter,
                body=new_body,
                orelse=node.orelse,
                type_comment=getattr(node, "type_comment", None),
            )

    new_tree = _ForUnpack().visit(tree)
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree) + "\n"
    except Exception:
        return src


SUITE_START = (
    "def",
    "class",
    "if",
    "elif",
    "else",
    "while",
    "for",
    "try",
    "except",
    "finally",
    "with",
    "async",
)


def _stmt_first(code: str) -> str:
    """First keyword of a logical line. `except*` is still except (PEP 654)."""
    first = code.split(None, 1)[0] if code else ""
    first = first.rstrip(":")
    if first.startswith("except"):
        return "except"
    return first


def _leading_ws(line: str) -> str:
    i = 0
    while i < len(line) and line[i] in " \t":
        i += 1
    return line[:i]


def _code_part(line: str) -> tuple[str, str]:
    """Split a physical line into code vs trailing comment, ignoring # in strings."""
    in_s = None
    esc = False
    i = 0
    while i < len(line):
        c = line[i]
        if in_s:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == in_s:
                in_s = None
            i += 1
            continue
        if c in ("'", '"'):
            # triple quotes
            if line[i : i + 3] in ("'''", '"""'):
                in_s = line[i : i + 3]
                i += 3
                continue
            in_s = c
            i += 1
            continue
        if c == "#":
            return line[:i].rstrip(), line[i:]
        i += 1
    return line.rstrip(), ""


def _indent_width(ws: str) -> int:
    n = 0
    for c in ws:
        n += 4 if c == "\t" else 1
    return n


def _advance_quote_state(s: str, state: str | None) -> str | None:
    """Track unclosed quotes across lines. state is None, ', \", ''', or \"\"\"."""
    i = 0
    n = len(s)
    while i < n:
        if state:
            closer = state
            if s.startswith(closer, i):
                i += len(closer)
                state = None
                continue
            if s[i] == "\\" and len(closer) == 1:
                i += 2
                continue
            i += 1
            continue
        c = s[i]
        if c == "#":
            break
        if s.startswith('"""', i):
            state = '"""'
            i += 3
            continue
        if s.startswith("'''", i):
            state = "'''"
            i += 3
            continue
        if c in ("'", '"'):
            state = c
            i += 1
            continue
        i += 1
    return state


def _bracket_delta(s: str) -> int:
    """Net open-paren/bracket/brace change, ignoring strings/comments."""
    delta = 0
    in_s = None
    esc = False
    i = 0
    while i < len(s):
        c = s[i]
        if in_s:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == in_s[0] and s.startswith(in_s, i):
                i += len(in_s)
                in_s = None
                continue
            i += 1
            continue
        if c == "#":
            break
        if s.startswith('"""', i):
            in_s = '"""'
            i += 3
            continue
        if s.startswith("'''", i):
            in_s = "'''"
            i += 3
            continue
        if c in ("'", '"'):
            in_s = c
            i += 1
            continue
        if c in "([{":
            delta += 1
        elif c in ")]}":
            delta -= 1
        i += 1
    return delta


def _endswith_cont(code: str) -> bool:
    """True if *code* ends with a Python line-continuation backslash."""
    return code.rstrip().endswith("\\")


def _join_cont_codes(parts: list[str]) -> str:
    """Join backslash-continued code fragments into one logical line."""
    cleaned = []
    for p in parts:
        s = p.rstrip()
        if s.endswith("\\"):
            s = s[:-1].rstrip()
        cleaned.append(s)
    return " ".join(x for x in cleaned if x)



def _suite_colon_index(s: str) -> int:
    """Index of the suite ':' (bracket-depth 0, outside strings), or -1.

    Slice/dict/lambda colons sit inside [] {} or after lambda and must not be
    treated as the end of an if/for/def header. Used by one-liner rewrites so
    `if line[-1:] == '\\n': body` keeps the slice intact.
    """
    depth = 0
    in_s = None
    esc = False
    i = 0
    while i < len(s):
        c = s[i]
        if in_s:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == in_s[0] and s.startswith(in_s, i):
                i += len(in_s)
                in_s = None
                continue
            i += 1
            continue
        if c == "#":
            break
        if s.startswith('"""', i):
            in_s = '"""'
            i += 3
            continue
        if s.startswith("'''", i):
            in_s = "'''"
            i += 3
            continue
        if c in ("'", '"'):
            in_s = c
            i += 1
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == ":" and depth == 0:
            return i
        i += 1
    return -1



_NAMEERROR_PROBE_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)try:[ \t]*\n"
    r"(?P=indent)[ \t]+(?P<name>[A-Za-z_][A-Za-z0-9_]*)[ \t]*\n"
    r"(?P=indent)except[ \t]+NameError[ \t]*:"
)


def desugar_nameerror_probe(src: str) -> str:
    """Pre-bind bare `try: NAME` / `except NameError` probes (locale.CODESET).

    AILang treats the probe as a Variable reference and fails compile with
    Variable not found: CODESET when `_locale` star-import did not bind it.
    Binding NAME = None before the try makes the probe succeed legally.
    """
    def repl(m: re.Match) -> str:
        indent, name = m.group("indent"), m.group("name")
        # Exception type names are EmitIdent ints; `WindowsError = None`
        # became `3 = Types.GetNone()` (test_exceptions PARSE).
        if name.endswith(("Error", "Warning")) or name in {
            "Exception",
            "BaseException",
            "StopIteration",
            "KeyboardInterrupt",
            "SystemExit",
            "StopAsyncIteration",
            "GeneratorExit",
        }:
            return m.group(0)
        return f"{indent}{name} = None\n{m.group(0)}"
    return _NAMEERROR_PROBE_RE.sub(repl, src)

def _scan_depth_and_string(s: str) -> tuple[int, str | None]:
    """Paren/bracket depth and open string delimiter (handles ''' / \"\"\")."""
    depth = 0
    in_s: str | None = None
    i = 0
    n = len(s)
    while i < n:
        if in_s:
            if in_s in ("'''", '"""'):
                if s.startswith(in_s, i):
                    in_s = None
                    i += 3
                    continue
            else:
                if s[i] == "\\":
                    i += 2
                    continue
                if s[i] == in_s:
                    in_s = None
            i += 1
            continue
        if s.startswith('"""', i):
            in_s = '"""'
            i += 3
            continue
        if s.startswith("'''", i):
            in_s = "'''"
            i += 3
            continue
        c = s[i]
        if c in ("'", '"'):
            in_s = c
            i += 1
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        i += 1
    return depth, in_s


def _strip_physical_comment(s: str) -> str:
    """Drop a `#` comment on one physical line; keep `#` inside strings."""
    in_s: str | None = None
    i = 0
    n = len(s)
    while i < n:
        if in_s:
            if in_s in ("'''", '"""'):
                if s.startswith(in_s, i):
                    in_s = None
                    i += 3
                    continue
            else:
                if s[i] == "\\":
                    i += 2
                    continue
                if s[i] == in_s:
                    in_s = None
            i += 1
            continue
        if s.startswith('"""', i):
            in_s = '"""'
            i += 3
            continue
        if s.startswith("'''", i):
            in_s = "'''"
            i += 3
            continue
        c = s[i]
        if c in ("'", '"'):
            in_s = c
            i += 1
            continue
        if c == "#":
            return s[:i].rstrip()
        i += 1
    return s


_YIELD_RE = re.compile(r"^(\s*)yield(\b.*)$")
_PEP695_DEF_RE = re.compile(
    r"^(\s*)(def|class)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\[[^\]]*\]\s*(\()"
)
_PEP695_DEF_TRAIL_RE = re.compile(
    r"^(\s*)(def|class)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\[[^\]]*\]\s*$"
)


def desugar_yield(src: str) -> str:
    """Rewrite yield into a compile stub (AIMacro has no yield).

    Bare `yield` otherwise leaves the parser expecting an expression and the
    next statement (e.g. `x -= 1`) becomes Unexpected token MINUS_ASSIGN.
    Multiline `yield from sorted(...)` must consume balanced parens or the
    continuation lines become orphan tokens (enum Flag regression).
    """
    lines = src.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _YIELD_RE.match(line.rstrip("\n"))
        if not m:
            out.append(line)
            i += 1
            continue
        indent, rest = m.group(1), m.group(2).strip()
        if rest.startswith("from "):
            expr = rest[5:].strip()
            kind = "from"
        elif rest == "" or rest.startswith("#"):
            out.append(f"{indent}yield\n")
            i += 1
            continue
        else:
            # Do not rstrip(",") here: a continued call
            #   yield TokenInfo(STRING, a[:end],
            #          start, (n, end), line)
            # would lose the comma after a[:end] and parse as IDENT after RPAREN.
            expr = rest
            kind = "yield"
        buf = _strip_physical_comment(expr)
        depth, in_s = _scan_depth_and_string(buf)
        while (depth > 0 or in_s) and i + 1 < len(lines):
            i += 1
            buf += " " + _strip_physical_comment(lines[i].strip())
            depth, in_s = _scan_depth_and_string(buf)
        if kind == "from":
            out.append(f"{indent}yield from ({buf})\n")
        else:
            out.append(f"{indent}yield ({buf})\n")
        i += 1
    return "".join(out)


def desugar_pep695_type_params(src: str) -> str:
    """Strip PEP 695 type-parameter lists: def f[T]( -> def f(."""
    lines = src.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        raw = line.rstrip("\n")
        m = _PEP695_DEF_RE.match(raw)
        if m:
            indent, kind, name, _paren = m.groups()
            tail = raw[m.end() - 1 :]  # from (
            nl = "\n" if line.endswith("\n") else ""
            out.append(f"{indent}{kind} {name}{tail}{nl}")
            continue
        m2 = _PEP695_DEF_TRAIL_RE.match(raw)
        if m2:
            indent, kind, name = m2.groups()
            nl = "\n" if line.endswith("\n") else ""
            out.append(f"{indent}{kind} {name}{nl}")
            continue
        out.append(line)
    return "".join(out)



_STARARGS_ANN_RE = re.compile(
    r"(\*\*?)([A-Za-z_][A-Za-z0-9_]*)\s*:\s*[^,)=\n]+"
)


def desugar_starargs_annotations(src: str) -> str:
    """No-op: the parser now skips *args/**kwargs annotations, including
    bracketed forms like *args: Unpack[tuple[int, str]]. The old regex
    stopped at the first comma and left `*args, str]:`."""
    return src


def _fn_own_yields(fn: ast.AST) -> bool:
    class _V(ast.NodeVisitor):
        def __init__(self):
            self.found = False

        def visit_FunctionDef(self, n: ast.FunctionDef):
            return

        def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef):
            return

        def visit_ClassDef(self, n: ast.ClassDef):
            return

        def visit_Lambda(self, n: ast.Lambda):
            return

        def visit_Yield(self, n: ast.Yield):
            self.found = True

        def visit_YieldFrom(self, n: ast.YieldFrom):
            self.found = True

    v = _V()
    for s in getattr(fn, "body", []) or []:
        v.visit(s)
        if v.found:
            return True
    return False


def _tree_has_yield(node: ast.AST) -> bool:
    if isinstance(node, (ast.Yield, ast.YieldFrom)):
        return True
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return False
    for c in ast.iter_child_nodes(node):
        if _tree_has_yield(c):
            return True
    return False


def _gen_self_attr(name: str, ctx) -> ast.Attribute:
    return ast.Attribute(
        value=ast.Name(id="self", ctx=ast.Load()),
        attr=name,
        ctx=ctx,
    )


# ExcKind ints from Gen_MapExcKind / exception-name-as-value.
_GEN_EXC_KINDS = (
    (1, "Exception"),
    (2, "ValueError"),
    (3, "OSError"),
    (4, "FileNotFoundError"),
    (5, "TypeError"),
    (6, "RuntimeError"),
    (7, "ZeroDivisionError"),
    (8, "AssertionError"),
    (9, "StopIteration"),
    (14, "AttributeError"),
    (15, "KeyError"),
    (16, "NameError"),
    (17, "IndexError"),
    (27, "GeneratorExit"),
)


def _tkind_raise_stmts() -> list[ast.stmt]:
    """Raise the stored ExcKind. `raise self._tkind` is an IDENT named
    `_tkind` and maps to RuntimeError; dispatch by integer instead.
    """
    stmts: list[ast.stmt] = [
        ast.Assign(
            targets=[_gen_self_attr("_tkind_save", ast.Store())],
            value=_gen_self_attr("_tkind", ast.Load()),
        ),
        ast.Assign(
            targets=[_gen_self_attr("_tkind", ast.Store())],
            value=ast.Constant(value=0),
        ),
    ]
    for kind, name in _GEN_EXC_KINDS:
        stmts.append(
            ast.If(
                test=ast.Compare(
                    left=_gen_self_attr("_tkind_save", ast.Load()),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=kind)],
                ),
                body=[
                    ast.Raise(
                        exc=ast.Call(
                            func=ast.Name(id=name, ctx=ast.Load()),
                            args=[],
                            keywords=[],
                        ),
                        cause=None,
                    )
                ],
                orelse=[],
            )
        )
    stmts.append(
        ast.Raise(
            exc=ast.Call(
                func=ast.Name(id="RuntimeError", ctx=ast.Load()),
                args=[],
                keywords=[],
            ),
            cause=None,
        )
    )
    return stmts


def _throw_if_stmt() -> ast.stmt:
    """Call __aim_raise so the kind table lives once per class.

    AIMacro exceptions are a process-wide pending kind, so a raise
    inside __aim_raise is still seen by send()'s Try wrap. Do not
    Return from send here: a Return inside a wrapped try body skips
    the except Fork that runs `except GeneratorExit`.
    """
    return ast.If(
        test=_gen_self_attr("_tkind", ast.Load()),
        body=[
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="self", ctx=ast.Load()),
                        attr="__aim_raise",
                        ctx=ast.Load(),
                    ),
                    args=[],
                    keywords=[],
                )
            )
        ],
        orelse=[],
    )


def _frame_dummy() -> ast.expr:
    """Live gi_frame. `gi_frame = self` is a cyclic OOP instance and
    SmartPrint SEGVs; a tiny hash with f_back=None is printable.
    """
    return ast.Dict(
        keys=[ast.Constant(value="f_back")],
        values=[ast.Constant(value=None)],
    )


_GEN_SKIP_FIELDS = {
    "send",
    "throw",
    "close",
    "__aim_raise",
    "__next__",
    "__iter__",
    "__init__",
    "__class__",
    "__data__",
}


def _genexp_to_fn(node: ast.GeneratorExp, name: str) -> ast.FunctionDef:
    body: list[ast.stmt] = [ast.Expr(value=ast.Yield(value=node.elt))]
    for gen in reversed(node.generators):
        for iff in reversed(gen.ifs):
            body = [ast.If(test=iff, body=body, orelse=[])]
        body = [
            ast.For(target=gen.target, iter=gen.iter, body=body, orelse=[])
        ]
    return ast.FunctionDef(
        name=name,
        args=ast.arguments(
            posonlyargs=[],
            args=[],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=body,
        decorator_list=[],
    )


def _hoist_genexps(tree: ast.AST, counter: list[int], changed: list[bool]) -> ast.AST:
    """(x for x in it) → nested def that yields, then the existing
    generator-function conversion. Isolation golds currently compile
    genexp as LIST_COMP; converting makes next()/send work.
    """

    class _Skip(ast.NodeTransformer):
        def visit_FunctionDef(self, n: ast.FunctionDef):
            return n

        def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef):
            return n

        def visit_ClassDef(self, n: ast.ClassDef):
            return n

        def visit_Lambda(self, n: ast.Lambda):
            return n

        def visit_ListComp(self, n: ast.ListComp):
            return n

        def visit_SetComp(self, n: ast.SetComp):
            return n

        def visit_DictComp(self, n: ast.DictComp):
            return n

        def visit_GeneratorExp(self, n: ast.GeneratorExp):
            if any(g.is_async for g in n.generators):
                return n
            n = self.generic_visit(n)
            counter[0] += 1
            name = f"_aim_gx_{counter[0]}"
            self.pending.append(_genexp_to_fn(n, name))
            changed[0] = True
            return ast.Call(
                func=ast.Name(id=name, ctx=ast.Load()),
                args=[],
                keywords=[],
            )

    def hoist_body(body: list[ast.stmt]) -> list[ast.stmt]:
        out: list[ast.stmt] = []
        for stmt in body:
            r = _Skip()
            r.pending = []
            stmt2 = r.visit(stmt)
            out.extend(r.pending)
            if isinstance(stmt2, ast.FunctionDef):
                stmt2.body = hoist_body(stmt2.body)
            elif isinstance(stmt2, ast.AsyncFunctionDef):
                stmt2.body = hoist_body(stmt2.body)
            elif isinstance(stmt2, ast.ClassDef):
                stmt2.body = hoist_body(stmt2.body)
            out.append(stmt2)
        return out

    class _M(ast.NodeTransformer):
        def visit_Module(self, node: ast.Module):
            node.body = hoist_body(node.body)
            return node

    return _M().visit(tree)


class _GenNameRew(ast.NodeTransformer):
    def __init__(self, mapping: dict[str, str]):
        self.mapping = mapping
        self._skip: set[str] = set()

    def visit_Name(self, n: ast.Name):
        if n.id in self._skip:
            return n
        if n.id in self.mapping:
            return _gen_self_attr(self.mapping[n.id], n.ctx)
        return n

    def _visit_comp(self, n):
        bound: set[str] = set()
        for g in n.generators:
            for x in ast.walk(g.target):
                if isinstance(x, ast.Name):
                    bound.add(x.id)
        old = self._skip
        self._skip = old | bound
        n = self.generic_visit(n)
        self._skip = old
        return n

    def visit_ListComp(self, n: ast.ListComp):
        return self._visit_comp(n)

    def visit_SetComp(self, n: ast.SetComp):
        return self._visit_comp(n)

    def visit_DictComp(self, n: ast.DictComp):
        return self._visit_comp(n)

    def visit_GeneratorExp(self, n: ast.GeneratorExp):
        return self._visit_comp(n)

    def visit_FunctionDef(self, n: ast.FunctionDef):
        return n

    def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef):
        return n

    def visit_ClassDef(self, n: ast.ClassDef):
        return n

    def visit_Lambda(self, n: ast.Lambda):
        return n


class _GenSM:
    def __init__(self, mapping: dict[str, str]):
        self.rew = _GenNameRew(mapping)
        self.states: list[list[ast.stmt]] = [[_throw_if_stmt()]]
        self.cur = 0
        self.it_n = 0
        self.loops: list[tuple[int, int]] = []
        self.wrapped: set[int] = set()

    def news(self) -> int:
        sid = len(self.states)
        self.states.append([_throw_if_stmt()])
        return sid

    def add(self, stmt: ast.stmt):
        self.states[self.cur].append(stmt)

    def rw(self, node):
        return self.rew.visit(node)

    def set_s(self, sid: int) -> ast.Assign:
        return ast.Assign(
            targets=[_gen_self_attr("_s", ast.Store())],
            value=ast.Constant(value=sid),
        )

    def goto(self, sid: int):
        self.add(self.set_s(sid))
        self.add(ast.Continue())

    def yield_to(self, expr: ast.expr | None, nxt: int):
        self.add(self.set_s(nxt))
        self.add(ast.Return(value=expr if expr is not None else ast.Constant(value=None)))

    def stop(self):
        self.add(self.set_s(-1))
        self.add(
            ast.Assign(
                targets=[_gen_self_attr("gi_frame", ast.Store())],
                value=ast.Constant(value=None),
            )
        )
        self.add(
            ast.If(
                test=_gen_self_attr("_closing", ast.Load()),
                body=[ast.Return(value=ast.Constant(value=None))],
                orelse=[
                    ast.Raise(
                        exc=ast.Call(
                            func=ast.Name(id="StopIteration", ctx=ast.Load()),
                            args=[],
                            keywords=[],
                        ),
                        cause=None,
                    )
                ],
            )
        )

    def build(self, stmts: list[ast.stmt], after: int | None):
        i = 0
        while i < len(stmts):
            s = stmts[i]
            rest = stmts[i + 1 :]
            if isinstance(s, ast.For) and _tree_has_yield(s):
                self._for(s, rest, after)
                return
            if isinstance(s, ast.While) and _tree_has_yield(s):
                self._while(s, rest, after)
                return
            if isinstance(s, ast.If) and _tree_has_yield(s):
                self._if(s, rest, after)
                return
            if isinstance(s, ast.Try) and _tree_has_yield(s):
                self._try(s, rest, after)
                return
            if isinstance(s, ast.Expr) and isinstance(s.value, ast.Yield):
                self._yield_stmt(s.value.value, None, rest, after)
                return
            if isinstance(s, ast.Expr) and isinstance(s.value, ast.YieldFrom):
                self._yield_from(s.value.value, None, rest, after)
                return
            if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.value, ast.Yield):
                self._yield_stmt(s.value.value, s.targets[0], rest, after)
                return
            if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.value, ast.YieldFrom):
                self._yield_from(s.value.value, s.targets[0], rest, after)
                return
            if isinstance(s, ast.Return):
                self.stop()
                return
            if isinstance(s, ast.Break) and self.loops:
                self.goto(self.loops[-1][1])
                return
            if isinstance(s, ast.Continue) and self.loops:
                self.goto(self.loops[-1][0])
                return
            self.add(self.rw(s))
            i += 1
        if after is None:
            self.stop()
        else:
            self.goto(after)

    def _yield_stmt(self, expr, target, rest, after):
        nxt = self.news()
        e = self.rw(expr) if expr is not None else ast.Constant(value=None)
        self.yield_to(e, nxt)
        old = self.cur
        self.cur = nxt
        if target is not None:
            self.add(
                ast.Assign(
                    targets=[self.rw(target)],
                    value=_gen_self_attr("_sent", ast.Load()),
                )
            )
        self.build(rest, after)
        self.cur = old

    def _next_or_stop(self, it_attr: str, dest, after_sid: int):
        """next(self.it) into dest; on StopIteration goto after.

        Continue stays outside the Try: AILANG ContinueLoop inside
        Fork (except) does not resume the outer WhileLoop.
        """
        flag = f"_k{self.it_n}"
        self.it_n += 1
        self.add(
            ast.Assign(
                targets=[_gen_self_attr(flag, ast.Store())],
                value=ast.Constant(value=0),
            )
        )
        self.add(
            ast.Try(
                body=[
                    ast.Assign(
                        targets=[dest],
                        value=ast.Call(
                            func=ast.Name(id="next", ctx=ast.Load()),
                            args=[_gen_self_attr(it_attr, ast.Load())],
                            keywords=[],
                        ),
                    )
                ],
                handlers=[
                    ast.ExceptHandler(
                        type=ast.Name(id="StopIteration", ctx=ast.Load()),
                        name=None,
                        body=[
                            ast.Assign(
                                targets=[_gen_self_attr(flag, ast.Store())],
                                value=ast.Constant(value=1),
                            )
                        ],
                    )
                ],
                orelse=[],
                finalbody=[],
            )
        )
        self.add(
            ast.If(
                test=_gen_self_attr(flag, ast.Load()),
                body=[self.set_s(after_sid), ast.Continue()],
                orelse=[],
            )
        )

    def _yield_from(self, expr, target, rest, after):
        # for _v in expr: yield _v  then assign last sent
        it = f"_i{self.it_n}"
        self.it_n += 1
        self.add(
            ast.Assign(
                targets=[_gen_self_attr(it, ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="iter", ctx=ast.Load()),
                    args=[self.rw(expr)],
                    keywords=[],
                ),
            )
        )
        head = self.news()
        after_yf = self.news()
        self.goto(head)
        old = self.cur
        self.cur = head
        tmp = f"_v{self.it_n}"
        self._next_or_stop(it, _gen_self_attr(tmp, ast.Store()), after_yf)
        self.yield_to(_gen_self_attr(tmp, ast.Load()), head)
        self.cur = after_yf
        if target is not None:
            self.add(
                ast.Assign(
                    targets=[self.rw(target)],
                    value=_gen_self_attr("_sent", ast.Load()),
                )
            )
        self.build(rest, after)
        self.cur = old

    def _for(self, s: ast.For, rest, after):
        it = f"_i{self.it_n}"
        self.it_n += 1
        self.add(
            ast.Assign(
                targets=[_gen_self_attr(it, ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="iter", ctx=ast.Load()),
                    args=[self.rw(s.iter)],
                    keywords=[],
                ),
            )
        )
        head = self.news()
        body_s = self.news()
        after_for = self.news() if (rest or after is not None or s.orelse) else None
        if after_for is None:
            after_for = self.news()
        self.goto(head)
        old = self.cur
        self.cur = head
        self._next_or_stop(it, self.rw(s.target), after_for)
        self.goto(body_s)
        self.cur = body_s
        self.loops.append((head, after_for))
        self.build(list(s.body), head)
        self.loops.pop()
        self.cur = after_for
        if s.orelse:
            self.build(list(s.orelse) + rest, after)
        else:
            self.build(rest, after)
        self.cur = old

    def _while(self, s: ast.While, rest, after):
        head = self.news()
        body_s = self.news()
        after_w = self.news() if (rest or after is not None or s.orelse) else self.news()
        self.goto(head)
        old = self.cur
        self.cur = head
        self.add(
            ast.If(
                test=self.rw(s.test),
                body=[self.set_s(body_s), ast.Continue()],
                orelse=[self.set_s(after_w), ast.Continue()],
            )
        )
        self.cur = body_s
        self.loops.append((head, after_w))
        self.build(list(s.body), head)
        self.loops.pop()
        self.cur = after_w
        if s.orelse:
            self.build(list(s.orelse) + rest, after)
        else:
            self.build(rest, after)
        self.cur = old

    def _if(self, s: ast.If, rest, after):
        then_s = self.news()
        else_s = self.news() if s.orelse else None
        join = self.news() if (rest or after is not None) else None
        then_after = join if join is not None else after
        else_after = join if join is not None else after
        if else_s is None:
            els = [self.set_s(join if join is not None else (after if after is not None else -1)), ast.Continue()]
        else:
            els = [self.set_s(else_s), ast.Continue()]
        self.add(
            ast.If(
                test=self.rw(s.test),
                body=[self.set_s(then_s), ast.Continue()],
                orelse=els,
            )
        )
        old = self.cur
        self.cur = then_s
        self.build(list(s.body), then_after if then_after is not None else -1)
        if else_s is not None:
            self.cur = else_s
            self.build(list(s.orelse), else_after if else_after is not None else -1)
        if join is not None:
            self.cur = join
            self.build(rest, after)
        self.cur = old

    def _try(self, s: ast.Try, rest, after):
        join = self.news() if (rest or after is not None) else None
        fin = self.news() if s.finalbody else join
        if fin is None:
            fin = after
        body_s = self.news()
        handler_sids: list[int] = []
        for _h in s.handlers:
            handler_sids.append(self.news())
        self.goto(body_s)
        old = self.cur
        n_before = len(self.states)
        self.cur = body_s
        self.build(list(s.body), fin if isinstance(fin, int) else join)
        wrap_ids = [body_s] + list(range(n_before, len(self.states)))
        flag = f"_kt{self.it_n}"
        self.it_n += 1
        if s.handlers:
            for sid in wrap_ids:
                orig = list(self.states[sid])
                hs = []
                for i, h in enumerate(s.handlers):
                    hs.append(
                        ast.ExceptHandler(
                            type=self.rw(h.type) if h.type is not None else None,
                            name=h.name,
                            body=[
                                ast.Assign(
                                    targets=[_gen_self_attr(flag, ast.Store())],
                                    value=ast.Constant(value=i + 1),
                                )
                            ],
                        )
                    )
                head, tail = orig, []
                if orig and isinstance(orig[-1], (ast.Return, ast.Continue)):
                    if len(orig) >= 2 and isinstance(orig[-2], ast.Assign):
                        head, tail = orig[:-2], orig[-2:]
                    else:
                        head, tail = orig[:-1], orig[-1:]
                wrapped: list[ast.stmt] = [
                    ast.Assign(
                        targets=[_gen_self_attr(flag, ast.Store())],
                        value=ast.Constant(value=0),
                    ),
                    ast.Try(
                        body=head if head else [ast.Pass()],
                        handlers=hs,
                        orelse=[],
                        finalbody=[],
                    ),
                ]
                for i, hsid in enumerate(handler_sids):
                    wrapped.append(
                        ast.If(
                            test=ast.Compare(
                                left=_gen_self_attr(flag, ast.Load()),
                                ops=[ast.Eq()],
                                comparators=[ast.Constant(value=i + 1)],
                            ),
                            body=[self.set_s(hsid), ast.Continue()],
                            orelse=[],
                        )
                    )
                wrapped.extend(tail)
                self.states[sid] = wrapped
                self.wrapped.update(wrap_ids)
        for h, hsid in zip(s.handlers, handler_sids):
            self.cur = hsid
            self.build(list(h.body), fin if isinstance(fin, int) else join)
        if s.finalbody:
            self.cur = fin
            self.build(list(s.finalbody), join if join is not None else after)
        if join is not None:
            self.cur = join
            self.build(rest, after)
        self.cur = old


def _gen_wrap_unwrapped_close(sm: _GenSM) -> None:
    """Swallow GeneratorExit on close in states with no user try.

    Wrap only throw_if. Wrapping the yield Return leaks ExcEnter
    (Return/Continue skip ExcLeave) and SEGVs later next() calls.
    """
    for sid, body in enumerate(sm.states):
        if sid in sm.wrapped:
            continue
        orig = list(body) if body else [_throw_if_stmt()]
        throw_if = orig[0] if orig else _throw_if_stmt()
        rest = orig[1:] if orig else []
        flag = f"_kc{sid}"
        head: list[ast.stmt] = [
            ast.Assign(
                targets=[_gen_self_attr(flag, ast.Store())],
                value=ast.Constant(value=0),
            ),
            ast.Try(
                body=[throw_if],
                handlers=[
                    ast.ExceptHandler(
                        type=ast.Name(id="GeneratorExit", ctx=ast.Load()),
                        name=None,
                        body=[
                            ast.Assign(
                                targets=[_gen_self_attr(flag, ast.Store())],
                                value=ast.Constant(value=1),
                            )
                        ],
                    ),
                    ast.ExceptHandler(
                        type=ast.Name(id="StopIteration", ctx=ast.Load()),
                        name=None,
                        body=[
                            ast.Assign(
                                targets=[_gen_self_attr(flag, ast.Store())],
                                value=ast.Constant(value=2),
                            )
                        ],
                    ),
                    ast.ExceptHandler(
                        type=ast.Name(id="Exception", ctx=ast.Load()),
                        name=None,
                        body=[
                            ast.Assign(
                                targets=[_gen_self_attr(flag, ast.Store())],
                                value=ast.Constant(value=3),
                            )
                        ],
                    ),
                ],
                orelse=[],
                finalbody=[],
            ),
            ast.If(
                test=ast.Compare(
                    left=_gen_self_attr(flag, ast.Load()),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=1)],
                ),
                body=[
                    ast.If(
                        test=_gen_self_attr("_closing", ast.Load()),
                        body=[
                            ast.Assign(
                                targets=[_gen_self_attr("_s", ast.Store())],
                                value=ast.Constant(value=-1),
                            ),
                            ast.Assign(
                                targets=[_gen_self_attr("gi_frame", ast.Store())],
                                value=ast.Constant(value=None),
                            ),
                            ast.Return(value=ast.Constant(value=None)),
                        ],
                        orelse=[
                            ast.Raise(
                                exc=ast.Call(
                                    func=ast.Name(
                                        id="GeneratorExit", ctx=ast.Load()
                                    ),
                                    args=[],
                                    keywords=[],
                                ),
                                cause=None,
                            )
                        ],
                    )
                ],
                orelse=[],
            ),
            ast.If(
                test=ast.Compare(
                    left=_gen_self_attr(flag, ast.Load()),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=2)],
                ),
                body=[
                    ast.If(
                        test=_gen_self_attr("_closing", ast.Load()),
                        body=[
                            ast.Assign(
                                targets=[_gen_self_attr("_s", ast.Store())],
                                value=ast.Constant(value=-1),
                            ),
                            ast.Assign(
                                targets=[_gen_self_attr("gi_frame", ast.Store())],
                                value=ast.Constant(value=None),
                            ),
                            ast.Return(value=ast.Constant(value=None)),
                        ],
                        orelse=[
                            ast.Raise(
                                exc=ast.Call(
                                    func=ast.Name(
                                        id="StopIteration", ctx=ast.Load()
                                    ),
                                    args=[],
                                    keywords=[],
                                ),
                                cause=None,
                            )
                        ],
                    )
                ],
                orelse=[],
            ),
            ast.If(
                test=ast.Compare(
                    left=_gen_self_attr(flag, ast.Load()),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=3)],
                ),
                body=[
                    ast.Assign(
                        targets=[_gen_self_attr("_s", ast.Store())],
                        value=ast.Constant(value=-1),
                    ),
                    ast.Assign(
                        targets=[_gen_self_attr("gi_frame", ast.Store())],
                        value=ast.Constant(value=None),
                    ),
                    ast.Assign(
                        targets=[_gen_self_attr("_tkind", ast.Store())],
                        value=_gen_self_attr("_tkind_save", ast.Load()),
                    ),
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="self", ctx=ast.Load()),
                                attr="__aim_raise",
                                ctx=ast.Load(),
                            ),
                            args=[],
                            keywords=[],
                        )
                    ),
                    ast.Return(value=ast.Constant(value=None)),
                ],
                orelse=[],
            ),
        ]
        sm.states[sid] = head + rest


def _gen_convert(
    fn: ast.FunctionDef, enclosing: set[str], counter: list[int]
) -> tuple[ast.ClassDef, ast.FunctionDef]:
    counter[0] += 1
    cname = f"__aim_gen_{counter[0]}"
    params = [a.arg for a in fn.args.args]
    frees = _clos_freevars(fn, enclosing)
    locs = _clos_direct_assigned(fn)
    mapping: dict[str, str] = {}
    for n in params + list(locs) + frees:
        if n not in mapping and n not in ("_s", "_sent"):
            mapping[n] = f"_g_{n}"
    sm = _GenSM(mapping)
    sm.build(list(fn.body), None)
    _gen_wrap_unwrapped_close(sm)
    init_args = [ast.arg(arg="self")]
    init_body: list[ast.stmt] = [
        ast.Assign(
            targets=[_gen_self_attr("_s", ast.Store())],
            value=ast.Constant(value=0),
        ),
        ast.Assign(
            targets=[_gen_self_attr("_sent", ast.Store())],
            value=ast.Constant(value=None),
        ),
        ast.Assign(
            targets=[_gen_self_attr("_tkind", ast.Store())],
            value=ast.Constant(value=0),
        ),
        ast.Assign(
            targets=[_gen_self_attr("_tkind_save", ast.Store())],
            value=ast.Constant(value=0),
        ),
        ast.Assign(
            targets=[_gen_self_attr("gi_running", ast.Store())],
            value=ast.Constant(value=0),
        ),
        ast.Assign(
            targets=[_gen_self_attr("_closing", ast.Store())],
            value=ast.Constant(value=0),
        ),
        ast.Assign(
            targets=[_gen_self_attr("gi_frame", ast.Store())],
            value=_frame_dummy(),
        ),
    ]
    factory_args: list[ast.expr] = []
    seen_init: set[str] = set()
    param_attrs: set[str] = set()
    for n in params + frees:
        if n in seen_init or n not in mapping:
            continue
        seen_init.add(n)
        pname = mapping[n]
        init_args.append(ast.arg(arg=pname))
        init_body.append(
            ast.Assign(
                targets=[_gen_self_attr(pname, ast.Store())],
                value=ast.Name(id=pname, ctx=ast.Load()),
            )
        )
        factory_args.append(ast.Name(id=n, ctx=ast.Load()))
        param_attrs.add(pname)
    fields: set[str] = set(mapping.values()) | {"_s", "_sent"}
    for body in sm.states:
        for stmt in body:
            for n in ast.walk(stmt):
                if (
                    isinstance(n, ast.Attribute)
                    and isinstance(n.value, ast.Name)
                    and n.value.id == "self"
                    and isinstance(n.ctx, ast.Store)
                ):
                    fields.add(n.attr)
    for attr in sorted(fields):
        if (
            attr
            in (
                "_s",
                "_sent",
                "_tkind",
                "_tkind_save",
                "gi_running",
                "_closing",
                "gi_frame",
            )
            or attr in param_attrs
            or attr in _GEN_SKIP_FIELDS
        ):
            continue
        init_body.append(
            ast.Assign(
                targets=[_gen_self_attr(attr, ast.Store())],
                value=ast.Constant(value=None),
            )
        )
    init = ast.FunctionDef(
        name="__init__",
        args=ast.arguments(
            posonlyargs=[],
            args=init_args,
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=init_body,
        decorator_list=[],
    )
    send_ifs: list[ast.stmt] = [
        ast.If(
            test=ast.Compare(
                left=_gen_self_attr("_s", ast.Load()),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=-1)],
            ),
            body=[
                ast.Assign(
                    targets=[_gen_self_attr("gi_frame", ast.Store())],
                    value=ast.Constant(value=None),
                ),
                ast.If(
                    test=_gen_self_attr("_closing", ast.Load()),
                    body=[ast.Return(value=ast.Constant(value=None))],
                    orelse=[
                        ast.Raise(
                            exc=ast.Call(
                                func=ast.Name(id="StopIteration", ctx=ast.Load()),
                                args=[],
                                keywords=[],
                            ),
                            cause=None,
                        )
                    ],
                ),
            ],
            orelse=[],
        )
    ]
    for sid, body in enumerate(sm.states):
        if not body:
            body = [_throw_if_stmt()]
        send_ifs.append(
            ast.If(
                test=ast.Compare(
                    left=_gen_self_attr("_s", ast.Load()),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=sid)],
                ),
                body=body,
                orelse=[],
            )
        )
    send_ifs.append(
        ast.Raise(
            exc=ast.Call(
                func=ast.Name(id="StopIteration", ctx=ast.Load()),
                args=[],
                keywords=[],
            ),
            cause=None,
        )
    )
    send = ast.FunctionDef(
        name="send",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self"), ast.arg(arg="_aim_v")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            ast.Assign(
                targets=[_gen_self_attr("_sent", ast.Store())],
                value=ast.Name(id="_aim_v", ctx=ast.Load()),
            ),
            ast.Assign(
                targets=[ast.Name(id="_aim_run", ctx=ast.Store())],
                value=ast.Constant(value=True),
            ),
            ast.While(
                test=ast.Name(id="_aim_run", ctx=ast.Load()),
                body=send_ifs,
                orelse=[],
            ),
        ],
        decorator_list=[],
    )
    dunder_next = ast.FunctionDef(
        name="__next__",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            ast.Return(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="self", ctx=ast.Load()),
                        attr="send",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Constant(value=None)],
                    keywords=[],
                )
            )
        ],
        decorator_list=[],
    )
    dunder_iter = ast.FunctionDef(
        name="__iter__",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[ast.Return(value=ast.Name(id="self", ctx=ast.Load()))],
        decorator_list=[],
    )
    aim_raise = ast.FunctionDef(
        name="__aim_raise",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=_tkind_raise_stmts(),
        decorator_list=[],
    )
    throw_closed: list[ast.stmt] = [
        ast.If(
            test=ast.Compare(
                left=_gen_self_attr("_s", ast.Load()),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=-1)],
            ),
            body=[
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="self", ctx=ast.Load()),
                            attr="__aim_raise",
                            ctx=ast.Load(),
                        ),
                        args=[],
                        keywords=[],
                    )
                ),
                ast.Return(value=ast.Constant(value=None)),
            ],
            orelse=[],
        )
    ]
    throw = ast.FunctionDef(
        name="throw",
        args=ast.arguments(
            posonlyargs=[],
            args=[
                ast.arg(arg="self"),
                ast.arg(arg="typ"),
                ast.arg(arg="val"),
                ast.arg(arg="tb"),
            ],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[ast.Constant(value=None), ast.Constant(value=None)],
        ),
        body=[
            ast.Assign(
                targets=[_gen_self_attr("_tkind", ast.Store())],
                value=ast.Name(id="typ", ctx=ast.Load()),
            )
        ]
        + throw_closed
        + [
            ast.Return(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="self", ctx=ast.Load()),
                        attr="send",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Constant(value=None)],
                    keywords=[],
                )
            )
        ],
        decorator_list=[],
    )
    close = ast.FunctionDef(
        name="close",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            ast.If(
                test=ast.Compare(
                    left=_gen_self_attr("_s", ast.Load()),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=-1)],
                ),
                body=[ast.Return(value=ast.Constant(value=None))],
                orelse=[],
            ),
            ast.If(
                test=ast.Compare(
                    left=_gen_self_attr("_s", ast.Load()),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=0)],
                ),
                body=[
                    ast.Assign(
                        targets=[_gen_self_attr("_s", ast.Store())],
                        value=ast.Constant(value=-1),
                    ),
                    ast.Assign(
                        targets=[_gen_self_attr("gi_frame", ast.Store())],
                        value=ast.Constant(value=None),
                    ),
                    ast.Return(value=ast.Constant(value=None)),
                ],
                orelse=[],
            ),
            ast.Assign(
                targets=[_gen_self_attr("_closing", ast.Store())],
                value=ast.Constant(value=1),
            ),
            ast.Assign(
                targets=[_gen_self_attr("_tkind", ast.Store())],
                value=ast.Constant(value=27),
            ),
            ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id="self", ctx=ast.Load()),
                        attr="send",
                        ctx=ast.Load(),
                    ),
                    args=[ast.Constant(value=None)],
                    keywords=[],
                )
            ),
            ast.Assign(
                targets=[_gen_self_attr("_closing", ast.Store())],
                value=ast.Constant(value=0),
            ),
            ast.If(
                test=ast.Compare(
                    left=_gen_self_attr("_s", ast.Load()),
                    ops=[ast.NotEq()],
                    comparators=[ast.Constant(value=-1)],
                ),
                body=[
                    ast.Raise(
                        exc=ast.Call(
                            func=ast.Name(id="RuntimeError", ctx=ast.Load()),
                            args=[
                                ast.Constant(
                                    value="generator ignored GeneratorExit"
                                )
                            ],
                            keywords=[],
                        ),
                        cause=None,
                    )
                ],
                orelse=[],
            ),
            ast.Assign(
                targets=[_gen_self_attr("_s", ast.Store())],
                value=ast.Constant(value=-1),
            ),
            ast.Assign(
                targets=[_gen_self_attr("gi_frame", ast.Store())],
                value=ast.Constant(value=None),
            ),
        ],
        decorator_list=[],
    )
    cls = ast.ClassDef(
        name=cname,
        bases=[],
        keywords=[],
        body=[init, aim_raise, send, dunder_next, dunder_iter, throw, close],
        decorator_list=[],
    )
    new_fn = ast.FunctionDef(
        name=fn.name,
        args=fn.args,
        body=[
            ast.Return(
                value=ast.Call(
                    func=ast.Name(id=cname, ctx=ast.Load()),
                    args=factory_args,
                    keywords=[],
                )
            )
        ],
        decorator_list=list(fn.decorator_list),
        returns=fn.returns,
    )
    return cls, new_fn


def _for_to_while(node: ast.For, counter: list[int]) -> list[ast.stmt]:
    """for x in e → iter/next loop. Gen_For uses IterLen/IterGet, which
    treats an OOP generator as a dict (Hash.Keys). Files with generator
    functions rewrite remaining for-loops so `for x in gen()` works.
    `_aim_gr` is a dedicated while flag: codegen `while True` reuses
    `_aim_t0`, and ContinueLoop then sees a falsy last temp.
    """
    counter[0] += 1
    n = counter[0]
    it = f"_aim_gi{n}"
    st = f"_aim_gs{n}"
    run = f"_aim_gr{n}"
    nxt = ast.Assign(
        targets=[node.target],
        value=ast.Call(
            func=ast.Name(id="next", ctx=ast.Load()),
            args=[ast.Name(id=it, ctx=ast.Load())],
            keywords=[],
        ),
    )
    orelse = list(node.orelse) if node.orelse else []
    return [
        ast.Assign(
            targets=[ast.Name(id=it, ctx=ast.Store())],
            value=ast.Call(
                func=ast.Name(id="iter", ctx=ast.Load()),
                args=[node.iter],
                keywords=[],
            ),
        ),
        ast.Assign(
            targets=[ast.Name(id=run, ctx=ast.Store())],
            value=ast.Constant(value=True),
        ),
        ast.While(
            test=ast.Name(id=run, ctx=ast.Load()),
            body=[
                ast.Assign(
                    targets=[ast.Name(id=st, ctx=ast.Store())],
                    value=ast.Constant(value=0),
                ),
                ast.Try(
                    body=[nxt],
                    handlers=[
                        ast.ExceptHandler(
                            type=ast.Name(id="StopIteration", ctx=ast.Load()),
                            name=None,
                            body=[
                                ast.Assign(
                                    targets=[ast.Name(id=st, ctx=ast.Store())],
                                    value=ast.Constant(value=1),
                                )
                            ],
                        )
                    ],
                    orelse=[],
                    finalbody=[],
                ),
                ast.If(
                    test=ast.Name(id=st, ctx=ast.Load()),
                    body=orelse + [ast.Break()],
                    orelse=[],
                ),
            ]
            + list(node.body),
            orelse=[],
        ),
    ]


def _rewrite_for_over_gens(tree: ast.AST, gen_names: set[str]) -> ast.AST:
    """Rewrite `for x in genfunc(...)` only. Rewriting every for-loop
    in a file that contains a generator turns `for k in d.keys()` into
    iter(keys-view), which AIMacro rejects as not iterable (shelve).
    """
    if not gen_names:
        return tree
    counter = [0]

    class _F(ast.NodeTransformer):
        def visit_For(self, node: ast.For):
            node = self.generic_visit(node)
            it = node.iter
            if (
                isinstance(it, ast.Call)
                and isinstance(it.func, ast.Name)
                and it.func.id in gen_names
            ):
                return _for_to_while(node, counter)
            return node

        def visit_ListComp(self, node):
            return node

        def visit_SetComp(self, node):
            return node

        def visit_DictComp(self, node):
            return node

        def visit_GeneratorExp(self, node):
            return node

    return _F().visit(tree)


def desugar_generators(src: str) -> str:
    """Generator functions → class with __next__/send (pause at yield).

    Codegen currently collects yields into a list and runs the body at
    call time, so `g = f()` already prints side effects. Isolation files
    without generator functions stay byte-identical.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    counter = [0]
    changed = [False]
    gen_names: set[str] = set()
    tree = _hoist_genexps(tree, counter, changed)

    class _G(ast.NodeTransformer):
        def __init__(self):
            self.stack: list[set[str]] = []

        def _visit_fn(self, node: ast.FunctionDef, hoisted: list[ast.stmt]):
            assigned = _clos_direct_assigned(node)
            self.stack.append(assigned | {node.name})
            inner_h: list[ast.stmt] = []
            new_body: list[ast.stmt] = []
            for stmt in node.body:
                if isinstance(stmt, ast.FunctionDef):
                    new_body.append(self._visit_fn(stmt, inner_h))
                elif isinstance(stmt, ast.AsyncFunctionDef):
                    new_body.append(stmt)
                elif isinstance(stmt, ast.ClassDef):
                    new_body.append(self.visit(stmt))
                else:
                    new_body.append(stmt)
            self.stack.pop()
            node.body = inner_h + new_body
            if _fn_own_yields(node) and not node.decorator_list:
                enclosing: set[str] = set()
                for e in self.stack:
                    enclosing |= e
                cls, fn = _gen_convert(node, enclosing, counter)
                hoisted.append(cls)
                changed[0] = True
                gen_names.add(node.name)
                return fn
            return node

        def visit_Module(self, node: ast.Module):
            self.stack.append(set())
            hoisted: list[ast.stmt] = []
            new_body: list[ast.stmt] = []
            for stmt in node.body:
                if isinstance(stmt, ast.FunctionDef):
                    new_body.append(self._visit_fn(stmt, hoisted))
                elif isinstance(stmt, ast.ClassDef):
                    new_body.append(self.visit(stmt))
                else:
                    new_body.append(stmt)
            self.stack.pop()
            node.body = hoisted + new_body
            return node

        def visit_ClassDef(self, node: ast.ClassDef):
            hoisted: list[ast.stmt] = []
            new_body: list[ast.stmt] = []
            for stmt in node.body:
                if isinstance(stmt, ast.FunctionDef):
                    new_body.append(self._visit_fn(stmt, hoisted))
                elif isinstance(stmt, ast.ClassDef):
                    new_body.append(self.visit(stmt))
                else:
                    new_body.append(stmt)
            node.body = hoisted + new_body
            return node

    new_tree = _G().visit(tree)
    if not changed[0]:
        return src
    new_tree = _rewrite_for_over_gens(new_tree, gen_names)
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree) + "\n"
    except Exception:
        return src


def desugar_nested_class_cells(src: str) -> str:
    """Capture enclosing locals used by nested class methods into a module dict.

    Codegen flattens nested class methods to top-level Functions without closures.
    Mutating module-level `_aim_ncells` needs no `global` (aimacro has no global).
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    cell_counter = [0]
    need_dict = [False]

    class _Cell(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef):
            self.generic_visit(node)
            assigned: set[str] = set()
            for n in ast.walk(node):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    assigned.add(n.id)
            for a in node.args.args + node.args.kwonlyargs:
                assigned.add(a.arg)
            if node.args.vararg:
                assigned.add(node.args.vararg.arg)
            if node.args.kwarg:
                assigned.add(node.args.kwarg.arg)

            new_body: list[ast.stmt] = []
            cell_maps: list[tuple[str, str]] = []
            for stmt in node.body:
                if isinstance(stmt, ast.ClassDef):
                    used: set[str] = set()
                    method_locals: dict[int, set[str]] = {}
                    for i, item in enumerate(stmt.body):
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            ml: set[str] = {a.arg for a in item.args.args}
                            for a in item.args.kwonlyargs:
                                ml.add(a.arg)
                            for n in ast.walk(item):
                                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                                    ml.add(n.id)
                            method_locals[i] = ml
                            for n in ast.walk(item):
                                if (
                                    isinstance(n, ast.Name)
                                    and isinstance(n.ctx, ast.Load)
                                    and n.id in assigned
                                    and n.id not in ml
                                    and n.id != stmt.name
                                    and not n.id.startswith("_aim_ncell")
                                ):
                                    used.add(n.id)
                    if used:
                        has_call = any(
                            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and item.name == "__call__"
                            for item in stmt.body
                        )
                        # __call__ + enclosing freevars: per-call cell in
                        # desugar_nested_func_closures (SmartCall1 on the
                        # instance SEGVs; bound hash + self._c is the fix).
                        if has_call:
                            new_body.append(stmt)
                            continue
                        cell_counter[0] += 1
                        cid = cell_counter[0]
                        need_dict[0] = True
                        mapping = {v: f"{cid}_{v}" for v in sorted(used)}
                        for v, key in mapping.items():
                            cell_maps.append((v, key))
                            new_body.append(
                                ast.Assign(
                                    targets=[
                                        ast.Subscript(
                                            value=ast.Name(id="_aim_ncells", ctx=ast.Load()),
                                            slice=ast.Constant(value=key),
                                            ctx=ast.Store(),
                                        )
                                    ],
                                    value=ast.Name(id=v, ctx=ast.Load()),
                                )
                            )

                        class _Rew(ast.NodeTransformer):
                            def __init__(self, ml: set[str]):
                                self.ml = ml

                            def visit_Name(self, n: ast.Name):
                                if (
                                    isinstance(n.ctx, ast.Load)
                                    and n.id in mapping
                                    and n.id not in self.ml
                                ):
                                    return ast.Subscript(
                                        value=ast.Name(id="_aim_ncells", ctx=ast.Load()),
                                        slice=ast.Constant(value=mapping[n.id]),
                                        ctx=ast.Load(),
                                    )
                                return n

                        new_cls_body = []
                        for i, item in enumerate(stmt.body):
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                new_cls_body.append(_Rew(method_locals[i]).visit(item))
                            else:
                                new_cls_body.append(item)
                        stmt = ast.ClassDef(
                            name=stmt.name,
                            bases=stmt.bases,
                            keywords=stmt.keywords,
                            body=new_cls_body,
                            decorator_list=stmt.decorator_list,
                            type_params=getattr(stmt, "type_params", []),
                        )
                new_body.append(stmt)
            if cell_maps:
                patched: list[ast.stmt] = []
                for stmt in new_body:
                    patched.append(stmt)
                    names: list[str] = []
                    if isinstance(stmt, ast.Assign):
                        for t in stmt.targets:
                            if isinstance(t, ast.Name):
                                names.append(t.id)
                    elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                        names.append(stmt.target.id)
                    elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
                        names.append(stmt.target.id)
                    for v, key in cell_maps:
                        if v in names:
                            patched.append(
                                ast.Assign(
                                    targets=[
                                        ast.Subscript(
                                            value=ast.Name(id="_aim_ncells", ctx=ast.Load()),
                                            slice=ast.Constant(value=key),
                                            ctx=ast.Store(),
                                        )
                                    ],
                                    value=ast.Name(id=v, ctx=ast.Load()),
                                )
                            )
                new_body = patched
            node.body = new_body
            return node

    new_tree = _Cell().visit(tree)
    if need_dict[0]:
        # prepend _aim_ncells = {} at module level
        assign = ast.Assign(
            targets=[ast.Name(id="_aim_ncells", ctx=ast.Store())],
            value=ast.Dict(keys=[], values=[]),
        )
        new_tree.body.insert(0, assign)
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree) + "\n"
    except Exception:
        return src


_CLOS_SKIP = {
    "self",
    "cls",
    "True",
    "False",
    "None",
    "_aim_c",
    "_aim_ncells",
}


def _clos_params(node: ast.AST) -> set[str]:
    if not hasattr(node, "args"):
        return set()
    names = {a.arg for a in node.args.args + node.args.kwonlyargs}
    if node.args.vararg:
        names.add(node.args.vararg.arg)
    if node.args.kwarg:
        names.add(node.args.kwarg.arg)
    return names


def _clos_direct_assigned(node: ast.AST) -> set[str]:
    """Params plus stores in this function, not in nested def/class bodies."""
    assigned = _clos_params(node)
    body = getattr(node, "body", None) or []
    for stmt in body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for n in ast.walk(stmt):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                assigned.add(n.id)
    return assigned


def _clos_inner_locals(node: ast.AST) -> set[str]:
    locs = _clos_params(node)
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            locs.add(n.id)
    return locs


def _clos_freevars(inner: ast.AST, enclosing: set[str]) -> list[str]:
    iloc = _clos_inner_locals(inner)
    for n in ast.walk(inner):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            iloc.add(n.name)
    seen: list[str] = []
    for n in ast.walk(inner):
        if (
            isinstance(n, ast.Name)
            and isinstance(n.ctx, ast.Load)
            and n.id in enclosing
            and n.id not in iloc
            and n.id not in _CLOS_SKIP
            and n.id not in seen
        ):
            seen.append(n.id)
    return seen


def _lambda_needs_hoist(lam: ast.AST, enclosing: set[str]) -> bool:
    """True if this lambda closes over enclosing names or a nested
    lambda/def loads this lambda's params (the f1 / extra-nesting case)."""
    if not isinstance(lam, ast.Lambda):
        return bool(_clos_freevars(lam, enclosing))
    if _clos_freevars(lam, enclosing):
        return True
    owned = _clos_params(lam)
    inner_env = enclosing | owned
    for n in ast.walk(lam):
        if n is lam:
            continue
        if isinstance(n, ast.Lambda):
            if _clos_freevars(n, owned) or _lambda_needs_hoist(n, inner_env):
                return True
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _clos_freevars(n, owned):
                return True
    return False


def _hoist_in_stmts(
    body: list[ast.stmt],
    enclosing: set[str],
    counter: list[int],
    changed: list[bool],
) -> list[ast.stmt]:
    """Lift closure lambdas in *body* to nested FunctionDefs.

    Nested lambdas are lifted into the new FunctionDef so extra-nesting
    can pass the per-call cell through. Lambdas with no freevars stay
    as Lambda (isolation golds with `lambda: None` stay byte-identical).
    """
    hoisted: list[ast.stmt] = []

    class _R(ast.NodeTransformer):
        def visit_FunctionDef(self, n: ast.FunctionDef):
            return n

        def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef):
            return n

        def visit_ClassDef(self, n: ast.ClassDef):
            return n

        def visit_Lambda(self, n: ast.Lambda):
            if not _lambda_needs_hoist(n, enclosing):
                return n
            changed[0] = True
            counter[0] += 1
            name = f"_aim_lam_{counter[0]}"
            fn = ast.FunctionDef(
                name=name,
                args=n.args,
                body=[ast.Return(value=n.body)],
                decorator_list=[],
            )
            owned = _clos_direct_assigned(fn)
            fn.body = _hoist_in_stmts(
                fn.body, enclosing | owned, counter, changed
            )
            hoisted.append(fn)
            return ast.Name(id=name, ctx=ast.Load())

    new_body = [_R().visit(s) for s in body]
    return hoisted + new_body


def _hoist_lambdas_tree(
    tree: ast.AST, counter: list[int], changed: list[bool]
) -> ast.AST:
    """Pre-pass: lambda with freevars → nested def, then existing cell desugar."""

    class _H(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef):
            node = self.generic_visit(node)
            enclosing = _clos_direct_assigned(node)
            node.body = _hoist_in_stmts(
                list(node.body), enclosing, counter, changed
            )
            return node

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Module(self, node: ast.Module):
            node = self.generic_visit(node)
            # Module names are globals, not cells. Only hoist nested-lambda
            # owners (lambda x: lambda y: x + y) at module level.
            node.body = _hoist_in_stmts(
                list(node.body), set(), counter, changed
            )
            return node

    return _H().visit(tree)


class _ClosRewrite(ast.NodeTransformer):
    def __init__(self, mapping: dict[str, str], cell: str, via_self: bool):
        self.mapping = mapping
        self.cell = cell
        self.via_self = via_self

    def _cell(self) -> ast.expr:
        if self.via_self:
            return ast.Attribute(
                value=ast.Name(id="self", ctx=ast.Load()),
                attr="_c",
                ctx=ast.Load(),
            )
        return ast.Name(id=self.cell, ctx=ast.Load())

    def _sub(self, name: str, ctx):
        return ast.Subscript(
            value=self._cell(),
            slice=ast.Constant(value=self.mapping[name]),
            ctx=ctx,
        )

    def visit_Name(self, node: ast.Name):
        if node.id in self.mapping:
            return self._sub(node.id, node.ctx)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Already-converted __aim_clos_ methods: rewrite freevar Names
        # (f8 middle scope). Other nested defs stay intact for convert.
        if node.name in ("__init__", "__call__"):
            return self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        return node

    def visit_ClassDef(self, node: ast.ClassDef):
        if str(node.name).startswith("__aim_clos_"):
            return self.generic_visit(node)
        return node

    def visit_Lambda(self, node: ast.Lambda):
        return node


def _clos_copy_parent_into_cell(
    body: list[ast.stmt], mapping: dict[str, str]
) -> list[ast.stmt]:
    """After a child `_aim_c = {}`, copy parent cell keys into it.

    f8 / mixed freevars: middle def already built a cell for its own
    locals (b); parent freevars (z, y) must be copied so the inner
    class, whose self._c is that dict, can load them.
    """
    if not mapping:
        return body
    out: list[ast.stmt] = []
    for stmt in body:
        out.append(stmt)
        if (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], ast.Name)
            and stmt.targets[0].id == "_aim_c"
            and isinstance(stmt.value, ast.Dict)
        ):
            for key in mapping.values():
                out.append(
                    ast.Assign(
                        targets=[
                            ast.Subscript(
                                value=ast.Name(id="_aim_c", ctx=ast.Load()),
                                slice=ast.Constant(value=key),
                                ctx=ast.Store(),
                            )
                        ],
                        value=ast.Subscript(
                            value=_clos_self_c(),
                            slice=ast.Constant(value=key),
                            ctx=ast.Load(),
                        ),
                    )
                )
    return out


def _clos_self_c() -> ast.expr:
    return ast.Attribute(
        value=ast.Name(id="self", ctx=ast.Load()),
        attr="_c",
        ctx=ast.Load(),
    )


def _clos_bound_value(cname: str, cell_expr: ast.expr) -> ast.Dict:
    return ast.Dict(
        keys=[
            ast.Constant(value="__bound__"),
            ast.Constant(value="obj"),
            ast.Constant(value="name"),
        ],
        values=[
            ast.Constant(value=1),
            ast.Call(
                func=ast.Name(id=cname, ctx=ast.Load()),
                args=[cell_expr],
                keywords=[],
            ),
            ast.Constant(value="__call__"),
        ],
    )


def _clos_class(
    cname: str,
    inner: ast.FunctionDef,
    mapping: dict[str, str],
    enclosing: set[str],
    counter: list[int],
    changed: list[bool],
) -> ast.ClassDef:
    """class C: def __init__(self, _c): self._c = _c
    def __call__(self, ...inner args...): rewritten body.

    Nested defs in the body are converted against the same cell (self._c)
    so extra() can pass x through to adder without loading x.
    """
    init = ast.FunctionDef(
        name="__init__",
        args=ast.arguments(
            posonlyargs=[],
            args=[
                ast.arg(arg="self"),
                ast.arg(arg="_c"),
            ],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            ast.Assign(
                targets=[
                    ast.Attribute(
                        value=ast.Name(id="self", ctx=ast.Load()),
                        attr="_c",
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Name(id="_c", ctx=ast.Load()),
            )
        ],
        decorator_list=[],
    )
    call_args = ast.arguments(
        posonlyargs=[],
        args=[ast.arg(arg="self")] + list(inner.args.args),
        vararg=inner.args.vararg,
        kwonlyargs=list(inner.args.kwonlyargs),
        kw_defaults=list(inner.args.kw_defaults),
        kwarg=inner.args.kwarg,
        defaults=list(inner.args.defaults),
    )
    call_body = [_ClosRewrite(mapping, "_c", True).visit(s) for s in inner.body]
    call_body = _clos_copy_parent_into_cell(call_body, mapping)
    call_body, _frees = _clos_replace_nested(
        call_body, enclosing, _clos_self_c(), counter, changed
    )
    if not call_body:
        call_body = [ast.Pass()]
    call = ast.FunctionDef(
        name="__call__",
        args=call_args,
        body=call_body,
        decorator_list=[],
        returns=inner.returns,
    )
    return ast.ClassDef(
        name=cname,
        bases=[],
        keywords=[],
        body=[init, call],
        decorator_list=[],
    )


def _class_has_call(cls: ast.ClassDef) -> bool:
    return any(
        isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == "__call__"
        for item in cls.body
    )


def _clos_class_method_freevars(
    cls: ast.ClassDef, enclosing: set[str]
) -> list[str]:
    seen: list[str] = []
    for item in cls.body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        ml = _clos_inner_locals(item)
        ml.add(item.name)
        for n in ast.walk(item):
            if (
                isinstance(n, ast.Name)
                and isinstance(n.ctx, ast.Load)
                and n.id in enclosing
                and n.id not in ml
                and n.id not in _CLOS_SKIP
                and n.id != cls.name
                and n.id not in seen
            ):
                seen.append(n.id)
    return seen


def _clos_init_c_assign() -> ast.Assign:
    return ast.Assign(
        targets=[
            ast.Attribute(
                value=ast.Name(id="self", ctx=ast.Load()),
                attr="_c",
                ctx=ast.Store(),
            )
        ],
        value=ast.Name(id="_c", ctx=ast.Load()),
    )


def _rewrite_method_freevars(
    fn: ast.FunctionDef, mapping: dict[str, str]
) -> ast.FunctionDef:
    class _M(ast.NodeTransformer):
        def visit_Name(self, n: ast.Name):
            if n.id in mapping:
                return ast.Subscript(
                    value=_clos_self_c(),
                    slice=ast.Constant(value=mapping[n.id]),
                    ctx=n.ctx,
                )
            return n

        def visit_FunctionDef(self, n: ast.FunctionDef):
            return n

        def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef):
            return n

        def visit_ClassDef(self, n: ast.ClassDef):
            return n

        def visit_Lambda(self, n: ast.Lambda):
            return n

    fn.body = [_M().visit(s) for s in fn.body]
    return fn


def _clos_patch_nested_class(
    cls: ast.ClassDef, mapping: dict[str, str]
) -> ast.ClassDef:
    """Inject __init__(self, _c) and rewrite method freevars to self._c."""
    new_body: list[ast.stmt] = []
    has_init = False
    for item in cls.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name == "__init__":
                has_init = True
                args = item.args
                rest = list(args.args)
                if rest and rest[0].arg in ("self", "cls"):
                    new_args = [rest[0], ast.arg(arg="_c")] + rest[1:]
                else:
                    new_args = [ast.arg(arg="self"), ast.arg(arg="_c")] + rest
                item.args = ast.arguments(
                    posonlyargs=list(args.posonlyargs),
                    args=new_args,
                    vararg=args.vararg,
                    kwonlyargs=list(args.kwonlyargs),
                    kw_defaults=list(args.kw_defaults),
                    kwarg=args.kwarg,
                    defaults=list(args.defaults),
                )
                item.body = [_clos_init_c_assign()] + list(item.body)
            item = _rewrite_method_freevars(item, mapping)
            new_body.append(item)
        else:
            new_body.append(item)
    if not has_init:
        init = ast.FunctionDef(
            name="__init__",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg="self"), ast.arg(arg="_c")],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=[_clos_init_c_assign()],
            decorator_list=[],
        )
        new_body.insert(0, init)
    return ast.ClassDef(
        name=cls.name,
        bases=list(cls.bases),
        keywords=list(cls.keywords),
        body=new_body,
        decorator_list=list(cls.decorator_list),
    )


def _clos_rewrite_ctors(
    body: list[ast.stmt],
    ctor_kind: dict[str, str],
    cell_expr: ast.expr,
) -> list[ast.stmt]:
    """Adder() → bound hash / Adder(_aim_c) so SmartCall1 does not SEGV."""

    class _C(ast.NodeTransformer):
        def visit_ClassDef(self, n: ast.ClassDef):
            return n

        def visit_Call(self, n: ast.Call):
            n = self.generic_visit(n)
            if isinstance(n.func, ast.Name) and n.func.id in ctor_kind:
                n.args = [cell_expr] + list(n.args)
                if ctor_kind[n.func.id] == "bound":
                    return ast.Dict(
                        keys=[
                            ast.Constant(value="__bound__"),
                            ast.Constant(value="obj"),
                            ast.Constant(value="name"),
                        ],
                        values=[
                            ast.Constant(value=1),
                            n,
                            ast.Constant(value="__call__"),
                        ],
                    )
            return n

    return [
        s if isinstance(s, ast.ClassDef) else _C().visit(s) for s in body
    ]


def _clos_replace_nested(
    body: list[ast.stmt],
    enclosing: set[str],
    cell_expr: ast.expr,
    counter: list[int],
    changed: list[bool],
) -> tuple[list[ast.stmt], list[tuple[str, str]]]:
    """Turn nested defs that close over enclosing names into bound classes."""
    new_body: list[ast.stmt] = []
    cell_maps: list[tuple[str, str]] = []
    renames: dict[str, str] = {}
    ctor_kind: dict[str, str] = {}
    for stmt in body:
        if isinstance(stmt, ast.FunctionDef):
            frees = _clos_freevars(stmt, enclosing)
            if frees:
                changed[0] = True
                counter[0] += 1
                cid = counter[0]
                cname = f"__aim_clos_{cid}"
                fn_name = f"_aim_fn_{cid}"
                mapping = {v: v for v in frees}
                for v in frees:
                    if (v, v) not in cell_maps:
                        cell_maps.append((v, v))
                new_body.append(
                    _clos_class(cname, stmt, mapping, enclosing, counter, changed)
                )
                new_body.append(
                    ast.Assign(
                        targets=[ast.Name(id=fn_name, ctx=ast.Store())],
                        value=_clos_bound_value(cname, cell_expr),
                    )
                )
                renames[stmt.name] = fn_name
                continue
        if isinstance(stmt, ast.ClassDef):
            frees = _clos_class_method_freevars(stmt, enclosing)
            if frees and _class_has_call(stmt):
                changed[0] = True
                mapping = {v: v for v in frees}
                for v in frees:
                    if (v, v) not in cell_maps:
                        cell_maps.append((v, v))
                new_body.append(_clos_patch_nested_class(stmt, mapping))
                ctor_kind[stmt.name] = "bound"
                continue
        new_body.append(stmt)
    if ctor_kind:
        new_body = _clos_rewrite_ctors(new_body, ctor_kind, cell_expr)
    if renames:

        class _Ren(ast.NodeTransformer):
            def visit_Name(self, n: ast.Name):
                if n.id in renames:
                    return ast.Name(id=renames[n.id], ctx=n.ctx)
                return n

            def visit_ClassDef(self, n: ast.ClassDef):
                return n

        new_body = [
            s
            if isinstance(s, ast.ClassDef) and str(s.name).startswith("__aim_clos_")
            else _Ren().visit(s)
            for s in new_body
        ]
    return new_body, cell_maps


def desugar_nested_func_closures(src: str) -> str:
    """Nested def/lambda/class with freevars → per-call cell dict + callable class.

    Codegen flattens nested Functions and stores freevars in one PyMod.x,
    so make_adder(1) then make_adder(10) share the cell. Isolation golds
    that only close over self/cls are left byte-identical. Lambdas are
    lifted to nested defs first so the same cell path applies. Nested
    class with __call__ gets __init__(self, _c) and a bound-hash ctor.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    counter = [0]
    changed = [False]
    tree = _hoist_lambdas_tree(tree, counter, changed)

    class _X(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef):
            node = self.generic_visit(node)
            enclosing = _clos_direct_assigned(node)
            cell_name = "_aim_c"
            new_body, cell_maps = _clos_replace_nested(
                list(node.body),
                enclosing,
                ast.Name(id=cell_name, ctx=ast.Load()),
                counter,
                changed,
            )
            if cell_maps:
                inits: list[ast.stmt] = [
                    ast.Assign(
                        targets=[ast.Name(id=cell_name, ctx=ast.Store())],
                        value=ast.Dict(keys=[], values=[]),
                    )
                ]
                for v, key in cell_maps:
                    inits.append(
                        ast.Assign(
                            targets=[
                                ast.Subscript(
                                    value=ast.Name(id=cell_name, ctx=ast.Load()),
                                    slice=ast.Constant(value=key),
                                    ctx=ast.Store(),
                                )
                            ],
                            value=ast.Name(id=v, ctx=ast.Load()),
                        )
                    )
                mapping = {v: k for v, k in cell_maps}
                rewritten = []
                for stmt in new_body:
                    if isinstance(stmt, ast.ClassDef) and stmt.name.startswith(
                        "__aim_clos_"
                    ):
                        rewritten.append(stmt)
                    else:
                        rewritten.append(
                            _ClosRewrite(mapping, cell_name, False).visit(stmt)
                        )
                node.body = inits + rewritten
            else:
                node.body = new_body
            return node

        visit_AsyncFunctionDef = visit_FunctionDef

    new_tree = _X().visit(tree)
    if not changed[0]:
        return src
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree) + "\n"
    except Exception:
        return src


def desugar_dict_call(src: str) -> str:
    """dict(a=1, b=2) → {'a': 1, 'b': 2} so keyword args survive AIMacro CALL."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src

    class _DictKw(ast.NodeTransformer):
        def visit_Call(self, node):
            self.generic_visit(node)
            if not isinstance(node.func, ast.Name) or node.func.id != "dict":
                return node
            if node.args or not node.keywords:
                return node
            keys = []
            vals = []
            for kw in node.keywords:
                if kw.arg is None:
                    return node
                keys.append(ast.Constant(kw.arg))
                vals.append(kw.value)
            return ast.copy_location(ast.Dict(keys=keys, values=vals), node)

    try:
        return ast.unparse(_DictKw().visit(tree)) + "\n"
    except Exception:
        return src


def convert(src: str) -> str:
    # Empty / whitespace-only modules (e.g. empty __init__.py): aimacro.x
    # rejects zero-byte input. Emit a bare `pass` so transpile succeeds.
    if not src or not src.strip():
        return "pass\n"
    # match/case already desugared if called via main;
    # accept raw match too when convert() used alone
    if re.search(r"(?m)^\s*match\s+.+:\s*(#.*)?$", src):
        src = desugar_match(src)
    src = desugar_pep695_type_params(src)
    src = desugar_starargs_annotations(src)
    src = desugar_nameerror_probe(src)
    src = desugar_yield(src)
    src = desugar_from_import_as(src)
    src = desugar_tuple_unpack(src)
    src = desugar_for_unpack(src)
    src = desugar_generators(src)
    src = desugar_nested_class_cells(src)
    src = desugar_nested_func_closures(src)
    src = desugar_dict_call(src)
    """Insert `{` / `}` from indentation. Preserve comments."""
    raw_lines = src.splitlines()
    if src.endswith("\n"):
        raw_lines.append("")  # dummy to flush dedents; dropped if empty

    out: list[str] = []
    stack = [0]
    i = 0
    n = len(raw_lines)
    qstate: str | None = None
    # >0 while inside an unclosed ([{ on a suite header (multiline def/class)
    header_depth = 0
    header_indent = 0

    def is_blank_or_comment(s: str) -> bool:
        t = s.strip()
        return t == "" or t.startswith("#")

    while i < n:
        line = raw_lines[i]
        if i == n - 1 and line == "" and src.endswith("\n"):
            # flush remaining closes
            while len(stack) > 1:
                pad = " " * stack[-2]
                out.append(f"{pad}}}")
                stack.pop()
            break

        # Docstrings / multi-line strings: do not treat colons as suites.
        if qstate:
            out.append(line)
            qstate = _advance_quote_state(line, qstate)
            i += 1
            continue

        if is_blank_or_comment(line):
            out.append(line)
            i += 1
            continue

        ws = _leading_ws(line)
        width = _indent_width(ws)
        code, comment = _code_part(line[len(ws) :])
        first = _stmt_first(code)
        line_q = _advance_quote_state(line, None)

        # Dedent: close braces. else/elif/except/finally share the brace.
        # need_cont_close: True when we popped an indented body and will emit
        # `} else` / `} elif`. False when the previous sibling was a one-liner
        # `if x { stmt }` that already self-closed — then just `else { ... }`.
        need_cont_close = False
        while width < stack[-1]:
            stack.pop()
            pad = " " * stack[-1]
            if width == stack[-1] and first in CONTINUE_SUITE:
                # `} else {` on this line — brace emitted with the keyword
                need_cont_close = True
                break
            out.append(f"{pad}}}")

        if width == stack[-1] and first in CONTINUE_SUITE:
            # replace implicit close: emit `} else {` using this line's indent
            # Backslash-continued headers: elif a and \<nl> b:  →  } elif a and b {
            # Paren-continued headers: elif (a and\n b): → } elif (a and\n b) {
            #   (do NOT open '{' until the signature ':' closes — same as if/def header_depth)
            # One-liner continue-suite: else: stmt / elif x: stmt → else { stmt }
            parts = [code]
            cont_i = i
            cont_comment = comment
            while _endswith_cont(parts[-1]) and cont_i + 1 < n:
                cont_i += 1
                nline = raw_lines[cont_i]
                nws = _leading_ws(nline)
                ncode, ncomment = _code_part(nline[len(nws) :])
                parts.append(ncode)
                if ncomment:
                    cont_comment = ncomment
            body = _join_cont_codes(parts)
            close = "} " if need_cont_close else ""
            if body.endswith(":"):
                body = body[:-1].rstrip()
                extra = ""
                if cont_comment:
                    extra = "  " + cont_comment
                out.append(f"{ws}{close}{body} {{{extra}")
                i = cont_i + 1
                j = i
                while j < n and is_blank_or_comment(raw_lines[j]):
                    j += 1
                if j < n:
                    nxt_w = _indent_width(_leading_ws(raw_lines[j]))
                    if nxt_w > width:
                        stack.append(nxt_w)
                qstate = _advance_quote_state(raw_lines[cont_i], None)
                continue
            # One-liner: else: stmt  /  elif cond: stmt  /  except E: stmt
            # Suite colon only (ignore slice/dict/lambda ':' inside brackets)
            colon = _suite_colon_index(body)
            if colon != -1 and colon < len(body) - 1:
                head = body[:colon].rstrip()
                tail = body[colon + 1 :].strip()
                extra = ""
                if cont_comment:
                    extra = "  " + cont_comment
                out.append(f"{ws}{close}{head} {{ {tail} }}{extra}")
                i = cont_i + 1
                qstate = _advance_quote_state(raw_lines[cont_i], None)
                continue
            # Incomplete continue-suite header (open parens, no ':' yet).
            # Close prior suite with `}` then emit the partial line; header_depth
            # finishes when a later line ends with ':'.
            if cont_i > i:
                # Unusual: backslash join without colon — emit joined text, no '{'.
                extra = ""
                if cont_comment:
                    extra = "  " + cont_comment
                out.append(f"{ws}{close}{body}{extra}")
                i = cont_i + 1
                qstate = _advance_quote_state(raw_lines[cont_i], None)
                continue
            extra = ""
            if comment:
                extra = "  " + comment
            out.append(f"{ws}{close}{code}{extra}")
            delta = _bracket_delta(code)
            if delta > 0:
                header_depth = delta
                header_indent = width
            i += 1
            qstate = line_q
            continue

        # One-liner suite: if cond: stmt. Use depth-0 ':' so slices like
        # line[-1:] / data[8:12] are not mistaken for the suite colon (and so
        # paren-continued headers with slices fall through to header_depth).
        colon = _suite_colon_index(code)
        if first in SUITE_START and colon != -1 and colon < len(code) - 1 and not code.endswith(":"):
            head = code[:colon].rstrip()
            tail = code[colon + 1 :].strip()
            extra = ""
            if comment:
                extra = "  " + comment
            out.append(f"{ws}{head} {{ {tail} }}{extra}")
            i += 1
            qstate = line_q
            continue

        # Backslash-continued suite header: if a and \<nl> b:  →  if a and b {
        if first in SUITE_START and _endswith_cont(code) and not code.endswith(":"):
            parts = [code]
            cont_i = i
            cont_comment = comment
            while _endswith_cont(parts[-1]) and cont_i + 1 < n:
                cont_i += 1
                nline = raw_lines[cont_i]
                nws = _leading_ws(nline)
                ncode, ncomment = _code_part(nline[len(nws) :])
                parts.append(ncode)
                if ncomment:
                    cont_comment = ncomment
            body = _join_cont_codes(parts)
            if body.endswith(":"):
                body = body[:-1].rstrip()
                extra = ""
                if cont_comment:
                    extra = "  " + cont_comment
                out.append(f"{ws}{body} {{{extra}")
                i = cont_i + 1
                j = i
                while j < n and is_blank_or_comment(raw_lines[j]):
                    j += 1
                if j < n:
                    nxt_w = _indent_width(_leading_ws(raw_lines[j]))
                    if nxt_w > width:
                        stack.append(nxt_w)
                    elif nxt_w == width:
                        out.append(f"{ws}}}")
                else:
                    out.append(f"{ws}}}")
                qstate = _advance_quote_state(raw_lines[cont_i], None)
                continue
            # No colon yet (unusual) — fall through with joined text as opaque lines
            for k in range(i, cont_i + 1):
                out.append(raw_lines[k])
            i = cont_i + 1
            qstate = _advance_quote_state(raw_lines[cont_i], None)
            continue

        if code.endswith(":") and first in SUITE_START:
            body = code[:-1].rstrip()
            extra = ""
            if comment:
                extra = "  " + comment
            out.append(f"{ws}{body} {{{extra}")
            i += 1
            j = i
            while j < n and is_blank_or_comment(raw_lines[j]):
                j += 1
            if j < n:
                nxt_w = _indent_width(_leading_ws(raw_lines[j]))
                if nxt_w > width:
                    stack.append(nxt_w)
                elif nxt_w == width:
                    # one-liner already consumed? treat as empty block
                    out.append(f"{ws}}}")
            else:
                out.append(f"{ws}}}")
            qstate = line_q
            continue

        # Multiline def/class/(if) header: track brackets; closing '):' → ') {'
        if header_depth > 0:
            delta = _bracket_delta(code)
            header_depth += delta
            if header_depth <= 0 and code.rstrip().endswith(":"):
                # signature finished: width=None):  →  width=None) {
                body = code[:-1].rstrip()
                extra = ""
                if comment:
                    extra = "  " + comment
                out.append(f"{ws}{body} {{{extra}")
                header_depth = 0
                i += 1
                j = i
                while j < n and is_blank_or_comment(raw_lines[j]):
                    j += 1
                if j < n:
                    nxt_w = _indent_width(_leading_ws(raw_lines[j]))
                    if nxt_w > header_indent:
                        stack.append(nxt_w)
                    elif nxt_w == header_indent:
                        out.append(f"{' ' * header_indent}}}")
                else:
                    out.append(f"{' ' * header_indent}}}")
                qstate = line_q
                continue
            out.append(line)
            qstate = line_q
            i += 1
            continue

        # Suite header that opens brackets without ending ':' on this line
        if first in SUITE_START and not code.endswith(":"):
            delta = _bracket_delta(code)
            if delta > 0:
                out.append(line)
                header_depth = delta
                header_indent = width
                qstate = line_q
                i += 1
                continue

        out.append(line)
        qstate = line_q
        i += 1

    # drop trailing dummy empties from flush
    while out and out[-1] == "":
        out.pop()
    text = "\n".join(out)
    if text and not text.endswith("\n"):
        text += "\n"
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("input", nargs="?", help="Python source file")
    ap.add_argument("output", nargs="?", help="AIMacro .aim path (default stdout)")
    ap.add_argument("--stdin", action="store_true", help="Read source from stdin")
    args = ap.parse_args()

    if args.stdin or not args.input:
        src = sys.stdin.read()
    else:
        with open(args.input, encoding="utf-8") as f:
            src = f.read()

    aim = convert(desugar_for_unpack(desugar_tuple_unpack(desugar_from_import_as(desugar_yield(desugar_nameerror_probe(desugar_starargs_annotations(desugar_pep695_type_params(desugar_match(src)))))))))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(aim)
    else:
        sys.stdout.write(aim)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
