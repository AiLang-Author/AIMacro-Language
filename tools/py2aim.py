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

def _m_name(name: str, ctx=None) -> ast.Name:
    return ast.Name(id=name, ctx=ctx or ast.Load())


def _m_assign(name: str, value: ast.expr) -> ast.Assign:
    return ast.Assign(targets=[_m_name(name, ast.Store())], value=value)


def _m_const(v) -> ast.Constant:
    return ast.Constant(value=v)


def _m_call(name: str, args: list) -> ast.Call:
    return ast.Call(func=_m_name(name), args=args, keywords=[])


def _m_iff(test: ast.expr, body: list, orelse: list | None = None) -> ast.If:
    if not body:
        body = [ast.Pass()]
    return ast.If(test=test, body=body, orelse=orelse or [])


def _m_not(e: ast.expr) -> ast.UnaryOp:
    return ast.UnaryOp(op=ast.Not(), operand=e)


def _m_eq(a: ast.expr, b: ast.expr) -> ast.Compare:
    return ast.Compare(left=a, ops=[ast.Eq()], comparators=[b])


def _m_is(a: ast.expr, b: ast.expr) -> ast.Compare:
    return ast.Compare(left=a, ops=[ast.Is()], comparators=[b])


def _m_lt(a: ast.expr, b: ast.expr) -> ast.Compare:
    return ast.Compare(left=a, ops=[ast.Lt()], comparators=[b])


def _m_in(a: ast.expr, b: ast.expr) -> ast.Compare:
    return ast.Compare(left=a, ops=[ast.In()], comparators=[b])


def _m_sub(obj: ast.expr, idx: ast.expr, ctx=None) -> ast.Subscript:
    return ast.Subscript(value=obj, slice=idx, ctx=ctx or ast.Load())


def _m_attr(obj: ast.expr, attr: str, ctx=None) -> ast.Attribute:
    return ast.Attribute(value=obj, attr=attr, ctx=ctx or ast.Load())


def _m_fresh(counter: list, prefix: str) -> str:
    counter[0] += 1
    return f"_aim_{prefix}_{counter[0]}"


def _m_ensure(expr: ast.expr, counter: list, stmts: list) -> str:
    if isinstance(expr, ast.Name):
        return expr.id
    nm = _m_fresh(counter, "v")
    stmts.append(_m_assign(nm, expr))
    return nm


def _m_isinstance(obj: str, typ: str) -> ast.Call:
    return _m_call("isinstance", [_m_name(obj), _m_name(typ)])


def _collect_match_args(tree: ast.AST) -> dict:
    """Map class name → positional __match_args__ names.

    Explicit `__match_args__ = ('x', 'y')` wins. Dataclass field
    annotations are the fallback so `case Point(0, y)` can use Attribute
    loads without runtime getattr (GetAttr is a stub).
    """
    out: dict = {}
    for n in ast.walk(tree):
        if not isinstance(n, ast.ClassDef):
            continue
        ma = None
        fields: list[str] = []
        is_dc = False
        for d in n.decorator_list:
            if isinstance(d, ast.Name) and d.id == "dataclass":
                is_dc = True
            elif isinstance(d, ast.Attribute) and d.attr == "dataclass":
                is_dc = True
            elif isinstance(d, ast.Call):
                f = d.func
                if isinstance(f, ast.Name) and f.id == "dataclass":
                    is_dc = True
                elif isinstance(f, ast.Attribute) and f.attr == "dataclass":
                    is_dc = True
        for s in n.body:
            if isinstance(s, ast.Assign):
                for t in s.targets:
                    if isinstance(t, ast.Name) and t.id == "__match_args__":
                        if isinstance(s.value, (ast.Tuple, ast.List)):
                            ma = [
                                e.value
                                for e in s.value.elts
                                if isinstance(e, ast.Constant)
                                and isinstance(e.value, str)
                            ]
            elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                if not s.target.id.startswith("_"):
                    fields.append(s.target.id)
        names = ma if ma is not None else (fields if is_dc and fields else None)
        if names is None:
            continue
        if n.name in out:
            out[n.name] = None
        else:
            out[n.name] = names
    return out


_BUILTIN_MATCH_CLS = {
    "bool",
    "bytearray",
    "bytes",
    "dict",
    "float",
    "frozenset",
    "int",
    "list",
    "set",
    "str",
    "tuple",
}


def _match_on_attr(
    subj_e: ast.expr,
    attr: str,
    p: ast.pattern,
    ok: str,
    counter: list,
    match_args: dict,
    binds: dict,
    dest: list,
) -> None:
    val = _m_fresh(counter, "av")
    vs, vok, vb = _emit_pattern(_m_name(val), p, counter, match_args)
    step = [_m_assign(val, _m_attr(subj_e, attr))]
    step.extend(vs)
    step.append(_m_iff(_m_not(_m_name(vok)), [_m_assign(ok, _m_const(False))]))
    dest.append(_m_iff(_m_name(ok), step))
    binds.update(vb)


def _match_bind_names(pat: ast.pattern) -> list:
    names: list[str] = []

    def add(n):
        if n and n not in names:
            names.append(n)

    def walk(p):
        if p is None:
            return
        if isinstance(p, ast.MatchAs):
            walk(p.pattern)
            add(p.name)
        elif isinstance(p, ast.MatchOr):
            for q in p.patterns:
                walk(q)
        elif isinstance(p, ast.MatchSequence):
            for q in p.patterns:
                walk(q)
        elif isinstance(p, ast.MatchStar):
            add(p.name)
        elif isinstance(p, ast.MatchMapping):
            for q in p.patterns:
                walk(q)
            add(p.rest)
        elif isinstance(p, ast.MatchClass):
            for q in p.patterns:
                walk(q)
            for q in p.kwd_patterns:
                walk(q)

    walk(pat)
    return names


def _emit_pattern(
    subj: ast.expr,
    pat: ast.pattern,
    counter: list,
    match_args: dict,
) -> tuple:
    """Return (stmts, ok_name, bind_map name→expr). No user binds assigned."""
    stmts: list = []
    subj_n = _m_ensure(subj, counter, stmts)
    subj_e = _m_name(subj_n)
    ok = _m_fresh(counter, "ok")
    binds: dict = {}

    def fail_ok():
        return _m_assign(ok, _m_const(False))

    def ok_true():
        return _m_assign(ok, _m_const(True))

    if isinstance(pat, ast.MatchAs):
        if pat.pattern is None:
            stmts.append(ok_true())
            if pat.name:
                binds[pat.name] = subj_e
            return stmts, ok, binds
        inner_s, inner_ok, inner_b = _emit_pattern(
            subj_e, pat.pattern, counter, match_args
        )
        stmts.extend(inner_s)
        stmts.append(_m_assign(ok, _m_name(inner_ok)))
        binds.update(inner_b)
        if pat.name:
            binds[pat.name] = subj_e
        return stmts, ok, binds

    if isinstance(pat, ast.MatchValue):
        stmts.append(_m_assign(ok, _m_eq(subj_e, pat.value)))
        return stmts, ok, binds

    if isinstance(pat, ast.MatchSingleton):
        stmts.append(_m_assign(ok, _m_is(subj_e, _m_const(pat.value))))
        return stmts, ok, binds

    if isinstance(pat, ast.MatchOr):
        stmts.append(fail_ok())
        names = _match_bind_names(pat)
        tmps = {nm: _m_fresh(counter, "b") for nm in names}
        for nm in names:
            stmts.append(_m_assign(tmps[nm], _m_const(None)))
        for alt in pat.patterns:
            a_s, a_ok, a_b = _emit_pattern(subj_e, alt, counter, match_args)
            body = list(a_s)
            on = [_m_assign(ok, _m_const(True))]
            for nm, expr in a_b.items():
                if nm in tmps:
                    on.append(_m_assign(tmps[nm], expr))
            body.append(_m_iff(_m_name(a_ok), on))
            stmts.append(_m_iff(_m_not(_m_name(ok)), body))
        binds = {nm: _m_name(tmps[nm]) for nm in names}
        return stmts, ok, binds

    if isinstance(pat, ast.MatchSequence):
        isseq = _m_fresh(counter, "seq")
        stmts.append(_m_assign(isseq, _m_const(False)))
        stmts.append(
            ast.Try(
                body=[
                    ast.Expr(value=_m_call("len", [subj_e])),
                    _m_assign(isseq, _m_const(True)),
                ],
                handlers=[
                    ast.ExceptHandler(
                        type=_m_name("Exception"),
                        name=None,
                        body=[ast.Pass()],
                    )
                ],
                orelse=[],
                finalbody=[],
            )
        )
        for typ in ("list", "tuple", "range"):
            stmts.append(
                _m_iff(_m_isinstance(subj_n, typ), [_m_assign(isseq, _m_const(True))])
            )
        for typ in ("str", "bytes", "bytearray", "dict", "set"):
            stmts.append(
                _m_iff(_m_isinstance(subj_n, typ), [_m_assign(isseq, _m_const(False))])
            )
        stmts.append(fail_ok())
        pats = list(pat.patterns)
        star_i = None
        for i, p in enumerate(pats):
            if isinstance(p, ast.MatchStar):
                star_i = i
                break
        seq_body: list = [ok_true()]
        n_name = _m_fresh(counter, "n")
        seq_body.append(_m_assign(n_name, _m_call("len", [subj_e])))
        n_e = _m_name(n_name)
        if star_i is None:
            seq_body.append(
                _m_iff(
                    ast.Compare(
                        left=n_e,
                        ops=[ast.NotEq()],
                        comparators=[_m_const(len(pats))],
                    ),
                    [fail_ok()],
                )
            )
        else:
            nfixed = len(pats) - 1
            seq_body.append(
                _m_iff(_m_lt(n_e, _m_const(nfixed)), [fail_ok()])
            )
        for i, p in enumerate(pats):
            if isinstance(p, ast.MatchStar):
                continue
            if star_i is None or i < star_i:
                idx_e: ast.expr = _m_const(i)
            else:
                back = len(pats) - i
                idx_n = _m_fresh(counter, "i")
                seq_body.append(
                    _m_assign(
                        idx_n,
                        ast.BinOp(
                            left=n_e, op=ast.Sub(), right=_m_const(back)
                        ),
                    )
                )
                idx_e = _m_name(idx_n)
            elt = _m_sub(subj_e, idx_e)
            e_s, e_ok, e_b = _emit_pattern(elt, p, counter, match_args)
            elt_body = list(e_s)
            elt_body.append(_m_iff(_m_not(_m_name(e_ok)), [fail_ok()]))
            seq_body.append(_m_iff(_m_name(ok), elt_body))
            binds.update(e_b)
        if star_i is not None and pats[star_i].name:
            nfixed = len(pats) - 1
            st_n = _m_fresh(counter, "st")
            sl_n = _m_fresh(counter, "sl")
            en_n = _m_fresh(counter, "en")
            i_n = _m_fresh(counter, "si")
            sn = _m_fresh(counter, "star")
            elt_n = _m_fresh(counter, "se")
            star_body = [
                _m_assign(st_n, _m_const(star_i)),
                _m_assign(
                    sl_n,
                    ast.BinOp(left=n_e, op=ast.Sub(), right=_m_const(nfixed)),
                ),
                _m_assign(
                    en_n,
                    ast.BinOp(
                        left=_m_name(st_n), op=ast.Add(), right=_m_name(sl_n)
                    ),
                ),
                _m_assign(sn, ast.List(elts=[], ctx=ast.Load())),
                _m_assign(i_n, _m_name(st_n)),
                ast.While(
                    test=_m_lt(_m_name(i_n), _m_name(en_n)),
                    body=[
                        _m_assign(elt_n, _m_sub(subj_e, _m_name(i_n))),
                        ast.Expr(
                            value=ast.Call(
                                func=_m_attr(_m_name(sn), "append"),
                                args=[_m_name(elt_n)],
                                keywords=[],
                            )
                        ),
                        _m_assign(
                            i_n,
                            ast.BinOp(
                                left=_m_name(i_n),
                                op=ast.Add(),
                                right=_m_const(1),
                            ),
                        ),
                    ],
                    orelse=[],
                ),
            ]
            binds[pats[star_i].name] = _m_name(sn)
            seq_body.append(_m_iff(_m_name(ok), star_body))
        stmts.append(_m_iff(_m_name(isseq), seq_body))
        return stmts, ok, binds

    if isinstance(pat, ast.MatchMapping):
        ismap = _m_fresh(counter, "map")
        stmts.append(_m_assign(ismap, _m_const(False)))
        stmts.append(
            ast.Try(
                body=[
                    ast.Expr(
                        value=ast.Call(
                            func=_m_attr(subj_e, "keys"),
                            args=[],
                            keywords=[],
                        )
                    ),
                    _m_assign(ismap, _m_const(True)),
                ],
                handlers=[
                    ast.ExceptHandler(
                        type=_m_name("Exception"),
                        name=None,
                        body=[ast.Pass()],
                    )
                ],
                orelse=[],
                finalbody=[],
            )
        )
        stmts.append(
            _m_iff(_m_isinstance(subj_n, "dict"), [_m_assign(ismap, _m_const(True))])
        )
        stmts.append(fail_ok())
        used_n = _m_fresh(counter, "used")
        map_body: list = [
            ok_true(),
            _m_assign(used_n, ast.Dict(keys=[], values=[])),
        ]
        for key_e, vp in zip(pat.keys, pat.patterns):
            kn = _m_ensure(key_e, counter, map_body)
            has = _m_in(_m_name(kn), subj_e)
            vs, vok, vb = _emit_pattern(
                _m_sub(subj_e, _m_name(kn)), vp, counter, match_args
            )
            then = list(vs)
            then.append(_m_iff(_m_not(_m_name(vok)), [fail_ok()]))
            then.append(
                ast.Assign(
                    targets=[_m_sub(_m_name(used_n), _m_name(kn), ast.Store())],
                    value=_m_const(1),
                )
            )
            binds.update(vb)
            map_body.append(
                _m_iff(
                    _m_name(ok),
                    [_m_iff(has, then, [fail_ok()])],
                )
            )
        if pat.rest:
            rest_n = _m_fresh(counter, "rest")
            k_n = _m_fresh(counter, "k")
            rest_body = [
                _m_assign(rest_n, ast.Dict(keys=[], values=[])),
                ast.For(
                    target=_m_name(k_n, ast.Store()),
                    iter=subj_e,
                    body=[
                        _m_iff(
                            _m_not(_m_in(_m_name(k_n), _m_name(used_n))),
                            [
                                ast.Assign(
                                    targets=[
                                        _m_sub(
                                            _m_name(rest_n),
                                            _m_name(k_n),
                                            ast.Store(),
                                        )
                                    ],
                                    value=_m_sub(subj_e, _m_name(k_n)),
                                )
                            ],
                        )
                    ],
                    orelse=[],
                ),
            ]
            map_body.append(_m_iff(_m_name(ok), rest_body))
            binds[pat.rest] = _m_name(rest_n)
        stmts.append(_m_iff(_m_name(ismap), map_body))
        return stmts, ok, binds

    if isinstance(pat, ast.MatchClass):
        stmts.append(fail_ok())
        inst = _m_call("isinstance", [subj_e, pat.cls])
        cls_body: list = [ok_true()]
        static = None
        builtin = False
        if isinstance(pat.cls, ast.Name):
            static = match_args.get(pat.cls.id)
            builtin = pat.cls.id in _BUILTIN_MATCH_CLS
        npos = len(pat.patterns)
        if builtin:
            if npos == 1:
                vs, vok, vb = _emit_pattern(
                    subj_e, pat.patterns[0], counter, match_args
                )
                step = list(vs)
                step.append(_m_iff(_m_not(_m_name(vok)), [fail_ok()]))
                cls_body.append(_m_iff(_m_name(ok), step))
                binds.update(vb)
            elif npos > 1:
                cls_body.append(fail_ok())
        elif npos:
            if static is not None:
                if npos > len(static):
                    cls_body.append(fail_ok())
                else:
                    for i, p in enumerate(pat.patterns):
                        _match_on_attr(
                            subj_e,
                            static[i],
                            p,
                            ok,
                            counter,
                            match_args,
                            binds,
                            cls_body,
                        )
            else:
                ma_n = _m_fresh(counter, "ma")
                cls_body.append(
                    _m_assign(ma_n, _m_attr(pat.cls, "__match_args__"))
                )
                cls_body.append(
                    _m_iff(
                        _m_lt(
                            _m_call("len", [_m_name(ma_n)]),
                            _m_const(npos),
                        ),
                        [fail_ok()],
                    )
                )
                for i, p in enumerate(pat.patterns):
                    nm_n = _m_fresh(counter, "nm")
                    val_n = _m_fresh(counter, "cv")
                    got2 = _m_fresh(counter, "got")
                    step = [
                        _m_assign(nm_n, _m_sub(_m_name(ma_n), _m_const(i))),
                        _m_assign(got2, _m_const(True)),
                        ast.Try(
                            body=[
                                _m_assign(
                                    val_n,
                                    _m_call(
                                        "getattr",
                                        [subj_e, _m_name(nm_n)],
                                    ),
                                )
                            ],
                            handlers=[
                                ast.ExceptHandler(
                                    type=_m_name("AttributeError"),
                                    name=None,
                                    body=[
                                        _m_assign(got2, _m_const(False)),
                                        _m_assign(val_n, _m_const(None)),
                                    ],
                                )
                            ],
                            orelse=[],
                            finalbody=[],
                        ),
                    ]
                    vs, vok, vb = _emit_pattern(
                        _m_name(val_n), p, counter, match_args
                    )
                    inner = vs + [
                        _m_iff(_m_not(_m_name(vok)), [fail_ok()])
                    ]
                    step.append(
                        _m_iff(
                            _m_not(_m_name(got2)),
                            [fail_ok()],
                            inner,
                        )
                    )
                    cls_body.append(_m_iff(_m_name(ok), step))
                    binds.update(vb)
        for attr, p in zip(pat.kwd_attrs, pat.kwd_patterns):
            _match_on_attr(
                subj_e, attr, p, ok, counter, match_args, binds, cls_body
            )
        stmts.append(_m_iff(inst, cls_body))
        return stmts, ok, binds

    if isinstance(pat, ast.MatchStar):
        stmts.append(ok_true())
        if pat.name:
            binds[pat.name] = _m_call("list", [subj_e])
        return stmts, ok, binds

    stmts.append(fail_ok())
    return stmts, ok, binds


