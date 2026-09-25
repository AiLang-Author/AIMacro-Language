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

Gates (host): curated **25/25**, matrix **72/72/72**, fizzbuzz **215153** (was 211054; grew with Map/Iter/Next linked into AIMacro), Hash **922**.
Probe colorsys+keyword+quopri **3/3** (via py2aim→aimacro→ailang).

## Origin publish
- zlib staging in progress: lib.z.b64.02.0-9 micros on origin OK; remaining lib/cg4/cg2/oop parts + manifest pending MCP.
- md5: lib=`7f9326010e9ba34e211024dbf5c31cab` cg4=`7731c93bd2f50fd22562ccf3a0fec51d` cg2=`a70d70a494ba869a493ecda2d9534342` oop=`14f0e4b130cfe1f9edba55f4f87fed04`

## Ladder
1. ~~map~~ 2. ~~iter~~ 3. ~~next~~
4. **NEXT leftover:** heapq still has later parse/compile fails after next (bound-method path compiles on tiny repro)

Self-Hosting: not pushed.
