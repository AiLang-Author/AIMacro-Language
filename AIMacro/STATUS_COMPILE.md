# AIMacro overnight compile — STATUS (2026-09-25 stretch)

**Branch:** `grokasaurus2`
**widen compile 52/76 probed** (was 47 → **52** with pprint max_width chain-assign + list.reverse MapMethod + SLICE flatten)

## This stretch
- cg2_encode + cg4_encmap micros on origin (join md5 OK); Extra tip micros on origin (join e65c4246 OK)
- Extra Library tip assembled on origin (md5 e65c4246) after PLACEHOLDER FIX; extra_tip micros 000-003 + OOP oop_chain 000-020 join OK
- Local tip fixes (host rebuilt; Hash 922):
  - OOP `OOPGen_Assign` → `Gen_ResolveChainValue` (pprint `max_width`) — OOP md5 `7646560a…`; micros oop_chain 000-020 on origin, join OK
  - `AIMacro.ListReverse` + MapMethod `reverse` (gettext first fail → now `Variable not found: op`)
  - `Gen_SliceAccess`/`Gen_FlattenExpr` SLICE flatten-before-emit (reprlib Expected ')' SIGSEGV → **COMPILE_OK**)
- widen gained: pprint, reprlib, random, mailbox, netrc (no losses vs prior 47)

## Tip md5s (local/host — not all assembled on origin yet)
| file | md5 |
|------|-----|
| Extra | `e65c424621b959db2288b26074d67eb9` (on origin) |
| CodeGen1 | `37d1791141b42600d87525d8e8b97560` |
| CodeGen2 | `511122ee6615b9fec9879b355272147c` (slice flatten) |
| CodeGen3 | `9672189e8337e821bfe33bbe65563962` (SLICE FlattenExpr) |
| CodeGen4 | `91254a26b134602608a782d5feccae89` (reverse MapMethod) |
| AIMacro.ailang | `c15326296d8dbdc13a246b0dc531a1c1` (ListReverse) |
| CodeGenOOP | `7646560a2d6c536e4c05b33ea6be877e` (chain assign) |

## leftovers
import-stubs; typing/ast/turtle/configparser aimacro fails; gettext `op`; gzip/locale Expected ')' remnants; module-level consts; Library tip assemble (cg1/cg2/cg4/rt) onto origin; climb cg2_slice/cg3_slice/cg4_reverse/rt_listreverse micros then assemble OOP+cg2/3/4/rt

## Tests added
- `AIMacro_Tests/compile_chain_assign_max_width.aim`
- `AIMacro_Tests/compile_list_reverse.aim`
- `AIMacro_Tests/compile_slice_join_star.aim`

## Gates
- Hash 922
- fizzbuzz ELF ~215166 (pre-existing tip drift vs doc 211054)
- curated: re-run if needed after origin assemble

widen detail: ok=52 fail=24