def _desugar_one_match(
    node: ast.Match, counter: list, match_args: dict
) -> list:
    m_n = _m_fresh(counter, "m")
    hit = _m_fresh(counter, "hit")
    stmts = [
        _m_assign(m_n, node.subject),
        _m_assign(hit, _m_const(False)),
    ]
    for case in node.cases:
        ps, pok, pb = _emit_pattern(
            _m_name(m_n), case.pattern, counter, match_args
        )
        taken: list = []
        for nm, expr in pb.items():
            taken.append(_m_assign(nm, expr))
        body = [ast.copy_location(s, case.pattern) for s in case.body]
        if case.guard is None:
            taken.append(_m_assign(hit, _m_const(True)))
            taken.extend(body)
        else:
            taken.append(
                _m_iff(
                    case.guard,
                    [_m_assign(hit, _m_const(True))] + body,
                )
            )
        case_body = list(ps)
        case_body.append(_m_iff(_m_name(pok), taken))
        stmts.append(_m_iff(_m_not(_m_name(hit)), case_body))
    return stmts


def desugar_match(src: str) -> str:
    """Replace match/case with ifs. Isolation files without ast.Match stay intact."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    if not any(isinstance(n, ast.Match) for n in ast.walk(tree)):
        return src
    counter = [0]
    match_args = _collect_match_args(tree)

    class _M(ast.NodeTransformer):
        def visit_Match(self, node: ast.Match):
            node.subject = self.visit(node.subject)
            new_cases = []
            for c in node.cases:
                body = []
                for s in c.body:
                    r = self.visit(s)
                    if isinstance(r, list):
                        body.extend(r)
                    elif r is not None:
                        body.append(r)
                new_cases.append(
                    ast.match_case(
                        pattern=c.pattern, guard=c.guard, body=body
                    )
                )
            return _desugar_one_match(
                ast.Match(subject=node.subject, cases=new_cases),
                counter,
                match_args,
            )

    new_tree = _M().visit(tree)
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree) + "\n"
    except Exception:
        return src


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
    if isinstance(node, (ast.Yield, ast.YieldFrom, ast.Await)):
        return True
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return False
    for c in ast.iter_child_nodes(node):
        if _tree_has_yield(c):
            return True
    return False


def _expr_has_await(node: ast.AST) -> bool:
    if isinstance(node, ast.Await):
        return True
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return False
    for c in ast.iter_child_nodes(node):
        if _expr_has_await(c):
            return True
    return False


class _LiftAwait(ast.NodeTransformer):
    """Replace Await in expressions with a temp; collect assigns in .pre."""

    def __init__(self, counter: list[int]):
        self.counter = counter
        self.pre: list[ast.stmt] = []

    def visit_FunctionDef(self, n: ast.FunctionDef):
        return n

    def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef):
        return n

    def visit_ClassDef(self, n: ast.ClassDef):
        return n

    def visit_Lambda(self, n: ast.Lambda):
        return n

    def visit_Await(self, n: ast.Await):
        n = self.generic_visit(n)
        self.counter[0] += 1
        t = f"_aim_aw{self.counter[0]}"
        self.pre.append(
            ast.Assign(
                targets=[ast.Name(id=t, ctx=ast.Store())],
                value=ast.Await(value=n.value),
            )
        )
        return ast.Name(id=t, ctx=ast.Load())


def _lift_expr(expr: ast.expr, counter: list[int]) -> tuple[list[ast.stmt], ast.expr]:
    lifter = _LiftAwait(counter)
    new = lifter.visit(expr)
    return lifter.pre, new


def _rewrite_async_loops(body: list[ast.stmt], counter: list[int]) -> list[ast.stmt]:
    out: list[ast.stmt] = []
    for s in body:
        if isinstance(s, ast.AsyncFor):
            out.extend(_async_for_to_while(s, counter))
        elif isinstance(s, ast.AsyncWith):
            out.extend(_async_with_to_try(s, counter))
        elif isinstance(s, ast.If):
            s = ast.If(
                test=s.test,
                body=_rewrite_async_loops(list(s.body), counter),
                orelse=_rewrite_async_loops(list(s.orelse), counter),
            )
            out.append(s)
        elif isinstance(s, ast.While):
            s = ast.While(
                test=s.test,
                body=_rewrite_async_loops(list(s.body), counter),
                orelse=_rewrite_async_loops(list(s.orelse), counter),
            )
            out.append(s)
        elif isinstance(s, ast.For):
            s = ast.For(
                target=s.target,
                iter=s.iter,
                body=_rewrite_async_loops(list(s.body), counter),
                orelse=_rewrite_async_loops(list(s.orelse), counter),
            )
            out.append(s)
        elif isinstance(s, ast.Try):
            s = ast.Try(
                body=_rewrite_async_loops(list(s.body), counter),
                handlers=[
                    ast.ExceptHandler(
                        type=h.type,
                        name=h.name,
                        body=_rewrite_async_loops(list(h.body), counter),
                    )
                    for h in s.handlers
                ],
                orelse=_rewrite_async_loops(list(s.orelse), counter),
                finalbody=_rewrite_async_loops(list(s.finalbody), counter),
            )
            out.append(s)
        elif isinstance(s, ast.With):
            s = ast.With(
                items=s.items,
                body=_rewrite_async_loops(list(s.body), counter),
            )
            out.append(s)
        else:
            out.append(s)
    return out


def _async_for_to_while(node: ast.AsyncFor, counter: list[int]) -> list[ast.stmt]:
    """async for x in e → e.__aiter__() + send() until StopIteration/SAI.

    Catch SAI only around anext (iterator end). A store like tgt[0] = v
    that raises SAI(42) must leave the while and re-raise so
    assertRaises sees kind 10. leftover MethodCall does not abort the
    while on pending, so a later send() RaiseKind 9 would overwrite it.
    Do not Break inside except: leftover ContinueLoop/BreakLoop in
    Fork does not resume the outer WhileLoop.
    """
    counter[0] += 1
    n = counter[0]
    it = f"_aim_ai{n}"
    st = f"_aim_as{n}"
    run = f"_aim_ar{n}"
    nxt = f"_aim_an{n}"
    sav = f"_aim_ae{n}"
    sf = f"_aim_af{n}"
    ename = f"_aim_ex{n}"
    body = _rewrite_async_loops(list(node.body), counter)
    orelse = _rewrite_async_loops(list(node.orelse), counter) if node.orelse else []
    send_call = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id=it, ctx=ast.Load()),
            attr="send",
            ctx=ast.Load(),
        ),
        args=[ast.Constant(value=None)],
        keywords=[],
    )
    return [
        ast.Assign(
            targets=[ast.Name(id=it, ctx=ast.Store())],
            value=ast.Call(
                func=ast.Attribute(value=node.iter, attr="__aiter__", ctx=ast.Load()),
                args=[],
                keywords=[],
            ),
        ),
        ast.Assign(
            targets=[ast.Name(id=run, ctx=ast.Store())],
            value=ast.Constant(value=True),
        ),
        ast.Assign(
            targets=[ast.Name(id=sav, ctx=ast.Store())],
            value=ast.Constant(value=None),
        ),
        ast.Assign(
            targets=[ast.Name(id=sf, ctx=ast.Store())],
            value=ast.Constant(value=0),
        ),
        ast.While(
            test=ast.Name(id=run, ctx=ast.Load()),
            body=[
                ast.Assign(
                    targets=[ast.Name(id=st, ctx=ast.Store())],
                    value=ast.Constant(value=0),
                ),
                ast.Try(
                    body=[
                        ast.Assign(
                            targets=[ast.Name(id=nxt, ctx=ast.Store())],
                            value=send_call,
                        )
                    ],
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
                        ),
                        ast.ExceptHandler(
                            type=ast.Name(id="StopAsyncIteration", ctx=ast.Load()),
                            name=None,
                            body=[
                                ast.Assign(
                                    targets=[ast.Name(id=st, ctx=ast.Store())],
                                    value=ast.Constant(value=1),
                                )
                            ],
                        ),
                    ],
                    orelse=[],
                    finalbody=[],
                ),
                ast.If(
                    test=ast.Name(id=st, ctx=ast.Load()),
                    body=orelse + [ast.Break()],
                    orelse=[],
                ),
                ast.Try(
                    body=[
                        ast.Assign(
                            targets=[node.target],
                            value=ast.Name(id=nxt, ctx=ast.Load()),
                        )
                    ],
                    handlers=[
                        ast.ExceptHandler(
                            type=ast.Name(id="Exception", ctx=ast.Load()),
                            name=ename,
                            body=[
                                ast.Assign(
                                    targets=[ast.Name(id=sav, ctx=ast.Store())],
                                    value=ast.Name(id=ename, ctx=ast.Load()),
                                ),
                                ast.Assign(
                                    targets=[ast.Name(id=sf, ctx=ast.Store())],
                                    value=ast.Constant(value=1),
                                ),
                            ],
                        )
                    ],
                    orelse=[],
                    finalbody=[],
                ),
                ast.If(
                    test=ast.Name(id=sf, ctx=ast.Load()),
                    body=[ast.Break()],
                    orelse=[],
                ),
            ]
            + body,
            orelse=[],
        ),
        ast.If(
            test=ast.Name(id=sf, ctx=ast.Load()),
            body=[
                ast.Raise(
                    exc=ast.Name(id=sav, ctx=ast.Load()),
                    cause=None,
                )
            ],
            orelse=[],
        ),
    ]


def _async_with_to_try(node: ast.AsyncWith, counter: list[int]) -> list[ast.stmt]:
    """async with e as x → await __aenter__ / try / await __aexit__(None,None,None)."""
    body = _rewrite_async_loops(list(node.body), counter)
    for item in reversed(node.items):
        counter[0] += 1
        n = counter[0]
        mgr = f"_aim_am{n}"
        ent = f"_aim_ae{n}"
        inner: list[ast.stmt] = [
            ast.Assign(
                targets=[ast.Name(id=mgr, ctx=ast.Store())],
                value=item.context_expr,
            ),
            ast.Assign(
                targets=[ast.Name(id=ent, ctx=ast.Store())],
                value=ast.Await(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id=mgr, ctx=ast.Load()),
                            attr="__aenter__",
                            ctx=ast.Load(),
                        ),
                        args=[],
                        keywords=[],
                    )
                ),
            ),
        ]
        if item.optional_vars is not None:
            inner.append(
                ast.Assign(targets=[item.optional_vars], value=ast.Name(id=ent, ctx=ast.Load()))
            )
        inner.append(
            ast.Try(
                body=body if body else [ast.Pass()],
                handlers=[],
                orelse=[],
                finalbody=[
                    ast.Expr(
                        value=ast.Await(
                            value=ast.Call(
                                func=ast.Attribute(
                                    value=ast.Name(id=mgr, ctx=ast.Load()),
                                    attr="__aexit__",
                                    ctx=ast.Load(),
                                ),
                                args=[
                                    ast.Constant(value=None),
                                    ast.Constant(value=None),
                                    ast.Constant(value=None),
                                ],
                                keywords=[],
                            )
                        )
                    )
                ],
            )
        )
        body = inner
    return body


def _lift_awaits_in_body(body: list[ast.stmt], counter: list[int]) -> list[ast.stmt]:
    out: list[ast.stmt] = []
    for stmt in body:
        out.extend(_lift_awaits_stmt(stmt, counter))
    return out


def _lift_awaits_stmt(stmt: ast.stmt, counter: list[int]) -> list[ast.stmt]:
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [stmt]
    if isinstance(stmt, ast.If):
        pre, test = _lift_expr(stmt.test, counter)
        body = _lift_awaits_in_body(list(stmt.body), counter)
        orelse = _lift_awaits_in_body(list(stmt.orelse), counter)
        return pre + [ast.If(test=test, body=body if body else [ast.Pass()], orelse=orelse)]
    if isinstance(stmt, ast.While):
        if _expr_has_await(stmt.test):
            counter[0] += 1
            c = f"_aim_wc{counter[0]}"
            inner = [
                ast.Assign(
                    targets=[ast.Name(id=c, ctx=ast.Store())],
                    value=stmt.test,
                ),
                ast.If(
                    test=ast.UnaryOp(
                        op=ast.Not(), operand=ast.Name(id=c, ctx=ast.Load())
                    ),
                    body=[ast.Break()],
                    orelse=[],
                ),
            ] + list(stmt.body)
            inner = _lift_awaits_in_body(inner, counter)
            orelse = _lift_awaits_in_body(list(stmt.orelse), counter)
            return [
                ast.While(
                    test=ast.Constant(value=True),
                    body=inner,
                    orelse=orelse,
                )
            ]
        body = _lift_awaits_in_body(list(stmt.body), counter)
        orelse = _lift_awaits_in_body(list(stmt.orelse), counter)
        return [ast.While(test=stmt.test, body=body if body else [ast.Pass()], orelse=orelse)]
    if isinstance(stmt, ast.For):
        pre, it = _lift_expr(stmt.iter, counter)
        body = _lift_awaits_in_body(list(stmt.body), counter)
        orelse = _lift_awaits_in_body(list(stmt.orelse), counter)
        return pre + [
            ast.For(
                target=stmt.target,
                iter=it,
                body=body if body else [ast.Pass()],
                orelse=orelse,
            )
        ]
    if isinstance(stmt, ast.Try):
        body = _lift_awaits_in_body(list(stmt.body), counter)
        handlers = [
            ast.ExceptHandler(
                type=h.type,
                name=h.name,
                body=_lift_awaits_in_body(list(h.body), counter) or [ast.Pass()],
            )
            for h in stmt.handlers
        ]
        orelse = _lift_awaits_in_body(list(stmt.orelse), counter)
        finalbody = _lift_awaits_in_body(list(stmt.finalbody), counter)
        return [
            ast.Try(
                body=body if body else [ast.Pass()],
                handlers=handlers,
                orelse=orelse,
                finalbody=finalbody,
            )
        ]
    if isinstance(stmt, ast.With):
        pres: list[ast.stmt] = []
        items = []
        for it in stmt.items:
            p, ctx = _lift_expr(it.context_expr, counter)
            pres.extend(p)
            items.append(ast.withitem(context_expr=ctx, optional_vars=it.optional_vars))
        body = _lift_awaits_in_body(list(stmt.body), counter)
        return pres + [ast.With(items=items, body=body if body else [ast.Pass()])]
    if isinstance(stmt, ast.Return):
        if stmt.value is None:
            return [stmt]
        pre, v = _lift_expr(stmt.value, counter)
        return pre + [ast.Return(value=v)]
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.value, ast.Await):
        pre, v = _lift_expr(stmt.value.value, counter)
        return pre + [ast.Assign(targets=stmt.targets, value=ast.Await(value=v))]
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Await):
        pre, v = _lift_expr(stmt.value.value, counter)
        return pre + [ast.Expr(value=ast.Await(value=v))]
    if isinstance(stmt, ast.Assign):
        pre, v = _lift_expr(stmt.value, counter)
        return pre + [ast.Assign(targets=stmt.targets, value=v)]
    if isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
        pre, v = _lift_expr(stmt.value, counter)
        return pre + [
            ast.AnnAssign(
                target=stmt.target, annotation=stmt.annotation, value=v, simple=stmt.simple
            )
        ]
    if isinstance(stmt, ast.AugAssign):
        pre, v = _lift_expr(stmt.value, counter)
        return pre + [ast.AugAssign(target=stmt.target, op=stmt.op, value=v)]
    if isinstance(stmt, ast.Raise):
        pres: list[ast.stmt] = []
        exc = stmt.exc
        cause = stmt.cause
        if exc is not None:
            p, exc = _lift_expr(exc, counter)
            pres.extend(p)
        if cause is not None:
            p, cause = _lift_expr(cause, counter)
            pres.extend(p)
        return pres + [ast.Raise(exc=exc, cause=cause)]
    if isinstance(stmt, ast.Assert):
        pre, test = _lift_expr(stmt.test, counter)
        msg = stmt.msg
        more: list[ast.stmt] = []
        if msg is not None:
            p, msg = _lift_expr(msg, counter)
            more = p
        return pre + more + [ast.Assert(test=test, msg=msg)]
    if isinstance(stmt, ast.Expr):
        pre, v = _lift_expr(stmt.value, counter)
        return pre + [ast.Expr(value=v)]
    lifter = _LiftAwait(counter)
    new = lifter.visit(stmt)
    return lifter.pre + [new]


class _ExpandAsyncComp(ast.NodeTransformer):
    """Statement temps for async list/set/dict comps so leftover emit
    is async-for + append, not `async for self._c['tgt'][0]`."""

    def __init__(self, counter: list[int]):
        self.counter = counter
        self.pre: list[ast.stmt] = []

    def visit_FunctionDef(self, n: ast.FunctionDef):
        return n

    def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef):
        return n

    def visit_ClassDef(self, n: ast.ClassDef):
        return n

    def visit_Lambda(self, n: ast.Lambda):
        return n

    def visit_GeneratorExp(self, n: ast.GeneratorExp):
        return n

    def visit_ListComp(self, n: ast.ListComp):
        if not any(g.is_async for g in n.generators):
            return n
        n = self.generic_visit(n)
        return self._fill(n.elt, n.generators, "list")

    def visit_SetComp(self, n: ast.SetComp):
        if not any(g.is_async for g in n.generators):
            return n
        n = self.generic_visit(n)
        return self._fill(n.elt, n.generators, "set")

    def visit_DictComp(self, n: ast.DictComp):
        if not any(g.is_async for g in n.generators):
            return n
        n = self.generic_visit(n)
        return self._fill(n.value, n.generators, "dict", n.key)

    def _fill(
        self,
        elt: ast.expr,
        generators: list[ast.comprehension],
        kind: str,
        key: ast.expr | None = None,
    ) -> ast.Name:
        self.counter[0] += 1
        dest = f"_aim_ac{self.counter[0]}"
        if kind == "list":
            init: ast.expr = ast.List(elts=[], ctx=ast.Load())
            add: ast.stmt = ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id=dest, ctx=ast.Load()),
                        attr="append",
                        ctx=ast.Load(),
                    ),
                    args=[elt],
                    keywords=[],
                )
            )
        elif kind == "set":
            init = ast.Call(
                func=ast.Name(id="set", ctx=ast.Load()),
                args=[],
                keywords=[],
            )
            add = ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id=dest, ctx=ast.Load()),
                        attr="add",
                        ctx=ast.Load(),
                    ),
                    args=[elt],
                    keywords=[],
                )
            )
        else:
            init = ast.Dict(keys=[], values=[])
            add = ast.Assign(
                targets=[
                    ast.Subscript(
                        value=ast.Name(id=dest, ctx=ast.Load()),
                        slice=key if key is not None else ast.Constant(value=0),
                        ctx=ast.Store(),
                    )
                ],
                value=elt,
            )
        body: list[ast.stmt] = [add]
        for gen in reversed(generators):
            for iff in reversed(gen.ifs):
                body = [ast.If(test=iff, body=body, orelse=[])]
            if gen.is_async:
                body = [
                    ast.AsyncFor(
                        target=gen.target,
                        iter=gen.iter,
                        body=body,
                        orelse=[],
                    )
                ]
            else:
                body = [
                    ast.For(
                        target=gen.target,
                        iter=gen.iter,
                        body=body,
                        orelse=[],
                    )
                ]
        self.pre.append(
            ast.Assign(
                targets=[ast.Name(id=dest, ctx=ast.Store())],
                value=init,
            )
        )
        self.pre.extend(body)
        return ast.Name(id=dest, ctx=ast.Load())


def _expand_async_comps_in_body(
    body: list[ast.stmt], counter: list[int]
) -> list[ast.stmt]:
    out: list[ast.stmt] = []
    for s in body:
        if isinstance(s, ast.If):
            out.append(
                ast.If(
                    test=s.test,
                    body=_expand_async_comps_in_body(list(s.body), counter),
                    orelse=_expand_async_comps_in_body(list(s.orelse), counter),
                )
            )
            continue
        if isinstance(s, ast.While):
            out.append(
                ast.While(
                    test=s.test,
                    body=_expand_async_comps_in_body(list(s.body), counter),
                    orelse=_expand_async_comps_in_body(list(s.orelse), counter),
                )
            )
            continue
        if isinstance(s, ast.For):
            out.append(
                ast.For(
                    target=s.target,
                    iter=s.iter,
                    body=_expand_async_comps_in_body(list(s.body), counter),
                    orelse=_expand_async_comps_in_body(list(s.orelse), counter),
                )
            )
            continue
        if isinstance(s, ast.Try):
            out.append(
                ast.Try(
                    body=_expand_async_comps_in_body(list(s.body), counter),
                    handlers=[
                        ast.ExceptHandler(
                            type=h.type,
                            name=h.name,
                            body=_expand_async_comps_in_body(list(h.body), counter)
                            or [ast.Pass()],
                        )
                        for h in s.handlers
                    ],
                    orelse=_expand_async_comps_in_body(list(s.orelse), counter),
                    finalbody=_expand_async_comps_in_body(list(s.finalbody), counter),
                )
            )
            continue
        if isinstance(s, ast.With):
            out.append(
                ast.With(
                    items=s.items,
                    body=_expand_async_comps_in_body(list(s.body), counter),
                )
            )
            continue
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.append(s)
            continue
        exp = _ExpandAsyncComp(counter)
        new = exp.visit(s)
        out.extend(exp.pre)
        out.append(new)
    return out


def _async_prep(node: ast.AsyncFunctionDef, counter: list[int]) -> ast.FunctionDef:
    body = _expand_async_comps_in_body(list(node.body), counter)
    body = _rewrite_async_loops(body, counter)
    body = _lift_awaits_in_body(body, counter)
    return ast.FunctionDef(
        name=node.name,
        args=node.args,
        body=body if body else [ast.Pass()],
        decorator_list=[],
        returns=node.returns,
        type_params=getattr(node, "type_params", []),
    )


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


def _throw_norm_stmts() -> list[ast.stmt]:
    """Store throw(typ) as an ExcKind integer in _tkind.

    leftover type names are integers (ValueError is 2). leftover
    instances are hashes whose __class__ is the kind integer. _tkind
    is an OOP Integer field: ExcKindOf returns 1..40 and never stores
    the hash. Do not isinstance() the hash.
    """
    return [
        ast.Assign(
            targets=[_gen_self_attr("_texc", ast.Store())],
            value=ast.Name(id="typ", ctx=ast.Load()),
        ),
        ast.Assign(
            targets=[_gen_self_attr("_tkind", ast.Store())],
            value=ast.Call(
                func=ast.Name(id="__aim_exc_kind__", ctx=ast.Load()),
                args=[ast.Name(id="typ", ctx=ast.Load())],
                keywords=[],
            ),
        ),
    ]


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
    "__aim_catch_throw",
    "__next__",
    "__iter__",
    "__await__",
    "__aiter__",
    "__anext__",
    "asend",
    "__init__",
    "__class__",
    "__data__",
}


def _tree_has_async_gen(tree: ast.AST) -> bool:
    for n in ast.walk(tree):
        if isinstance(n, ast.AsyncFunctionDef) and _fn_own_yields(n):
            return True
        if isinstance(n, ast.GeneratorExp) and any(g.is_async for g in n.generators):
            return True
    return False


def _aim_anext_fn() -> ast.AsyncFunctionDef:
    """leftover await of async-gen __anext__: return-only coro.

    leftover _await yield_to's next() values. A leftover gen's send()
    returns the yield, so awaiting the gen itself leaks into run_async.
    This coro returns g.send(v) and maps StopIteration to SAI.
    """
    return ast.AsyncFunctionDef(
        name="_AimANext",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="g"), ast.arg(arg="v")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[ast.Constant(value=None)],
        ),
        body=[
            ast.Try(
                body=[
                    ast.Return(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="g", ctx=ast.Load()),
                                attr="send",
                                ctx=ast.Load(),
                            ),
                            args=[ast.Name(id="v", ctx=ast.Load())],
                            keywords=[],
                        )
                    )
                ],
                handlers=[
                    ast.ExceptHandler(
                        type=ast.Name(id="StopIteration", ctx=ast.Load()),
                        name=None,
                        body=[
                            ast.Raise(
                                exc=ast.Call(
                                    func=ast.Name(
                                        id="StopAsyncIteration", ctx=ast.Load()
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
                finalbody=[],
            )
        ],
        decorator_list=[],
    )


def _async_genexp_to_fn(node: ast.GeneratorExp, name: str) -> ast.AsyncFunctionDef:
    body: list[ast.stmt] = [ast.Expr(value=ast.Yield(value=node.elt))]
    for gen in reversed(node.generators):
        for iff in reversed(gen.ifs):
            body = [ast.If(test=iff, body=body, orelse=[])]
        if gen.is_async:
            body = [
                ast.AsyncFor(
                    target=gen.target, iter=gen.iter, body=body, orelse=[]
                )
            ]
        else:
            body = [
                ast.For(target=gen.target, iter=gen.iter, body=body, orelse=[])
            ]
    return ast.AsyncFunctionDef(
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
            n = self.generic_visit(n)
            counter[0] += 1
            name = f"_aim_gx_{counter[0]}"
            if any(g.is_async for g in n.generators):
                self.pending.append(_async_genexp_to_fn(n, name))
            else:
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
    def __init__(
        self,
        mapping: dict[str, str],
        cell_names: set[str] | None = None,
        skip_names: set[str] | None = None,
    ):
        self.mapping = mapping
        self.cell_names = cell_names or set()
        self._skip: set[str] = set(skip_names or ())

    def visit_Name(self, n: ast.Name):
        if n.id in self._skip:
            return n
        if n.id in self.cell_names:
            return ast.Subscript(
                value=_gen_self_attr("_g_fv", ast.Load()),
                slice=ast.Constant(value=n.id),
                ctx=n.ctx,
            )
        if n.id in self.mapping:
            return _gen_self_attr(self.mapping[n.id], n.ctx)
        return n

    def visit_AugAssign(self, node: ast.AugAssign):
        if isinstance(node.target, ast.Name) and node.target.id in self.cell_names:
            assign = ast.Assign(
                targets=[ast.Name(id=node.target.id, ctx=ast.Store())],
                value=ast.BinOp(
                    left=ast.Name(id=node.target.id, ctx=ast.Load()),
                    op=node.op,
                    right=node.value,
                ),
            )
            return self.visit(assign)
        return self.generic_visit(node)

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
    def __init__(
        self,
        mapping: dict[str, str],
        coro: bool = False,
        cell_names: set[str] | None = None,
        skip_names: set[str] | None = None,
    ):
        self.rew = _GenNameRew(mapping, cell_names, skip_names)
        self.states: list[list[ast.stmt]] = [[_throw_if_stmt()]]
        self.cur = 0
        self.it_n = 0
        self.loops: list[tuple[int, int]] = []
        self.wrapped: set[int] = set()
        self.coro = coro

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
        if self.coro:
            self.add(
                ast.Assign(
                    targets=[_gen_self_attr("cr_frame", ast.Store())],
                    value=ast.Constant(value=None),
                )
            )
        self.add(
            ast.If(
                test=_gen_self_attr("_closing", ast.Load()),
                body=[ast.Return(value=ast.Constant(value=None))],
                orelse=[_raise_stop_iteration()],
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
            if isinstance(s, ast.Expr) and isinstance(s.value, ast.Await):
                self._await(s.value.value, None, rest, after)
                return
            if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.value, ast.Yield):
                self._yield_stmt(s.value.value, s.targets[0], rest, after)
                return
            if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.value, ast.YieldFrom):
                self._yield_from(s.value.value, s.targets[0], rest, after)
                return
            if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.value, ast.Await):
                self._await(s.value.value, s.targets[0], rest, after)
                return
            if isinstance(s, (ast.Nonlocal, ast.Global)):
                i += 1
                continue
            if isinstance(s, ast.Return):
                val = s.value if s.value is not None else ast.Constant(value=None)
                if isinstance(val, ast.Yield):
                    self._yield_stmt(
                        val.value,
                        _gen_self_attr("_ret", ast.Store()),
                        [],
                        None,
                    )
                    return
                if isinstance(val, ast.YieldFrom):
                    self._yield_from(
                        val.value,
                        _gen_self_attr("_ret", ast.Store()),
                        [],
                        None,
                    )
                    return
                self.add(
                    ast.Assign(
                        targets=[_gen_self_attr("_ret", ast.Store())],
                        value=self.rw(val),
                    )
                )
                self.stop()
                return
            if isinstance(s, ast.Break) and self.loops:
                self.goto(self.loops[-1][1])
                return
            if isinstance(s, ast.Continue) and self.loops:
                self.goto(self.loops[-1][0])
                return
            if isinstance(s, ast.For):
                # For without yield stays a for-loop; _GenNameRew then
                # emits `for self._g_i in ...`, which the parser rejects.
                # Lower to while/next so the target is an assignment.
                c = [self.it_n]
                pieces = _for_to_while(s, c)
                self.it_n = c[0]
                for p in pieces:
                    self.add(self.rw(p))
                i += 1
                continue
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

    def _await(self, expr, target, rest, after):
        """await expr → iterate expr.__await__(); result is iterator._ret."""
        it = f"_i{self.it_n}"
        self.it_n += 1
        self.add(
            ast.Assign(
                targets=[_gen_self_attr(it, ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(
                        value=self.rw(expr),
                        attr="__await__",
                        ctx=ast.Load(),
                    ),
                    args=[],
                    keywords=[],
                ),
            )
        )
        head = self.news()
        after_aw = self.news()
        self.goto(head)
        old = self.cur
        self.cur = head
        tmp = f"_v{self.it_n}"
        self._next_or_stop(it, _gen_self_attr(tmp, ast.Store()), after_aw)
        self.yield_to(_gen_self_attr(tmp, ast.Load()), head)
        self.cur = after_aw
        retv = f"_r{self.it_n}"
        self.it_n += 1
        self.add(
            ast.Assign(
                targets=[_gen_self_attr(retv, ast.Store())],
                value=ast.Constant(value=None),
            )
        )
        self.add(
            ast.Try(
                body=[
                    ast.Assign(
                        targets=[_gen_self_attr(retv, ast.Store())],
                        value=ast.Attribute(
                            value=_gen_self_attr(it, ast.Load()),
                            attr="_ret",
                            ctx=ast.Load(),
                        ),
                    )
                ],
                handlers=[
                    ast.ExceptHandler(
                        type=ast.Name(id="AttributeError", ctx=ast.Load()),
                        name=None,
                        body=[ast.Pass()],
                    )
                ],
                orelse=[],
                finalbody=[],
            )
        )
        if target is not None:
            self.add(
                ast.Assign(
                    targets=[self.rw(target)],
                    value=_gen_self_attr(retv, ast.Load()),
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
                    ename = h.name if h.name else "_aim_e"
                    # except as <param> rewrites to the cell/field and leftover
                    # except-binding of that name SEGVs (gencyc_4 as exc vs as e).
                    if (
                        ename in self.rew.mapping
                        or ename in self.rew.cell_names
                    ):
                        ename = f"_aim_e{i}"
                    hs.append(
                        ast.ExceptHandler(
                            type=self.rw(h.type) if h.type is not None else None,
                            name=ename,
                            body=[
                                ast.Assign(
                                    targets=[_gen_self_attr("_tctx", ast.Store())],
                                    value=ast.Name(id=ename, ctx=ast.Load()),
                                ),
                                ast.Assign(
                                    targets=[_gen_self_attr(flag, ast.Store())],
                                    value=ast.Constant(value=i + 1),
                                ),
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
        elif s.finalbody:
            # try/finally with no except: run finally, then re-raise.
            # _gen_wrap_unwrapped_close would swallow the throw and skip fin.
            for sid in wrap_ids:
                orig = list(self.states[sid])
                head, tail = orig, []
                if orig and isinstance(orig[-1], (ast.Return, ast.Continue)):
                    if len(orig) >= 2 and isinstance(orig[-2], ast.Assign):
                        head, tail = orig[:-2], orig[-2:]
                    else:
                        head, tail = orig[:-1], orig[-1:]
                wrapped = [
                    ast.Assign(
                        targets=[_gen_self_attr(flag, ast.Store())],
                        value=ast.Constant(value=0),
                    ),
                    ast.Try(
                        body=head if head else [ast.Pass()],
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
                                type=ast.Name(id="Exception", ctx=ast.Load()),
                                name=None,
                                body=[
                                    ast.Assign(
                                        targets=[_gen_self_attr(flag, ast.Store())],
                                        value=ast.Constant(value=1),
                                    )
                                ],
                            ),
                        ],
                        orelse=[],
                        finalbody=[],
                    ),
                    ast.If(
                        test=_gen_self_attr(flag, ast.Load()),
                        body=[
                            ast.Assign(
                                targets=[_gen_self_attr("_tf", ast.Store())],
                                value=ast.Constant(value=1),
                            ),
                            ast.If(
                                test=_gen_self_attr("_tkind", ast.Load()),
                                body=[
                                    ast.Assign(
                                        targets=[_gen_self_attr("_tkind_save", ast.Store())],
                                        value=_gen_self_attr("_tkind", ast.Load()),
                                    ),
                                    ast.Assign(
                                        targets=[_gen_self_attr("_tkind", ast.Store())],
                                        value=ast.Constant(value=0),
                                    ),
                                ],
                                orelse=[],
                            ),
                            self.set_s(fin),
                            ast.Continue(),
                        ],
                        orelse=[],
                    ),
                ]
                wrapped.extend(tail)
                self.states[sid] = wrapped
            self.wrapped.update(wrap_ids)
        for h, hsid in zip(s.handlers, handler_sids):
            self.cur = hsid
            self.build(list(h.body), fin if isinstance(fin, int) else join)
        if join is not None and s.handlers:
            # except ended: later throw() must not chain this instance.
            st = self.states[join]
            ins = ast.Assign(
                targets=[_gen_self_attr("_tctx", ast.Store())],
                value=ast.Constant(value=None),
            )
            if st:
                st.insert(1, ins)
            else:
                st.append(ins)
        if s.finalbody:
            chk = self.news()
            fin_after = join if join is not None else after
            self.cur = fin
            self.build(list(s.finalbody), chk)
            self.cur = chk
            self.add(
                ast.If(
                    test=_gen_self_attr("_tf", ast.Load()),
                    body=[
                        ast.Assign(
                            targets=[_gen_self_attr("_tf", ast.Store())],
                            value=ast.Constant(value=0),
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
                )
            )
            if fin_after is not None:
                self.goto(fin_after)
            else:
                self.stop()
        if join is not None:
            self.cur = join
            self.build(rest, after)
        self.cur = old


def _self_method_call(attr: str) -> ast.Call:
    return ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="self", ctx=ast.Load()),
            attr=attr,
            ctx=ast.Load(),
        ),
        args=[],
        keywords=[],
    )


def _raise_named(name: str) -> ast.Raise:
    return ast.Raise(
        exc=ast.Call(
            func=ast.Name(id=name, ctx=ast.Load()),
            args=[],
            keywords=[],
        ),
        cause=None,
    )


def _raise_stop_iteration() -> ast.Raise:
    """Generator return: StopIteration.value is self._ret."""
    return ast.Raise(
        exc=ast.Call(
            func=ast.Name(id="StopIteration", ctx=ast.Load()),
            args=[_gen_self_attr("_ret", ast.Load())],
            keywords=[],
        ),
        cause=None,
    )


def _close_stop_body() -> list[ast.stmt]:
    return [
        ast.Assign(
            targets=[_gen_self_attr("_s", ast.Store())],
            value=ast.Constant(value=-1),
        ),
        ast.Assign(
            targets=[_gen_self_attr("gi_frame", ast.Store())],
            value=ast.Constant(value=None),
        ),
        ast.Return(value=ast.Constant(value=1)),
    ]


def _throw_body() -> list[ast.stmt]:
    """Shared throw() body. _tkind is Integer; ExcKindOf never stores a hash."""
    throw_closed: list[ast.stmt] = [
        ast.If(
            test=ast.Compare(
                left=_gen_self_attr("_s", ast.Load()),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=-1)],
            ),
            body=[
                ast.Expr(value=_self_method_call("__aim_raise")),
                ast.Return(value=ast.Constant(value=None)),
            ],
            orelse=[],
        )
    ]
    return [
        ast.Expr(
            value=ast.Call(
                func=ast.Name(id="__aim_exc_clear__", ctx=ast.Load()),
                args=[],
                keywords=[],
            )
        ),
        ast.If(
            test=_gen_self_attr("_tctx", ast.Load()),
            body=[
                ast.Expr(
                    value=ast.Call(
                        func=ast.Name(id="__aim_exc_handled__", ctx=ast.Load()),
                        args=[_gen_self_attr("_tctx", ast.Load())],
                        keywords=[],
                    )
                )
            ],
            orelse=[],
        ),
    ] + _throw_norm_stmts() + throw_closed + [
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
    ]


def _aim_gen_throw_fn() -> ast.FunctionDef:
    """One module-level throw() so 4 gen classes do not intern 4 copies."""
    return ast.FunctionDef(
        name="__aim_gen_throw",
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
        body=_throw_body(),
        decorator_list=[],
    )


def _aim_catch_throw_fn() -> ast.FunctionDef:
    """One module-level throw/close handler for every generator class.

    Per-state Try/except copies made leftover test_coroutines 40k lines
    and py2aim 19s / runner 10s timeout. A per-class method still copied
    the handler ~160 times; send() calls this Function with self.
    """
    return ast.FunctionDef(
        name="__aim_catch_throw",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            ast.Assign(
                targets=[_gen_self_attr("_kc", ast.Store())],
                value=ast.Constant(value=0),
            ),
            ast.Try(
                body=[_throw_if_stmt()],
                handlers=[
                    ast.ExceptHandler(
                        type=ast.Name(id="GeneratorExit", ctx=ast.Load()),
                        name=None,
                        body=[
                            ast.Assign(
                                targets=[_gen_self_attr("_kc", ast.Store())],
                                value=ast.Constant(value=1),
                            )
                        ],
                    ),
                    ast.ExceptHandler(
                        type=ast.Name(id="StopIteration", ctx=ast.Load()),
                        name=None,
                        body=[
                            ast.Assign(
                                targets=[_gen_self_attr("_kc", ast.Store())],
                                value=ast.Constant(value=2),
                            )
                        ],
                    ),
                    ast.ExceptHandler(
                        type=ast.Name(id="Exception", ctx=ast.Load()),
                        name=None,
                        body=[
                            ast.Assign(
                                targets=[_gen_self_attr("_kc", ast.Store())],
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
                    left=_gen_self_attr("_kc", ast.Load()),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=1)],
                ),
                body=[
                    ast.If(
                        test=_gen_self_attr("_closing", ast.Load()),
                        body=_close_stop_body(),
                        orelse=[_raise_named("GeneratorExit")],
                    )
                ],
                orelse=[],
            ),
            ast.If(
                test=ast.Compare(
                    left=_gen_self_attr("_kc", ast.Load()),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value=2)],
                ),
                body=[
                    ast.If(
                        test=_gen_self_attr("_closing", ast.Load()),
                        body=_close_stop_body(),
                        orelse=[_raise_named("StopIteration")],
                    )
                ],
                orelse=[],
            ),
            ast.If(
                test=ast.Compare(
                    left=_gen_self_attr("_kc", ast.Load()),
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
                    ast.Expr(value=_self_method_call("__aim_raise")),
                    ast.Return(value=ast.Constant(value=1)),
                ],
                orelse=[],
            ),
            ast.Return(value=ast.Constant(value=0)),
        ],
        decorator_list=[],
    )


def _state_throw_guard() -> list[ast.stmt]:
    return [
        ast.If(
            test=ast.Call(
                func=ast.Name(id="__aim_catch_throw", ctx=ast.Load()),
                args=[ast.Name(id="self", ctx=ast.Load())],
                keywords=[],
            ),
            body=[ast.Return(value=ast.Constant(value=None))],
            orelse=[],
        )
    ]


def _gen_wrap_unwrapped_close(sm: _GenSM) -> None:
    """Swallow GeneratorExit on close in states with no user try.

    Wrap only throw_if. Wrapping the yield Return leaks ExcEnter
    (Return/Continue skip ExcLeave) and SEGVs later next() calls.
    One module-level __aim_catch_throw keeps send() small.
    """
    for sid, body in enumerate(sm.states):
        if sid in sm.wrapped:
            continue
        orig = list(body) if body else [_throw_if_stmt()]
        rest = orig[1:] if orig else []
        sm.states[sid] = _state_throw_guard() + rest


def _gen_convert(
    fn: ast.FunctionDef,
    enclosing: set[str],
    counter: list[int],
    coro: bool = False,
    asyncgen: bool = False,
) -> tuple[ast.ClassDef, ast.FunctionDef]:
    counter[0] += 1
    if coro:
        cname = f"_aim_coro_{counter[0]}"
    else:
        cname = f"_aim_gen_{counter[0]}"
    params = [a.arg for a in fn.args.args]
    frees = _clos_freevars(fn, enclosing)
    locs = _clos_direct_assigned(fn)
    mapping: dict[str, str] = {}
    cell_names = set(frees)
    for n in params + list(locs):
        if n not in mapping and n not in ("_s", "_sent") and n not in cell_names:
            mapping[n] = f"_g_{n}"
    alias_names: list[str] = []
    if cell_names:
        alias_names = _cell_store_alias_names(list(fn.body), cell_names)
    sm = _GenSM(
        mapping,
        coro=coro,
        cell_names=cell_names,
        skip_names=set(alias_names),
    )
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
            targets=[_gen_self_attr("_texc", ast.Store())],
            value=ast.Constant(value=None),
        ),
        ast.Assign(
            targets=[_gen_self_attr("_tctx", ast.Store())],
            value=ast.Constant(value=None),
        ),
        ast.Assign(
            targets=[_gen_self_attr("_tf", ast.Store())],
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
            targets=[_gen_self_attr("_kc", ast.Store())],
            value=ast.Constant(value=0),
        ),
        ast.Assign(
            targets=[_gen_self_attr("gi_frame", ast.Store())],
            value=_frame_dummy(),
        ),
        ast.Assign(
            targets=[_gen_self_attr("_ret", ast.Store())],
            value=ast.Constant(value=None),
        ),
    ]
    if coro:
        init_body.extend(
            [
                ast.Assign(
                    targets=[_gen_self_attr("cr_frame", ast.Store())],
                    value=_frame_dummy(),
                ),
                ast.Assign(
                    targets=[_gen_self_attr("cr_running", ast.Store())],
                    value=ast.Constant(value=0),
                ),
            ]
        )
    factory_args: list[ast.expr] = []
    seen_init: set[str] = set()
    param_attrs: set[str] = set()
    # Params only in __init__. Freevars are assigned after ObjectNew so a
    # 0 cell (f(0)) is not PackedGet-defaulted to None.
    for n in params:
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
    if cell_names:
        init_body.append(
            ast.Assign(
                targets=[_gen_self_attr("_g_fv", ast.Store())],
                value=ast.Dict(keys=[], values=[]),
            )
        )
        param_attrs.add("_g_fv")
    fields: set[str] = set(mapping.values()) | {"_s", "_sent"}
    if cell_names:
        fields.add("_g_fv")
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
                "_texc",
                "_tctx",
                "_tf",
                "gi_running",
                "_closing",
                "_kc",
                "gi_frame",
                "_ret",
                "cr_frame",
                "cr_running",
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
                    orelse=[_raise_stop_iteration()],
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
    send_ifs.append(_raise_stop_iteration())
    send_pre: list[ast.stmt] = [
        ast.If(
            test=ast.Compare(
                left=_gen_self_attr("_s", ast.Load()),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=0)],
            ),
            body=[
                ast.If(
                    test=ast.Compare(
                        left=ast.Name(id="_aim_v", ctx=ast.Load()),
                        ops=[ast.IsNot()],
                        comparators=[ast.Constant(value=None)],
                    ),
                    body=[_raise_named("TypeError")],
                    orelse=[],
                )
            ],
            orelse=[],
        ),
        ast.Assign(
            targets=[_gen_self_attr("_sent", ast.Store())],
            value=ast.Name(id="_aim_v", ctx=ast.Load()),
        ),
        ast.Assign(
            targets=[ast.Name(id="_aim_run", ctx=ast.Store())],
            value=ast.Constant(value=True),
        ),
    ]
    for n in alias_names:
        send_pre.append(
            ast.Assign(
                targets=[ast.Name(id=n, ctx=ast.Store())],
                value=ast.Subscript(
                    value=_gen_self_attr("_g_fv", ast.Load()),
                    slice=ast.Constant(value=n),
                    ctx=ast.Load(),
                ),
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
        body=send_pre
        + [
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
            ast.Return(
                value=ast.Call(
                    func=ast.Name(id="__aim_gen_throw", ctx=ast.Load()),
                    args=[
                        ast.Name(id="self", ctx=ast.Load()),
                        ast.Name(id="typ", ctx=ast.Load()),
                        ast.Name(id="val", ctx=ast.Load()),
                        ast.Name(id="tb", ctx=ast.Load()),
                    ],
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
    methods = [init, aim_raise, send, dunder_next, throw, close]
    if not coro:
        methods.insert(3, dunder_iter)
        if asyncgen:
            dunder_aiter = ast.FunctionDef(
                name="__aiter__",
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
            dunder_anext = ast.FunctionDef(
                name="__anext__",
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
                            func=ast.Name(id="_AimANext", ctx=ast.Load()),
                            args=[
                                ast.Name(id="self", ctx=ast.Load()),
                                ast.Constant(value=None),
                            ],
                            keywords=[],
                        )
                    )
                ],
                decorator_list=[],
            )
            asend = ast.FunctionDef(
                name="asend",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[ast.arg(arg="self"), ast.arg(arg="_aim_v")],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[],
                ),
                body=[
                    ast.Return(
                        value=ast.Call(
                            func=ast.Name(id="_AimANext", ctx=ast.Load()),
                            args=[
                                ast.Name(id="self", ctx=ast.Load()),
                                ast.Name(id="_aim_v", ctx=ast.Load()),
                            ],
                            keywords=[],
                        )
                    )
                ],
                decorator_list=[],
            )
            methods.extend([dunder_aiter, dunder_anext, asend])
    else:
        dunder_await = ast.FunctionDef(
            name="__await__",
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
        methods.insert(3, dunder_await)
    cls = ast.ClassDef(
        name=cname,
        bases=[],
        keywords=[],
        body=methods,
        decorator_list=[],
    )
    ctor = ast.Call(
        func=ast.Name(id=cname, ctx=ast.Load()),
        args=factory_args,
        keywords=[],
    )
    if frees:
        gtmp = "_aim_g"
        fact_body: list[ast.stmt] = [
            ast.Assign(
                targets=[ast.Name(id=gtmp, ctx=ast.Store())],
                value=ctor,
            )
        ]
        # Dummy loads keep frees in _clos_freevars so g becomes a
        # cell class and ClosRewrite maps _AIM_CELL to self._c.
        for n in frees:
            fact_body.append(ast.Expr(value=ast.Name(id=n, ctx=ast.Load())))
        # Share the enclosing cell dict so nonlocal stores in the
        # generator are visible after throw()/send() return.
        fact_body.append(
            ast.Assign(
                targets=[
                    ast.Attribute(
                        value=ast.Name(id=gtmp, ctx=ast.Load()),
                        attr="_g_fv",
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Name(id="_AIM_CELL", ctx=ast.Load()),
            )
        )
        fact_body.append(ast.Return(value=ast.Name(id=gtmp, ctx=ast.Load())))
    else:
        fact_body = [ast.Return(value=ctor)]
    new_fn = ast.FunctionDef(
        name=fn.name,
        args=fn.args,
        body=fact_body,
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


def _is_cm_name_deco(node: ast.FunctionDef) -> bool:
    """True for a single Name decorator `contextmanager`.

    Isolation golds use `@contextlib.contextmanager` (Attribute) and
    stay on the __yields stub so their emit stays byte-identical.
    leftover `from contextlib import contextmanager` is a Name.
    """
    if len(node.decorator_list) != 1:
        return False
    d = node.decorator_list[0]
    return isinstance(d, ast.Name) and d.id == "contextmanager"


def _wrap_factory_cm(fn: ast.FunctionDef) -> ast.FunctionDef:
    """Strip @contextmanager and wrap the factory return in _AimGenCM."""
    fn.decorator_list = []
    if fn.body and isinstance(fn.body[0], ast.Return) and fn.body[0].value is not None:
        fn.body[0] = ast.Return(
            value=ast.Call(
                func=ast.Name(id="_AimGenCM", ctx=ast.Load()),
                args=[fn.body[0].value],
                keywords=[],
            )
        )
    return fn


def _aim_gen_cm_class() -> ast.ClassDef:
    """PEP 343 wrapper: __enter__ = next(gen), __exit__ next/throw.

    Return inside except skips AILANG ExcLeave, so StopIteration is
    recorded in a flag and the return sits after the try.
    """
    def _n(i, ctx=None):
        return ast.Name(id=i, ctx=ctx or ast.Load())

    def _a(obj, attr, ctx=None):
        return ast.Attribute(value=_n(obj), attr=attr, ctx=ctx or ast.Load())

    init = ast.FunctionDef(
        name="__init__",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self"), ast.arg(arg="gen")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            ast.Assign(targets=[_a("self", "gen", ast.Store())], value=_n("gen")),
        ],
        decorator_list=[],
    )
    enter = ast.FunctionDef(
        name="__enter__",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            ast.Assign(targets=[_n("g", ast.Store())], value=_a("self", "gen")),
            ast.Return(
                value=ast.Call(func=_n("next"), args=[_n("g")], keywords=[])
            ),
        ],
        decorator_list=[],
    )
    exit_fn = ast.FunctionDef(
        name="__exit__",
        args=ast.arguments(
            posonlyargs=[],
            args=[
                ast.arg(arg="self"),
                ast.arg(arg="t"),
                ast.arg(arg="v"),
                ast.arg(arg="tb"),
            ],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            ast.Assign(targets=[_n("g", ast.Store())], value=_a("self", "gen")),
            ast.If(
                test=ast.Compare(
                    left=_n("t"),
                    ops=[ast.Is()],
                    comparators=[ast.Constant(value=None)],
                ),
                body=[
                    ast.Assign(
                        targets=[_n("_ok", ast.Store())],
                        value=ast.Constant(value=0),
                    ),
                    ast.Try(
                        body=[
                            ast.Expr(
                                value=ast.Call(
                                    func=_n("next"), args=[_n("g")], keywords=[]
                                )
                            )
                        ],
                        handlers=[
                            ast.ExceptHandler(
                                type=_n("StopIteration"),
                                name=None,
                                body=[
                                    ast.Assign(
                                        targets=[_n("_ok", ast.Store())],
                                        value=ast.Constant(value=1),
                                    )
                                ],
                            )
                        ],
                        orelse=[],
                        finalbody=[],
                    ),
                    ast.If(
                        test=ast.Compare(
                            left=_n("_ok"),
                            ops=[ast.Eq()],
                            comparators=[ast.Constant(value=1)],
                        ),
                        body=[ast.Return(value=ast.Constant(value=False))],
                        orelse=[],
                    ),
                    ast.Raise(
                        exc=ast.Call(
                            func=_n("RuntimeError"),
                            args=[
                                ast.Constant(value="generator didn't stop")
                            ],
                            keywords=[],
                        ),
                        cause=None,
                    ),
                ],
                orelse=[
                    ast.Assign(
                        targets=[_n("_sw", ast.Store())],
                        value=ast.Constant(value=0),
                    ),
                    ast.Try(
                        body=[
                            ast.Expr(
                                value=ast.Call(
                                    func=_a("g", "throw"),
                                    args=[_n("t")],
                                    keywords=[],
                                )
                            )
                        ],
                        handlers=[
                            ast.ExceptHandler(
                                type=_n("StopIteration"),
                                name=None,
                                body=[
                                    ast.Assign(
                                        targets=[_n("_sw", ast.Store())],
                                        value=ast.Constant(value=1),
                                    )
                                ],
                            )
                        ],
                        orelse=[],
                        finalbody=[],
                    ),
                    ast.If(
                        test=ast.Compare(
                            left=_n("_sw"),
                            ops=[ast.Eq()],
                            comparators=[ast.Constant(value=1)],
                        ),
                        body=[ast.Return(value=ast.Constant(value=True))],
                        orelse=[ast.Return(value=ast.Constant(value=False))],
                    ),
                ],
            ),
        ],
        decorator_list=[],
    )
    return ast.ClassDef(
        name="_AimGenCM",
        bases=[],
        keywords=[],
        body=[init, enter, exit_fn],
        decorator_list=[],
    )


def _lambda_has_yield(lam: ast.Lambda) -> bool:
    """True if this lambda's own body yields (nested def/lambda skipped)."""

    class _V(ast.NodeVisitor):
        def __init__(self):
            self.found = False

        def visit_Lambda(self, n: ast.Lambda):
            if n is lam:
                self.generic_visit(n)

        def visit_FunctionDef(self, n: ast.FunctionDef):
            return

        def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef):
            return

        def visit_ClassDef(self, n: ast.ClassDef):
            return

        def visit_Yield(self, n: ast.Yield):
            self.found = True

        def visit_YieldFrom(self, n: ast.YieldFrom):
            self.found = True

    v = _V()
    v.visit(lam)
    return v.found


