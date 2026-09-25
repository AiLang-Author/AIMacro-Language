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
| compile_h_append_bound | `AIMacro_Tests/compile_h_append_bound.aim` → `2` | `h_append=h.append` → AddressOf(SmartPush)+bound self; calls → SmartPush(h,x) |

Gates (host): curated **25/25**, matrix **73/73/73**, fizzbuzz **215153** (new baseline; do not chase 211054), Hash **922**.

## Origin zlib (tip after compile_h_append_bound)
- **MILESTONE lib:** origin micros assemble → md5 `7f9326010e9ba34e211024dbf5c31cab` MATCH
- **cg4:** origin parts assemble → md5 `7731c93bd2f50fd22562ccf3a0fec51d` MATCH
- **cg2:** origin assemble MATCH `a70d70a494ba869a493ecda2d9534342` (then h_append_bound on tip)
- **oop:** origin assemble MATCH `14f0e4b130cfe1f9edba55f4f87fed04`
- Note: tip CodeGen1/2/4 diverge from zlib micros (bound-append); regenerate micros before next assemble

## Ladder
1. ~~map~~ 2. ~~iter~~ 3. ~~next~~ 4. ~~h_append_bound~~
5. Next leftover: pick smallest transpile-ok compile-fail from lib probe (prefer named missing symbol / short SIGSEGV parse).

Self-Hosting: not pushed.
