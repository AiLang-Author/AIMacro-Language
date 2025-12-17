# AIMacro

**A compiled language stack for people who are done with Python's whitespace bullshit.**

## What Is This?

- **AILang** - A low-level compiled language that generates native x86-64 Linux executables https://github.com/AiLang-Author/AiLang
- **AIMacro** - A Python-like language that transpiles to AILang

Write code that reads like Python, compiles to native binaries, and never breaks because someone's editor converted tabs to spaces.

## Quick Start

```bash
# Compile AILang directly
python main.py myprogram.ailang

# Or use the AIMacro transpiler
./aimacro_console_exec
aim> load myprogram.aim
aim> save myprogram.ailang
aim> quit
python main.py myprogram.ailang
```

## AIMacro Example

```python
# factorial.aim
def factorial(n):
    if n <= 1:
        return 1
    end
    return n * factorial(n - 1)
end

def main():
    print("10! =", factorial(10))
end
```

Transpiles to clean AILang:

```ailang
Function.factorial {
    Input: p_n: Integer
    Output: Integer
    Body: {
        IfCondition LessEqual(p_n, 1) ThenBlock: {
            ReturnValue(1)
        }
        t0 = factorial(Subtract(p_n, 1))
        ReturnValue(Multiply(p_n, t0))
    }
}
```

## Supported Python Features

### Working Now ✅
- Functions with parameters and return values
- `if`/`elif`/`else` conditionals
- `while` loops with `break`/`continue`
- `for x in range()` loops (optimized)
- Lists: `[1, 2, 3]`, indexing, `.append()`, `.pop()`
- Operators: `+ - * / % **`, comparisons, `and`/`or`/`not`
- Augmented assignment: `+=`, `-=`, `*=`, `/=`
- Built-ins: `print()`, `len()`, `range()`, `abs()`, `max()`, `min()`, `sum()`, `str()`, `int()`, `input()`
- String methods: `.upper()`, `.lower()`, `.split()`, `.find()`
- Recursive functions
- Nested expressions with automatic temp variable extraction

### Not Yet Implemented
- String concatenation (`"hello" + "world"`)
- `in` operator (`if x in list`)
- Negative indexing (`arr[-1]`)
- Slicing (`arr[1:3]`)
- Lambda expressions
- List comprehensions
- Default arguments
- Classes/objects
- Exceptions

## Why?

**Python's problems:**
- Invisible whitespace bugs that waste hours
- Tabs vs spaces holy wars
- Copy-paste destroys indentation
- No compilation = runtime surprises

**Our solutions:**
- Explicit `end` block markers
- Compiles to native code - catch errors early
- No interpreter overhead
- Direct access to system calls when needed

## Architecture

```
AIMacro (.aim)
    ↓ transpiler (written in AILang, self-hosted)
AILang (.ailang)
    ↓ compiler (Python, generates x86-64)
Native Linux Executable
```

The AIMacro transpiler is itself written in AILang and compiles to a native executable. Bootstrapping in progress.

## Project Structure

```
ailang/
├── main.py                 # Main compiler entry point
├── ailang_compiler/        # AILang → x86-64 compiler
├── aimacro/               
│   ├── Library.AIMacroCore.ailang      # Lexer
│   ├── Library.AIMacroParserCore.ailang # Parser  
│   ├── Library.AIMacroCodeGen.ailang   # Code generator
│   └── aimacro_console.ailang          # Interactive console
├── libraries/
│   ├── Library.XArrays.ailang          # Dynamic arrays
│   ├── Library.XSHash.ailang           # Hash tables
│   └── Library.AIMacro.ailang          # Python built-in implementations
└── tests/
```

## Building

```bash
# Requirements: Python 3.8+, Linux x86-64

# Compile the AIMacro console
python main.py aimacro/aimacro_console.ailang

# Run it
./aimacro_console_exec
```

## Status

**Working:**
- AILang compiler generates functioning executables
- AIMacro transpiler handles core Python subset
- Self-hosted transpiler console operational
- Complex recursive algorithms compile and run correctly

**In Progress:**
- String operations
- More Python built-ins
- Error messages that don't suck

## License

MIT

---

*AIMacro: Because life's too short to debug whitespace.*