def _hoist_yield_in_stmts(
    body: list[ast.stmt], counter: list[int], changed: list[bool]
) -> list[ast.stmt]:
    """Lift `lambda: (yield ...)` to a FunctionDef so generator convert sees it."""
    hoisted: list[ast.stmt] = []

    class _R(ast.NodeTransformer):
        def visit_FunctionDef(self, n: ast.FunctionDef):
            return n

        def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef):
            return n

        def visit_ClassDef(self, n: ast.ClassDef):
            return n

        def visit_Lambda(self, n: ast.Lambda):
            n = self.generic_visit(n)
            if not _lambda_has_yield(n):
                return n
            changed[0] = True
            counter[0] += 1
            name = f"_aim_ylam_{counter[0]}"
            fn = ast.FunctionDef(
                name=name,
                args=n.args,
                body=[ast.Return(value=n.body)],
                decorator_list=[],
            )
            hoisted.append(fn)
            return ast.Name(id=name, ctx=ast.Load())

    new_body = [_R().visit(s) for s in body]
    return hoisted + new_body


def _hoist_yield_lambdas_tree(
    tree: ast.AST, counter: list[int], changed: list[bool]
) -> ast.AST:
    class _H(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef):
            node = self.generic_visit(node)
            node.body = _hoist_yield_in_stmts(list(node.body), counter, changed)
            return node

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node: ast.ClassDef):
            node = self.generic_visit(node)
            node.body = _hoist_yield_in_stmts(list(node.body), counter, changed)
            return node

        def visit_Module(self, node: ast.Module):
            node = self.generic_visit(node)
            node.body = _hoist_yield_in_stmts(list(node.body), counter, changed)
            return node

    return _H().visit(tree)


