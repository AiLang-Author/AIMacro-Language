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
_MATCH_RE = re.compile(r"^(\s*)match\s+(.+?)\s*:\s*$")


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
            cm = _CASE_RE.match(raw.rstrip("\n"))
            if not cm:
                ws = raw[: len(raw) - len(raw.lstrip())]
                if len(ws.expandtabs(4)) <= ind_w:
                    break
                out.append(raw)
                i += 1
                continue
            c_indent, pattern, trailing = cm.group(1), cm.group(2).strip(), cm.group(3)
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
                    r"^([A-Za-z_][A-Za-z0-9_]*)\(([A-Za-z_][A-Za-z0-9_]*)\)$",
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
                    cond = f"({tmp}) == ({pat})"
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
                return []  # unsupported
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
        return f"{indent}{name} = None\n{m.group(0)}"
    return _NAMEERROR_PROBE_RE.sub(repl, src)

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
        elif rest == "" or rest.startswith("#"):
            out.append(f"{indent}_ = None  # yield stub\n")
            i += 1
            continue
        else:
            # Do not rstrip(",") here: a continued call
            #   yield TokenInfo(STRING, a[:end],
            #          start, (n, end), line)
            # would lose the comma after a[:end] and parse as IDENT after RPAREN.
            expr = rest
        # Accumulate until paren/bracket balance non-negative and closed when opened
        buf = expr
        def _bal(s: str) -> int:
            depth = 0
            in_s = None
            for ch in s:
                if in_s:
                    if ch == in_s:
                        in_s = None
                    continue
                if ch in "\"\'":
                    in_s = ch
                    continue
                if ch in "([{":
                    depth += 1
                elif ch in ")]}":
                    depth -= 1
            return depth
        while _bal(buf) > 0 and i + 1 < len(lines):
            i += 1
            buf += " " + lines[i].strip()
        # Drop trailing comment on last physical line piece
        if "#" in buf:
            # keep simple: strip line comments only when not inside strings — best-effort
            pass
        out.append(f"{indent}_ = ({buf})  # yield stub\n")
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
    """Strip type annotations on *args / **kwargs in def signatures only."""
    lines = src.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        raw = line.rstrip("\n")
        stripped = raw.lstrip()
        if stripped.startswith("def ") and "*" in raw:
            raw2 = _STARARGS_ANN_RE.sub(r"\1\2", raw)
            nl = "\n" if line.endswith("\n") else ""
            out.append(raw2 + nl)
        else:
            out.append(line)
    return "".join(out)


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
                        cell_counter[0] += 1
                        cid = cell_counter[0]
                        need_dict[0] = True
                        mapping = {v: f"{cid}_{v}" for v in sorted(used)}
                        for v, key in mapping.items():
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



def convert(src: str) -> str:
    # Empty / whitespace-only modules (e.g. empty __init__.py): aimacro.x
    # rejects zero-byte input. Emit a bare `pass` so transpile succeeds.
    if not src or not src.strip():
        return "pass\n"
    # match/case already desugared if called via main;
    # accept raw match too when convert() used alone
    if re.search(r"(?m)^\s*match\s+.+:\s*$", src):
        src = desugar_match(src)
    src = desugar_pep695_type_params(src)
    src = desugar_starargs_annotations(src)
    src = desugar_nameerror_probe(src)
    src = desugar_yield(src)
    src = desugar_from_import_as(src)
    src = desugar_tuple_unpack(src)
    src = desugar_for_unpack(src)
    src = desugar_nested_class_cells(src)
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
        first = code.split(None, 1)[0] if code else ""
        first = first.rstrip(":")
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
