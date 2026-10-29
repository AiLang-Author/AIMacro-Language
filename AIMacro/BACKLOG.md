# AIMacro backlog

Score from the 2026-10-29 `--full` run. 568 files, **310 pass**, 258 fail, 2140 seconds. Database: `results/grind_db.json`. October 12 was 318 pass / 250 fail. This run gained 22 and lost 30. Compile failures went from 80 to 8.

Work one row at a time. Prove it with one small program that matches CPython, then the 59-file isolation set. Do not start a module just because a test file imports it. Speed stays parked.

## Now

1. **`0 - 2.0` is wrong** (`test_unary.py`, `UnaryOpTestCase.test_negative`). Literal `0` is a bigint. `NumAdd` handles a bigint before a float, so the float box is turned into a decimal pointer (`126342706233832`). Unary `-2.0` already prints `-2.0`. The next assert in that method is `0 - 2j`. LCD `/tmp/clos-lcd/neg1.py`.

## Regressions (were pass on October 12)

Take these after the float subtract, one file at a time. The symptom is the recorded tail, not a root cause.

| File | Stage | Tail |
|------|-------|------|
| `test_binop.py` | run rc=1 | 12 ran, 4 failed |
| `test_cmd_line_script.py` | run rc=1 | 44 ran, 1 failed |
| `test_compare.py` | run rc=1 | 13 ran, 2 failed |
| `test_contains.py` | run rc=1 | argument is not iterable |
| `test_contextlib.py` | run rc=1 | 31 ran, 8 failed |
| `test_ensurepip.py` | run rc=1 | Method not found: version |
| `test_eof.py` | run rc=1 | 3 ran, 2 failed |
| `test_generator_stop.py` | run rc=1 | 2 ran, 1 failed |
| `test_getopt.py` | run rc=1 | argument is not iterable |
| `test_importlib/import_/test_fromlist.py` | compile rc=1 | Variable not found: `PyMod.i_do_not_exist` |
| `test_importlib/test_threaded_import.py` | compile rc=1 | Variable not found: `PyMod.A` |
| `test_importlib/test_util.py` | run rc=1 | 3 ran, 1 failed |
| `test_iterlen.py` | run rc=1 | object is not iterable |
| `test_opcodes.py` | run rc=-11 | died in `OpcodeTest` |
| `test_openpty.py` | run rc=1 | 1 ran, 1 failed |
| `test_ordered_dict.py` | run rc=1 | Method not found: split |
| `test_pickle.py` | run rc=1 | not supported |
| `test_pipes.py` | run rc=1 | TypeError |
| `test_pkgutil.py` | run rc=1 | 4 ran, 2 failed |
| `test_pyclbr.py` | compile rc=1 | Variable not found: `compare` |
| `test_scope.py` | run rc=1 | 40 ran, 2 failed |
| `test_string.py` | run rc=1 | `test_override_format_field` |
| `test_syntax.py` | run rc=1 | line continuation / indented statement |
| `test_time.py` | run rc=1 | Exception: division by zero (aborts the file) |
| `test_typechecks.py` | run rc=1 | 5 ran, 2 failed |
| `test_unary.py` | run rc=1 | `test_negative` (row 1 above) |
| `test_userlist.py` | run rc=1 | 9 ran, 5 failed |
| `test_utf8source.py` | run rc=1 | 3 ran, 3 failed |
| `test_uu.py` | run rc=1 | TypeError |
| `test_with.py` | run rc=1 | 5 ran, 2 failed |

## Compile (8)

| File | What the compiler said |
|------|------------------------|
| `test_asyncio/test_tasks.py` | Variable not found: `PyMod._asyncio` |
| `test_buffer.py` | Variable not found: `os` |
| `test_compile.py` | Variable not found: `PyMod.__mangled_mod` |
| `test_hash.py` | parse: Expected ')' after arguments (rc=-11) |
| `test_import/__init__.py` | parse: Unexpected token in statement (rc=-11) |
| `test_importlib/import_/test_fromlist.py` | Variable not found: `PyMod.i_do_not_exist` |
| `test_importlib/test_threaded_import.py` | Variable not found: `PyMod.A` |
| `test_pyclbr.py` | Variable not found: `compare` |

## Transpile (8)

`py2aim` did not accept the file. `test_unicode_identifiers.py` is parked (below). The others failed inside a class body: `test_bdb.py`, `test_coroutines.py`, `test_hashlib.py`, `test_math.py`, `test_tarfile.py`, `test_traceback.py`, `test_xmlrpc.py`.

## Failure piles

These are counts, not one bug each.

| Count | Kind |
|------:|------|
| 128 | run rc=1 |
| 62 | run crash (rc=-11) |
| 35 | run, no tests ran |
| 14 | timeout (rc=124), including `test_bigmem.py`, `test___all__.py`, `test_lzma.py`, `test_frame.py` |
| 13 | `Exception: No such file` (`test_io`, `test_posix`, `test_ntpath`, `test_filecmp`, …) |
| 11 | TestCase scheduled but 0 tests ran (mostly the parked codec files) |
| 10 | `Exception: TypeError` |
| 8 | empty `Exception:` (windows, audit, devpoll, kqueue, launcher) |
| 4 | index out of range (`ftplib`, `genericalias`, `poplib`, `smtplib`) |

## Gained since October 12

`test__locale.py`, `test_asyncio/test_buffered_proto.py`, `test_asyncio/test_sslproto.py`, `test_asyncio/test_taskgroups.py`, `test_bigaddrspace.py`, `test_cmd_line.py`, `test_compileall.py`, `test_epoll.py`, `test_importlib/test_main.py`, `test_int_literal.py`, `test_json/test_dump.py`, `test_marshal.py`, `test_peepholer.py`, `test_reprlib.py`, `test_runpy.py`, `test_smtpd.py`, `test_sqlite3/test_types.py`, `test_textwrap.py`, `test_threadsignals.py`, `test_tools/test_pathfix.py`, `test_urllibnet.py`, `test_wsgiref.py`.

A passing file means the ELF exited 0 after tests ran. It does not mean the module is finished. `test_wsgiref.py` passes and still does not build the hello HTTP body. `test_tools/test_pathfix.py` passes and still does not rewrite a shebang.

## Parked

Do not harvest these. Fifteen language files: `test_codecencodings_cn.py`, `test_codecencodings_hk.py`, `test_codecencodings_jp.py`, `test_codecencodings_kr.py`, `test_codecencodings_tw.py`, `test_codecmaps_cn.py`, `test_codecmaps_hk.py`, `test_codecmaps_jp.py`, `test_codecmaps_kr.py`, `test_codecmaps_tw.py`, `test_locale.py`, `test__locale.py`, `test_gettext.py`, `test_unicode_identifiers.py`, `test_unicode_file_functions.py`.

`test__locale.py` is in the gained list and also stays parked as a locale file. Do not open it to chase locale behavior.

Do not start `optparse`, `urllib`, `wsgiref`, `reprlib`, `site`, or `warnings` as an import goal. Do not chase dict or set print order. Do not build a doctest runner. `test_codecs.py` and `test_unicode.py` stay active.

## Still open, not this queue

`sys.maxsize ** 2` prints 0. BytesIO, memoryview, `func.__code__`, float format, percent format, `chr` above 255, and two-arg `str` on bytes are still wrong. Imports do not walk `sys.path`. Ints between the loaded image (about 5 MB) and 16 MB can still be read as pointers.