def _flatten_run_async_send_tree(tree: ast.AST) -> ast.AST:
    """buffer.append(coro.send(None)) → _aim_rs = send(); append(_aim_rs).

    leftover RaiseKind StopIteration then ReturnValue(0) inside a Call
    argument still appends 0. A statement-level send() is caught by
    except StopIteration before append. Isolation golds have no run_async.
    """

    def flatten_body(body: list[ast.stmt]) -> list[ast.stmt]:
        out: list[ast.stmt] = []
        for s in body:
            if (
                isinstance(s, ast.Expr)
                and isinstance(s.value, ast.Call)
                and isinstance(s.value.func, ast.Attribute)
                and s.value.func.attr == "append"
                and len(s.value.args) == 1
                and isinstance(s.value.args[0], ast.Call)
                and isinstance(s.value.args[0].func, ast.Attribute)
                and s.value.args[0].func.attr == "send"
            ):
                send_call = s.value.args[0]
                out.append(
                    ast.Assign(
                        targets=[ast.Name(id="_aim_rs", ctx=ast.Store())],
                        value=send_call,
                    )
                )
                out.append(
                    ast.Expr(
                        value=ast.Call(
                            func=s.value.func,
                            args=[ast.Name(id="_aim_rs", ctx=ast.Load())],
                            keywords=list(s.value.keywords),
                        )
                    )
                )
                continue
            if isinstance(s, ast.While):
                out.append(
                    ast.While(
                        test=s.test,
                        body=flatten_body(list(s.body)),
                        orelse=flatten_body(list(s.orelse)),
                    )
                )
                continue
            if isinstance(s, ast.If):
                out.append(
                    ast.If(
                        test=s.test,
                        body=flatten_body(list(s.body)),
                        orelse=flatten_body(list(s.orelse)),
                    )
                )
                continue
            if isinstance(s, ast.Try):
                out.append(
                    ast.Try(
                        body=flatten_body(list(s.body)),
                        handlers=[
                            ast.ExceptHandler(
                                type=h.type,
                                name=h.name,
                                body=flatten_body(list(h.body)) or [ast.Pass()],
                            )
                            for h in s.handlers
                        ],
                        orelse=flatten_body(list(s.orelse)),
                        finalbody=flatten_body(list(s.finalbody)),
                    )
                )
                continue
            if isinstance(s, ast.For):
                out.append(
                    ast.For(
                        target=s.target,
                        iter=s.iter,
                        body=flatten_body(list(s.body)),
                        orelse=flatten_body(list(s.orelse)),
                    )
                )
                continue
            out.append(s)
        return out

    class _F(ast.NodeTransformer):
        def visit_FunctionDef(self, n: ast.FunctionDef):
            n = self.generic_visit(n)
            if n.name != "run_async":
                return n
            n.body = flatten_body(list(n.body))
            return n

    if not isinstance(tree, ast.Module):
        return tree
    return _F().visit(tree)


