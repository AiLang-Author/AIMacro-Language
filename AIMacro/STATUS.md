# AIMacro overnight compile — STATUS (2026-09-25)

## Applied steering
- CONFORMANCE ONLY (no optimize/profile)
- One construct per commit
- Branch grokasaurus2 only; Self-Hosting never pushed

## Local (box) — green
| Construct | Repro | Notes |
|-----------|-------|-------|
| compile_map_builtin | `AIMacro_Tests/compile_map_builtin.aim` → `3` | Gen_MapBuiltin map→AIMacro.Map; CallIndirect |
| compile_iter_builtin | `AIMacro_Tests/compile_iter_builtin.aim` → `3`/`2` | iter→AIMacro.Iter; IDENT builtins AddressOf |
| compile_next_builtin | `AIMacro_Tests/compile_next_builtin.aim` → `10`/`20` | next→AIMacro.Next; `it.__next__` → CallIndirect |

Gates (host): curated **25/25**, matrix **72/72/72**, fizzbuzz **215153** (new baseline; do not chase 211054), Hash **922**.

## Origin zlib (tip ~011ef8e)
- **MILESTONE lib:** origin micros assemble → md5 `7f9326010e9ba34e211024dbf5c31cab` MATCH
- **cg4:** origin parts assemble → md5 `7731c93bd2f50fd22562ccf3a0fec51d` MATCH
- **cg2:** micros through `cg2.z.b64.06.0` on origin; remaining `06.1`–`08.2` + oop `00.0`–`04.3` (~66 micros)
- **oop:** not yet on origin
- Then push updated `manifest.json` (micro-split parts) → CI assemble workflow
- Targets: lib=`7f932601…` cg4=`7731c93b…` cg2=`a70d70a4…` oop=`14f0e4b1…`
- Inbox bulk: `/workspace/mcp_push_cg2_oop_remain.json` + `mcp-inbox/REQUEST_cg2_oop_remain.json`

## Ladder
1. ~~map~~ 2. ~~iter~~ 3. ~~next~~
4. **After assemble:** `h_append = h.append` → Unknown function: h_append. Repro: `AIMacro_Tests/compile_h_append_bound.aim`. Fix: MarkCallableVar for attr `"append"` (same path as `__next__`) in CodeGen2 + CodeGenOOP → CallIndirect.

Self-Hosting: not pushed.