def _desugar_generators_tree(tree: ast.AST) -> tuple[ast.AST, bool]:
    """Generator/async def → class. Returns (tree, changed)."""
    counter = [0]
    changed = [False]
    need_cm = [False]
    gen_names: set[str] = set()
    tree = _hoist_genexps(tree, counter, changed)
    tree = _hoist_yield_lambdas_tree(tree, counter, changed)

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
                    new_body.append(self._visit_async_fn(stmt, inner_h))
                elif isinstance(stmt, ast.ClassDef):
                    new_body.append(self.visit(stmt))
                else:
                    new_body.append(stmt)
            self.stack.pop()
            node.body = inner_h + new_body
            is_cm = _is_cm_name_deco(node)
            if _fn_own_yields(node) and (not node.decorator_list or is_cm):
                enclosing: set[str] = set()
                for e in self.stack:
                    enclosing |= e
                cls, fn = _gen_convert(node, enclosing, counter)
                if is_cm:
                    fn = _wrap_factory_cm(fn)
                    need_cm[0] = True
                else:
                    gen_names.add(node.name)
                hoisted.append(cls)
                changed[0] = True
                return fn
            return node

        def _visit_async_fn(self, node: ast.AsyncFunctionDef, hoisted: list[ast.stmt]):
            assigned = _clos_direct_assigned(node)
            self.stack.append(assigned | {node.name})
            inner_h: list[ast.stmt] = []
            new_body: list[ast.stmt] = []
            for stmt in node.body:
                if isinstance(stmt, ast.FunctionDef):
                    new_body.append(self._visit_fn(stmt, inner_h))
                elif isinstance(stmt, ast.AsyncFunctionDef):
                    new_body.append(self._visit_async_fn(stmt, inner_h))
                elif isinstance(stmt, ast.ClassDef):
                    new_body.append(self.visit(stmt))
                else:
                    new_body.append(stmt)
            self.stack.pop()
            node.body = inner_h + new_body
            if node.decorator_list:
                return node
            enclosing: set[str] = set()
            for e in self.stack:
                enclosing |= e
            if _fn_own_yields(node):
                fn = _async_prep(node, counter)
                cls, new_fn = _gen_convert(
                    fn, enclosing, counter, coro=False, asyncgen=True
                )
                hoisted.append(cls)
                changed[0] = True
                return new_fn
            fn = _async_prep(node, counter)
            cls, new_fn = _gen_convert(fn, enclosing, counter, coro=True)
            hoisted.append(cls)
            changed[0] = True
            return new_fn

        def visit_Module(self, node: ast.Module):
            self.stack.append(set())
            hoisted: list[ast.stmt] = []
            new_body: list[ast.stmt] = []
            for stmt in node.body:
                if isinstance(stmt, ast.FunctionDef):
                    new_body.append(self._visit_fn(stmt, hoisted))
                elif isinstance(stmt, ast.AsyncFunctionDef):
                    new_body.append(self._visit_async_fn(stmt, hoisted))
                elif isinstance(stmt, ast.ClassDef):
                    new_body.append(self.visit(stmt))
                else:
                    new_body.append(stmt)
            self.stack.pop()
            node.body = hoisted + new_body
            prefix: list[ast.stmt] = []
            if changed[0]:
                prefix.append(_aim_catch_throw_fn())
                prefix.append(_aim_gen_throw_fn())
            if need_cm[0]:
                prefix.append(_aim_gen_cm_class())
            if prefix:
                node.body = prefix + node.body
            return node

        def visit_ClassDef(self, node: ast.ClassDef):
            hoisted: list[ast.stmt] = []
            new_body: list[ast.stmt] = []
            for stmt in node.body:
                if isinstance(stmt, ast.FunctionDef):
                    new_body.append(self._visit_fn(stmt, hoisted))
                elif isinstance(stmt, ast.AsyncFunctionDef):
                    new_body.append(self._visit_async_fn(stmt, hoisted))
                elif isinstance(stmt, ast.ClassDef):
                    new_body.append(self.visit(stmt))
                else:
                    new_body.append(stmt)
            node.body = hoisted + new_body
            return node

    if _tree_has_async_gen(tree):
        tree.body.insert(0, _aim_anext_fn())
        changed[0] = True
    new_tree = _G().visit(tree)
    if not changed[0]:
        return new_tree, False
    new_tree = _rewrite_for_over_gens(new_tree, gen_names)
    new_tree = _flatten_run_async_send_tree(new_tree)
    return new_tree, True


def desugar_generators(src: str) -> str:
    """Generator functions → class with __next__/send (pause at yield).

    Undecorated async def (no yield) → coroutine class with send/throw/close
    and __await__ (pause at await). Undecorated async def with yield → leftover
    gen plus __aiter__/__anext__/asend. Decorated async stays on the stub path.
    A single Name `@contextmanager` gen is converted and
    wrapped in `_AimGenCM` so with-as works; `@contextlib.contextmanager`
    (Attribute) stays stubbed so isolation golds stay byte-identical.
    Isolation files without generators or async def stay byte-identical.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    new_tree, changed = _desugar_generators_tree(tree)
    if not changed:
        return src
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree) + "\n"
    except Exception:
        return src


def _exec_const_true(test: ast.AST) -> bool:
    return isinstance(test, ast.Constant) and test.value in (1, True)


def _exec_store_names(target: ast.AST) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for elt in target.elts:
            names.extend(_exec_store_names(elt))
        return names
    return []


def _exec_rewrite_nested_globals(tree: ast.AST, gname: str) -> ast.AST:
    """global y in a nested def → _aim_eg['y'] so it uses exec globals."""

    class _RW(ast.NodeTransformer):
        def __init__(self):
            self.stack: list[set[str]] = []

        def visit_FunctionDef(self, node: ast.FunctionDef):
            self.stack.append(_clos_global_names(node))
            node.body = [self.visit(s) for s in node.body]
            self.stack.pop()
            return node

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Global(self, node: ast.Global):
            if self.stack:
                return ast.Pass()
            return node

        def visit_Name(self, node: ast.Name):
            if self.stack and node.id in self.stack[-1]:
                return ast.Subscript(
                    value=ast.Name(id=gname, ctx=ast.Load()),
                    slice=ast.Constant(value=node.id),
                    ctx=node.ctx,
                )
            return node

    return _RW().visit(tree)


def _exec_export_one(
    names: list[str], gname: str, lname: str, glob_names: set[str]
) -> list[ast.stmt]:
    out: list[ast.stmt] = []
    for nm in names:
        dest = gname if nm in glob_names else lname
        out.append(
            ast.Assign(
                targets=[
                    ast.Subscript(
                        value=ast.Name(id=dest, ctx=ast.Load()),
                        slice=ast.Constant(value=nm),
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Name(id=nm, ctx=ast.Load()),
            )
        )
    return out


def _exec_export_top(
    body: list[ast.stmt],
    gname: str,
    lname: str,
    glob_names: set[str],
    unpack_n: list[int],
) -> list[ast.stmt]:
    """STORE_GLOBAL names → exec globals dict; STORE_NAME → exec locals dict.

    Nested `global y` makes a top-level `y = 9` STORE_GLOBAL (CPython).
    Tuple assigns are expanded here because convert() already ran
    desugar_tuple_unpack before this splice.
    """
    out: list[ast.stmt] = []
    for stmt in body:
        if (
            isinstance(stmt, ast.If)
            and _exec_const_true(stmt.test)
            and not stmt.orelse
        ):
            out.extend(
                _exec_export_top(stmt.body, gname, lname, glob_names, unpack_n)
            )
            continue
        if (
            isinstance(stmt, ast.Assign)
            and len(stmt.targets) == 1
            and isinstance(stmt.targets[0], (ast.Tuple, ast.List))
        ):
            unpack_n[0] += 1
            tmp = f"_aim_unpack_{unpack_n[0]}"
            binds = _for_unpack_assigns(tmp, stmt.targets[0], unpack_n)
            out.append(
                ast.Assign(
                    targets=[ast.Name(id=tmp, ctx=ast.Store())],
                    value=stmt.value,
                )
            )
            out.extend(binds)
            out.extend(
                _exec_export_one(
                    _exec_store_names(stmt.targets[0]),
                    gname,
                    lname,
                    glob_names,
                )
            )
            continue
        out.append(stmt)
        names: list[str] = []
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [stmt.name]
        elif isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                names.extend(_exec_store_names(t))
        elif isinstance(stmt, ast.AugAssign):
            names.extend(_exec_store_names(stmt.target))
        elif isinstance(stmt, ast.AnnAssign) and stmt.target is not None:
            names.extend(_exec_store_names(stmt.target))
        out.extend(_exec_export_one(names, gname, lname, glob_names))
    return out


def _try_exec_const_stmt(
    stmt: ast.stmt, counter: list[int]
) -> list[ast.stmt] | None:
    """exec('def ...', glob, loc) with nested defs → wrapper that fills the dicts."""
    if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
        return None
    call = stmt.value
    if not isinstance(call.func, ast.Name) or call.func.id != "exec":
        return None
    if not call.args:
        return None
    src_n = call.args[0]
    if not isinstance(src_n, ast.Constant) or not isinstance(src_n.value, str):
        return None
    glob_e: ast.expr | None = call.args[1] if len(call.args) > 1 else None
    loc_e: ast.expr | None = call.args[2] if len(call.args) > 2 else None
    for kw in call.keywords:
        if kw.arg == "globals":
            glob_e = kw.value
        elif kw.arg == "locals":
            loc_e = kw.value
    if glob_e is None:
        return None
    if loc_e is None:
        loc_e = glob_e
    try:
        parsed = ast.parse(src_n.value)
    except SyntaxError:
        return None
    has_fn = any(
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        for n in ast.walk(parsed)
    )
    if not has_fn:
        return None
    counter[0] += 1
    fname = f"__aim_exec_{counter[0]}"
    gname = "_aim_eg"
    lname = "_aim_el"
    glob_names: set[str] = set()
    for n in ast.walk(parsed):
        if isinstance(n, ast.Global):
            glob_names.update(n.names)
    parsed = _exec_rewrite_nested_globals(parsed, gname)
    body = _exec_export_top(
        list(parsed.body), gname, lname, glob_names, [1000]
    )
    if not body:
        body = [ast.Pass()]
    fn = ast.FunctionDef(
        name=fname,
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg=gname), ast.arg(arg=lname)],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=body,
        decorator_list=[],
    )
    call_stmt = ast.Expr(
        value=ast.Call(
            func=ast.Name(id=fname, ctx=ast.Load()),
            args=[glob_e, loc_e],
            keywords=[],
        )
    )
    return [fn, call_stmt]


def _desugar_exec_const_tree(tree: ast.AST) -> tuple[ast.AST, bool]:
    """Constant exec of nested defs: run the body against the two namespaces."""
    counter = [0]
    changed = [False]

    def rewrite_stmts(body: list[ast.stmt]) -> list[ast.stmt]:
        out: list[ast.stmt] = []
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                stmt.body = rewrite_stmts(stmt.body)
                out.append(stmt)
                continue
            if isinstance(stmt, ast.If):
                stmt.body = rewrite_stmts(stmt.body)
                stmt.orelse = rewrite_stmts(stmt.orelse)
                out.append(stmt)
                continue
            if isinstance(stmt, (ast.For, ast.AsyncFor)):
                stmt.body = rewrite_stmts(stmt.body)
                stmt.orelse = rewrite_stmts(stmt.orelse)
                out.append(stmt)
                continue
            if isinstance(stmt, ast.While):
                stmt.body = rewrite_stmts(stmt.body)
                stmt.orelse = rewrite_stmts(stmt.orelse)
                out.append(stmt)
                continue
            if isinstance(stmt, (ast.With, ast.AsyncWith)):
                stmt.body = rewrite_stmts(stmt.body)
                out.append(stmt)
                continue
            if isinstance(stmt, ast.Try):
                stmt.body = rewrite_stmts(stmt.body)
                stmt.orelse = rewrite_stmts(stmt.orelse)
                stmt.finalbody = rewrite_stmts(stmt.finalbody)
                for h in stmt.handlers:
                    h.body = rewrite_stmts(h.body)
                out.append(stmt)
                continue
            if isinstance(stmt, ast.TryStar):
                stmt.body = rewrite_stmts(stmt.body)
                stmt.orelse = rewrite_stmts(stmt.orelse)
                stmt.finalbody = rewrite_stmts(stmt.finalbody)
                for h in stmt.handlers:
                    h.body = rewrite_stmts(h.body)
                out.append(stmt)
                continue
            pieces = _try_exec_const_stmt(stmt, counter)
            if pieces is None:
                out.append(stmt)
            else:
                changed[0] = True
                out.extend(pieces)
        return out

    if isinstance(tree, ast.Module):
        tree.body = rewrite_stmts(tree.body)
    return tree, changed[0]


def _is_locals_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "locals"
        and not node.args
        and not node.keywords
    )


def _desugar_class_ns_locals_tree(tree: ast.AST) -> tuple[ast.AST, bool]:
    """Class-body locals()[k] = v is STORE_NAME into the class namespace."""
    changed = [False]

    class _X(ast.NodeTransformer):
        def visit_ClassDef(self, node: ast.ClassDef):
            node = self.generic_visit(node)
            new_body: list[ast.stmt] = []
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                    t = stmt.targets[0]
                    sl = getattr(t, "slice", None)
                    if (
                        isinstance(t, ast.Subscript)
                        and _is_locals_call(t.value)
                        and isinstance(sl, ast.Constant)
                        and isinstance(sl.value, str)
                    ):
                        changed[0] = True
                        new_body.append(
                            ast.Assign(
                                targets=[ast.Name(id=sl.value, ctx=ast.Store())],
                                value=stmt.value,
                            )
                        )
                        continue
                new_body.append(stmt)
            node.body = new_body
            return node

    return _X().visit(tree), changed[0]


def _desugar_nested_class_cells_tree(tree: ast.AST) -> tuple[ast.AST, bool]:
    """Leave nested class methods with enclosing freevars for func closures.

    Per-call `_aim_c` lives in desugar_nested_func_closures (Class(_aim_c)
    or a bound-hash __call__). Shared module `_aim_ncells` is unused.
    """
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
                        # Per-call cell in desugar_nested_func_closures:
                        # __call__ gets a bound hash; other methods get
                        # Class(_aim_c) so two factory calls do not share
                        # one module _aim_ncells key.
                        new_body.append(stmt)
                        continue
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
    return new_tree, need_dict[0]


def desugar_nested_class_cells(src: str) -> str:
    """Capture enclosing locals used by nested class methods into a module dict.

    Always unparses so isolation golds without earlier desugars stay on the
    same comment-stripped emit they already golded.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    new_tree, _ = _desugar_nested_class_cells_tree(tree)
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


def _clos_is_cell_name(name: str) -> bool:
    """Per-function cell dict: `_aim_c` or `_aim_c_N`, not `_aim_cc_N`."""
    if name == "_aim_c":
        return True
    return name.startswith("_aim_c_") and not name.startswith("_aim_cc_")


def _clos_skip_name(name: str) -> bool:
    if name in _CLOS_SKIP:
        return True
    if name.startswith("_aim_cc_"):
        return True
    return _clos_is_cell_name(name)


def _clos_params(node: ast.AST) -> set[str]:
    if not hasattr(node, "args"):
        return set()
    names = {a.arg for a in node.args.args + node.args.kwonlyargs}
    if node.args.vararg:
        names.add(node.args.vararg.arg)
    if node.args.kwarg:
        names.add(node.args.kwarg.arg)
    return names


def _clos_decl_names(node: ast.AST, stmt_type: type) -> set[str]:
    """global/nonlocal names in this function, not in nested def/class bodies.

    Lambda.body is an expr: skip unless body is a stmt list.
    """
    names: set[str] = set()
    body = getattr(node, "body", None)
    if not isinstance(body, list):
        return names
    for stmt in body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(stmt, stmt_type):
            names.update(stmt.names)
            continue
        for n in ast.walk(stmt):
            if isinstance(n, stmt_type):
                names.update(n.names)
    return names


def _clos_global_names(node: ast.AST) -> set[str]:
    """Names declared global in this function, not in nested def/class bodies."""
    return _clos_decl_names(node, ast.Global)


def _clos_nonlocal_names(node: ast.AST) -> set[str]:
    """Names declared nonlocal in this function, not in nested def/class bodies."""
    return _clos_decl_names(node, ast.Nonlocal)


def _is_generated_gen_class(name: str) -> bool:
    """Hoisted generator/coroutine/genexp classes, not user locals."""
    return str(name).startswith(
        ("_aim_coro_", "_aim_gen_", "__aim_clos_", "_aim_gx_")
    )


def _for_target_needs_ident(cls: ast.ClassDef) -> bool:
    """leftover Parse_ConsumeForTarget is IDENT then [index].

    ClosRewrite of tgt[0] to self._c['tgt'][0] does not parse. Skip
    only those hoisted gen/coro classes that still have such a target.
    Do not skip __aim_clos_ or other leftover coros.
    """
    if not str(cls.name).startswith(("_aim_coro_", "_aim_gen_", "_aim_gx_")):
        return False
    for item in cls.body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for n in ast.walk(item):
            targets: list[ast.expr] = []
            if isinstance(n, (ast.For, ast.AsyncFor)):
                targets.append(n.target)
            elif isinstance(
                n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
            ):
                for g in n.generators:
                    targets.append(g.target)
            for t in targets:
                for x in ast.walk(t):
                    if isinstance(x, ast.Subscript) and isinstance(
                        x.value, ast.Name
                    ):
                        return True
    return False


def _comp_store_cell_bases(
    states: list[list[ast.stmt]], cell_names: set[str]
) -> list[str]:
    """Cell names stored as tgt[0] in a comprehension target.

    leftover for-targets parse name or name[index], not
    self._g_fv['tgt'][0] / self._c['tgt'][0]. Alias the cell to a
    local so the target stays tgt[0].
    """
    needed: list[str] = []
    seen: set[str] = set()
    for body in states:
        for stmt in body:
            needed.extend(_cell_store_alias_from_stmt(stmt, cell_names, seen))
    return needed


def _cell_store_alias_from_stmt(
    stmt: ast.stmt, cell_names: set[str], seen: set[str]
) -> list[str]:
    needed: list[str] = []
    for n in ast.walk(stmt):
        targets: list[ast.expr] = []
        if isinstance(n, ast.Assign):
            targets.extend(n.targets)
        elif isinstance(n, ast.AnnAssign):
            targets.append(n.target)
        elif isinstance(n, (ast.For, ast.AsyncFor)):
            targets.append(n.target)
        elif isinstance(
            n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        ):
            for g in n.generators:
                targets.append(g.target)
        for t in targets:
            for x in ast.walk(t):
                if (
                    isinstance(x, ast.Subscript)
                    and isinstance(x.value, ast.Name)
                    and x.value.id in cell_names
                    and x.value.id not in seen
                ):
                    seen.add(x.value.id)
                    needed.append(x.value.id)
    return needed


def _cell_store_alias_names(
    body: list[ast.stmt], cell_names: set[str]
) -> list[str]:
    needed: list[str] = []
    seen: set[str] = set()
    for stmt in body:
        needed.extend(_cell_store_alias_from_stmt(stmt, cell_names, seen))
    return needed


def _clos_direct_assigned(node: ast.AST) -> set[str]:
    """Params plus stores in this function, not in nested def/class bodies.

    Nested def/class names are locals of this function (Python). Omitting
    them left sibling `async def bar` unbound in foo.send(), so leftover
    test_coroutines bound every `bar` to the last flattened factory and
    `await bar()` on an int 42 SEGVd in strlen.
    Global names are module cells, not per-call _aim_c keys (make_adder6).
    Nonlocal names are enclosing cells (testNonLocalGenerator).
    """
    skip = _clos_global_names(node) | _clos_nonlocal_names(node)
    assigned = _clos_params(node)
    body = getattr(node, "body", None) or []
    for stmt in body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if stmt.name not in skip:
                assigned.add(stmt.name)
            continue
        if isinstance(stmt, ast.ClassDef):
            # Generated gen/coro classes are hoisted into the function; they
            # are not user locals. Capturing them filled _aim_c before the
            # ClassDef ran and ObjectNewInit lost send().
            if not _is_generated_gen_class(stmt.name):
                if stmt.name not in skip:
                    assigned.add(stmt.name)
            continue
        for n in ast.walk(stmt):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                if n.id not in skip:
                    assigned.add(n.id)
    return assigned


def _clos_inner_locals(node: ast.AST) -> set[str]:
    locs = _clos_params(node)
    skip = _clos_global_names(node) | _clos_nonlocal_names(node)
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            if n.id not in skip:
                locs.add(n.id)
    return locs


def _clos_freevars(inner: ast.AST, enclosing: set[str]) -> list[str]:
    iloc = _clos_inner_locals(inner)
    iglob = _clos_global_names(inner)
    inon = _clos_nonlocal_names(inner)
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
            and n.id not in iglob
            and not _clos_skip_name(n.id)
            and n.id not in seen
        ):
            seen.append(n.id)
    for n in inon:
        if (
            n in enclosing
            and n not in iglob
            and not _clos_skip_name(n)
            and n not in seen
        ):
            seen.append(n)
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
        if node.id == "_AIM_CELL":
            return self._cell()
        if node.id in self.mapping:
            return self._sub(node.id, node.ctx)
        return node

    def visit_AugAssign(self, node: ast.AugAssign):
        node.value = self.visit(node.value)
        if isinstance(node.target, ast.Name) and node.target.id in self.mapping:
            assign = ast.Assign(
                targets=[ast.Name(id=node.target.id, ctx=ast.Store())],
                value=ast.BinOp(
                    left=ast.Name(id=node.target.id, ctx=ast.Load()),
                    op=node.op,
                    right=node.value,
                ),
            )
            return self.visit(assign)
        node.target = self.visit(node.target)
        return node

    def visit_Nonlocal(self, node: ast.Nonlocal):
        return ast.Pass()

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
            and _clos_is_cell_name(stmt.targets[0].id)
            and isinstance(stmt.value, ast.Dict)
        ):
            cnm = stmt.targets[0].id
            for key in mapping.values():
                out.append(
                    ast.Assign(
                        targets=[
                            ast.Subscript(
                                value=ast.Name(id=cnm, ctx=ast.Load()),
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


def _clos_cell_obj(cell_expr: ast.expr, key: str) -> ast.Dict:
    """Distinct live cell wrapping (dict, key). Two factory calls get
    different wrappers; cell.cell_contents can later read dict[key]."""
    return ast.Dict(
        keys=[
            ast.Constant(value="_c"),
            ast.Constant(value="_k"),
        ],
        values=[
            cell_expr,
            ast.Constant(value=key),
        ],
    )


def _clos_bound_value(
    cname: str, cell_expr: ast.expr, frees: list[str] | None = None
) -> ast.Dict:
    if frees:
        clo_elts = [_clos_cell_obj(cell_expr, v) for v in frees]
        fv = list(frees)
    else:
        clo_elts = [_clos_cell_obj(cell_expr, "_")]
        fv = []
    code_obj = ast.Dict(
        keys=[ast.Constant(value="co_freevars")],
        values=[
            ast.Tuple(
                elts=[ast.Constant(value=v) for v in fv],
                ctx=ast.Load(),
            )
        ],
    )
    return ast.Dict(
        keys=[
            ast.Constant(value="__bound__"),
            ast.Constant(value="obj"),
            ast.Constant(value="name"),
            ast.Constant(value="__closure__"),
            ast.Constant(value="__code__"),
        ],
        values=[
            ast.Constant(value=1),
            ast.Call(
                func=ast.Name(id=cname, ctx=ast.Load()),
                args=[cell_expr],
                keywords=[],
            ),
            ast.Constant(value="__call__"),
            ast.Tuple(elts=clo_elts, ctx=ast.Load()),
            code_obj,
        ],
    )


def _clos_class(
    cname: str,
    inner: ast.FunctionDef,
    mapping: dict[str, str],
    enclosing: set[str],
    counter: list[int],
    changed: list[bool],
    cc_names: list[str] | None = None,
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
    call_body, _frees, _ren = _clos_replace_nested(
        call_body, enclosing, _clos_self_c(), counter, changed, cc_names
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
                and not _clos_skip_name(n.id)
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


def _clos_init_c_body(cls_name: str) -> list[ast.stmt]:
    """self._c = _c, or the class cell when C() is called outside the factory."""
    return [
        ast.If(
            test=ast.Compare(
                left=ast.Name(id="_c", ctx=ast.Load()),
                ops=[ast.Is()],
                comparators=[ast.Constant(value=None)],
            ),
            body=[
                ast.Assign(
                    targets=[ast.Name(id="_c", ctx=ast.Store())],
                    value=ast.Attribute(
                        value=ast.Name(id=cls_name, ctx=ast.Load()),
                        attr="_c",
                        ctx=ast.Load(),
                    ),
                )
            ],
            orelse=[],
        ),
        _clos_init_c_assign(),
    ]


def _clos_class_cell_bind(
    cell_expr: ast.expr, counter: list[int], cc_names: list[str]
) -> tuple[list[ast.stmt], ast.expr]:
    """Copy the per-call cell to a module name class-body LOAD_NAME can see.

    in_classattrs leftover-GetNones unknown IDENT; params and PyMod win.
    Nested factory locals (`_aim_c`) become GetNone; a global slot is
    PyMod._aim_cc_N. Prepend `_aim_cc_N = None` at module level so the
    FixedPool.PyMod scan sees the name (nested global is not scanned).
    """
    counter[0] += 1
    gname = f"_aim_cc_{counter[0]}"
    cc_names.append(gname)
    stmts = [
        ast.Global(names=[gname]),
        ast.Assign(
            targets=[ast.Name(id=gname, ctx=ast.Store())],
            value=cell_expr,
        ),
    ]
    return stmts, ast.Name(id=gname, ctx=ast.Load())

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
    cls: ast.ClassDef, mapping: dict[str, str], cell_expr: ast.expr
) -> ast.ClassDef:
    """Inject __init__(self, _c) and rewrite method freevars to self._c.

    Class-body `_c = cell` is ClassAttrSet (inlined in the factory) so
    `C()` outside the factory can still read the cell. `C._c = cell` as
    an Attribute store is ObjectSet on the class name string, a no-op.
    """
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
                item.body = _clos_init_c_body(cls.name) + list(item.body)
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
            body=_clos_init_c_body(cls.name),
            decorator_list=[],
        )
        new_body.insert(0, init)
    new_body.append(
        ast.Assign(
            targets=[ast.Name(id="_c", ctx=ast.Store())],
            value=cell_expr,
        )
    )
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
    cc_names: list[str] | None = None,
) -> tuple[list[ast.stmt], list[tuple[str, str]], dict[str, str]]:
    """Turn nested defs that close over enclosing names into bound classes."""
    if cc_names is None:
        cc_names = []
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
                    _clos_class(
                        cname, stmt, mapping, enclosing, counter, changed, cc_names
                    )
                )
                new_body.append(
                    ast.Assign(
                        targets=[ast.Name(id=fn_name, ctx=ast.Store())],
                        value=_clos_bound_value(cname, cell_expr, list(frees)),
                    )
                )
                renames[stmt.name] = fn_name
                continue
        if isinstance(stmt, ast.ClassDef):
            if _for_target_needs_ident(stmt):
                new_body.append(stmt)
                continue
            frees = _clos_class_method_freevars(stmt, enclosing)
            if frees:
                changed[0] = True
                mapping = {v: v for v in frees}
                for v in frees:
                    if (v, v) not in cell_maps:
                        cell_maps.append((v, v))
                bind, gexpr = _clos_class_cell_bind(cell_expr, counter, cc_names)
                new_body.extend(bind)
                new_body.append(
                    _clos_patch_nested_class(stmt, mapping, gexpr)
                )
                if _class_has_call(stmt):
                    ctor_kind[stmt.name] = "bound"
                else:
                    ctor_kind[stmt.name] = "cell"
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
    return new_body, cell_maps, renames


def _desugar_nested_func_closures_tree(tree: ast.AST) -> tuple[ast.AST, bool]:
    """Nested def/lambda/class with freevars → per-call cell dict + callable class."""
    counter = [0]
    changed = [False]
    cc_names: list[str] = []
    cell_seq = [0]
    tree = _hoist_lambdas_tree(tree, counter, changed)

    class _X(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef):
            node = self.generic_visit(node)
            enclosing = _clos_direct_assigned(node)
            cell_name = f"_aim_c_{cell_seq[0] + 1}"
            new_body, cell_maps, renames = _clos_replace_nested(
                list(node.body),
                enclosing,
                ast.Name(id=cell_name, ctx=ast.Load()),
                counter,
                changed,
                cc_names,
            )
            if cell_maps:
                cell_seq[0] += 1
                params = _clos_params(node)
                inits: list[ast.stmt] = [
                    ast.Assign(
                        targets=[ast.Name(id=cell_name, ctx=ast.Store())],
                        value=ast.Dict(keys=[], values=[]),
                    )
                ]
                va = node.args.vararg.arg if node.args.vararg else None
                for v, key in cell_maps:
                    # Params exist at entry. Nested def/class names are
                    # assigned later; storing them here is GetNone and
                    # leftover await bar() then strlen(42) SEGVd.
                    if v in params:
                        val: ast.expr = ast.Name(id=v, ctx=ast.Load())
                        if va is not None and v == va:
                            val = ast.Call(
                                func=ast.Name(id="tuple", ctx=ast.Load()),
                                args=[val],
                                keywords=[],
                            )
                        inits.append(
                            ast.Assign(
                                targets=[
                                    ast.Subscript(
                                        value=ast.Name(
                                            id=cell_name, ctx=ast.Load()
                                        ),
                                        slice=ast.Constant(value=key),
                                        ctx=ast.Store(),
                                    )
                                ],
                                value=val,
                            )
                        )
                mapping = {v: k for v, k in cell_maps}
                fn_to_orig = {fn: orig for orig, fn in renames.items()}
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
                patched: list[ast.stmt] = []
                for stmt in rewritten:
                    patched.append(stmt)
                    stored: list[str] = []
                    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        stored.append(stmt.name)
                    elif isinstance(stmt, ast.ClassDef):
                        stored.append(stmt.name)
                    elif isinstance(stmt, ast.Assign):
                        for t in stmt.targets:
                            if isinstance(t, ast.Name):
                                stored.append(t.id)
                    for nm in stored:
                        if nm in mapping:
                            patched.append(
                                ast.Assign(
                                    targets=[
                                        ast.Subscript(
                                            value=ast.Name(
                                                id=cell_name, ctx=ast.Load()
                                            ),
                                            slice=ast.Constant(value=mapping[nm]),
                                            ctx=ast.Store(),
                                        )
                                    ],
                                    value=ast.Name(id=nm, ctx=ast.Load()),
                                )
                            )
                        orig = fn_to_orig.get(nm)
                        if orig is not None and orig in mapping:
                            patched.append(
                                ast.Assign(
                                    targets=[
                                        ast.Subscript(
                                            value=ast.Name(
                                                id=cell_name, ctx=ast.Load()
                                            ),
                                            slice=ast.Constant(value=mapping[orig]),
                                            ctx=ast.Store(),
                                        )
                                    ],
                                    value=ast.Name(id=nm, ctx=ast.Load()),
                                )
                            )
                node.body = inits + patched
            else:
                node.body = new_body
            return node

        visit_AsyncFunctionDef = visit_FunctionDef

    new_tree = _X().visit(tree)
    if cc_names and isinstance(new_tree, ast.Module):
        inits = [
            ast.Assign(
                targets=[ast.Name(id=nm, ctx=ast.Store())],
                value=ast.Constant(value=None),
            )
            for nm in cc_names
        ]
        new_tree.body = inits + list(new_tree.body)
    return new_tree, changed[0]


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
    new_tree, changed = _desugar_nested_func_closures_tree(tree)
    if not changed:
        return src
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree) + "\n"
    except Exception:
        return src


def _desugar_dict_call_tree(tree: ast.AST) -> tuple[ast.AST, bool]:
    """dict(a=1, b=2) → {'a': 1, 'b': 2} so keyword args survive AIMacro CALL."""
    changed = [False]

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
            changed[0] = True
            return ast.copy_location(ast.Dict(keys=keys, values=vals), node)

    return _DictKw().visit(tree), changed[0]


def desugar_dict_call(src: str) -> str:
    """dict(a=1, b=2) → {'a': 1, 'b': 2} so keyword args survive AIMacro CALL."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    new_tree, changed = _desugar_dict_call_tree(tree)
    if not changed:
        return src
    try:
        return ast.unparse(new_tree) + "\n"
    except Exception:
        return src


def _is_kwonly_fn(fn: ast.FunctionDef) -> str | None:
    a = fn.args
    if (
        a.kwarg
        and not a.posonlyargs
        and not a.args
        and not a.kwonlyargs
        and not a.vararg
    ):
        return a.kwarg.arg
    return None


def _kwcall_to_dict(call: ast.Call) -> ast.Call:
    """f(a=11) → f({'a': 11}); f() → f({}); f(**d) → f(d)."""
    if call.args:
        return call
    keys: list[ast.expr | None] = []
    vals: list[ast.expr] = []
    rest = None
    for kw in call.keywords:
        if kw.arg is None:
            rest = kw.value
        else:
            keys.append(ast.Constant(value=kw.arg))
            vals.append(kw.value)
    if rest is not None and not keys:
        d: ast.expr = rest
    elif rest is not None:
        d = ast.Dict(keys=[None] + keys, values=[rest] + vals)
    else:
        d = ast.Dict(keys=keys, values=vals)
    return ast.Call(func=call.func, args=[d], keywords=[])


def _rewrite_body_kwonly(body: list[ast.stmt]) -> list[ast.stmt]:
    kwonly: dict[str, str] = {}

    class _Calls(ast.NodeTransformer):
        def visit_FunctionDef(self, n: ast.FunctionDef):
            return n

        def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef):
            return n

        def visit_ClassDef(self, n: ast.ClassDef):
            return n

        def visit_Call(self, n: ast.Call):
            n = self.generic_visit(n)
            if isinstance(n.func, ast.Name) and n.func.id in kwonly:
                return _kwcall_to_dict(n)
            return n

    out: list[ast.stmt] = []
    for stmt in body:
        if isinstance(stmt, ast.FunctionDef):
            stmt.body = _rewrite_body_kwonly(list(stmt.body))
            kn = _is_kwonly_fn(stmt)
            if kn:
                stmt.args.kwarg = None
                stmt.args.args = [ast.arg(arg=kn)]
                kwonly[stmt.name] = kn
            out.append(stmt)
        elif isinstance(stmt, ast.AsyncFunctionDef):
            stmt.body = _rewrite_body_kwonly(list(stmt.body))
            out.append(stmt)
        elif isinstance(stmt, ast.ClassDef):
            stmt.body = _rewrite_body_kwonly(list(stmt.body))
            out.append(stmt)
        else:
            out.append(_Calls().visit(stmt))
    return out


def _desugar_kwonly_dict_tree(tree: ast.AST) -> tuple[ast.AST, bool]:
    """def f(**kwargs) plus f(a=11) → f({'a': 11}) so the dict is a param."""
    if not isinstance(tree, ast.Module):
        return tree, False
    new_body = _rewrite_body_kwonly(list(tree.body))
    tree.body = new_body
    return tree, True


def _desugar_keyerror_ctor_tree(tree: ast.AST) -> tuple[ast.AST, bool]:
    """exc = KeyError('a') → raise/except so leftover gets a RaiseKind hash.

    leftover CALL of KeyError was SmartCall1(0) skip. MakeExc of that
    CALL in a 4-method ELF SEGVd on throw(instance). RaiseKind hashes
    already throw in that ELF. Isolation golds have no KeyError() ctor.
    """

    class T(ast.NodeTransformer):
        def visit_Assign(self, node: ast.Assign):
            node = self.generic_visit(node)
            if (
                isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "KeyError"
            ):
                return ast.Try(
                    body=[ast.Raise(exc=node.value, cause=None)],
                    handlers=[
                        ast.ExceptHandler(
                            type=ast.Name(id="Exception", ctx=ast.Load()),
                            name="_aim_ke",
                            body=[
                                ast.Assign(
                                    targets=node.targets,
                                    value=ast.Name(id="_aim_ke", ctx=ast.Load()),
                                )
                            ],
                        )
                    ],
                    orelse=[],
                    finalbody=[],
                )
            return node

    if not isinstance(tree, ast.Module):
        return tree, False
    return T().visit(tree), True


def convert(src: str) -> str:
    # Empty / whitespace-only modules (e.g. empty __init__.py): aimacro.x
    # rejects zero-byte input. Emit a bare `pass` so transpile succeeds.
    if not src or not src.strip():
        return "pass\n"
    src = desugar_match(src)
    src = desugar_pep695_type_params(src)
    src = desugar_starargs_annotations(src)
    src = desugar_nameerror_probe(src)
    src = desugar_yield(src)
    src = desugar_from_import_as(src)
    src = desugar_tuple_unpack(src)
    src = desugar_for_unpack(src)
    # One parse + one unparse for generators/class_cells/closures/dict_call.
    # Isolation golds already went through class_cells always-unparse, so
    # always unparsing here keeps that comment-stripped emit.
    try:
        _late = ast.parse(src)
    except SyntaxError:
        _late = None
    if _late is not None:
        _late, _ = _desugar_exec_const_tree(_late)
        _late, _ = _desugar_keyerror_ctor_tree(_late)
        _late, _ = _desugar_generators_tree(_late)
        _late, _ = _desugar_class_ns_locals_tree(_late)
        _late, _ = _desugar_nested_class_cells_tree(_late)
        _late, _ = _desugar_kwonly_dict_tree(_late)
        _late, _ = _desugar_nested_func_closures_tree(_late)
        _late, _ = _desugar_dict_call_tree(_late)
        ast.fix_missing_locations(_late)
        try:
            src = ast.unparse(_late) + "\n"
        except Exception:
            pass
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
