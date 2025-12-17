# AIMacro Language

**For Python developers who want to retire with a full head of hair.**

## What is AIMacro?

AIMacro is a Python-compatible macro language that compiles to AILang assembly. It gives you Python's readability without the whitespace nightmares, clear block delimiters, and escape hatches to lower-level code when you need performance.

## Language Specification v3.2

### Core Syntax

```aimacro
# Functions with explicit end markers - no indentation errors!
def calculate(x, y):
    result = x + y;
    print(result);
    return result;
end;

# Or use 'func' for AIMacro native style
func main():
    values = range(10);
    total = 0;
    
    for val in values:
        total = total + val;
    end;
    
    return total;
end;
```

### Key Features

**No Whitespace Sensitivity**
- Blocks open with `:` and close with `end;`
- Semicolons terminate statements (optional but recommended)
- Mix tabs and spaces without breaking your code

**Python Compatibility**
- Use `def`/`pass` or `func`/`end`
- Built-in functions work as expected: `print()`, `len()`, `range()`, `str()`, `int()`
- Gradual migration path from Python

**Escape Hatches**
```aimacro
func optimize():
    # Drop to AILang for performance
    ailang {
        WhileLoop LessThan(i, 1000000) {
            ArraySet(buffer, i, 0)
            i = Add(i, 1)
        }
    };
    
    # Direct assembly when needed
    asm {
        MOV RAX, 60
        XOR RDI, RDI
        SYSCALL
    };
end;
```

### Parser Implementation

The AIMacro parser (v3.2) is written in pure AILang and includes:
- Python-style function call parsing
- Automatic built-in function translation
- AILANG and assembly escape blocks
- Clear error boundaries (no cascading indentation failures)

### Quick Start

```bash
# Compile AIMacro to AILang
./aimacro_parser your_code.aimacro > output.ailang

# Then compile AILang to executable
./ailang_compiler output.ailang
```

### Why AIMacro?

**Python's Problems:**
- Invisible whitespace bugs
- Tabs vs spaces holy wars  
- Copy-paste destroys indentation
- Silent scope errors

**AIMacro's Solutions:**
- Explicit `end;` markers
- Clear visual blocks
- Whitespace is just whitespace
- Compile-time scope validation

### Syntax Comparison

| Python | AIMacro | Benefit |
|--------|---------|---------|
| Invisible indentation | `:` and `end;` | Visual block boundaries |
| `def func():` | `def func():` or `func name():` | Compatible or cleaner |
| Whitespace sensitive | Semicolon terminated | No silent errors |
| No escape hatch | `ailang { }` blocks | Performance when needed |

# AIMacro Python Feature Checklist

## CONTROL FLOW

| Feature | Parser | CodeGen | Runtime | Notes |
|---------|--------|---------|---------|-------|
| `if/elif/else` | ✅ | ✅ | ✅ | Working |
| `while` | ✅ | ✅ | ✅ | Working |
| `for x in range()` | ✅ | ✅ | ✅ | Optimized to WhileLoop |
| `for x in list` | ✅ | ⚠️ | ❌ | Emits ForEvery, needs runtime |
| `break` | ✅ | ✅ | ✅ | Working |
| `continue` | ✅ | ✅ | ✅ | Working |
| `pass` | ✅ | ❌ | - | Need to emit nothing/comment |

## FUNCTIONS

| Feature | Parser | CodeGen | Runtime | Notes |
|---------|--------|---------|---------|-------|
| `def func():` | ✅ | ✅ | ✅ | Working |
| `def func(a, b):` | ✅ | ✅ | ✅ | Working |
| `return value` | ✅ | ✅ | ✅ | Working |
| `return` (no value) | ✅ | ✅ | ✅ | Returns 0 |
| Type hints `def f(x: int) -> int:` | ✅ | ⚠️ | - | Parsed, ignored |
| Default args `def f(x=5):` | ❌ | ❌ | - | **MISSING** |
| `*args` | ❌ | ❌ | - | Not planned |
| `**kwargs` | ❌ | ❌ | - | Not planned |
| Lambda `lambda x: x+1` | ❌ | ❌ | - | **MISSING** - useful |
| Nested functions | ❌ | ❌ | - | Complex, skip for now |

## OPERATORS

| Feature | Parser | CodeGen | Runtime | Notes |
|---------|--------|---------|---------|-------|
| `+ - * / %` | ✅ | ✅ | ✅ | Working |
| `//` floor div | ✅ | ⚠️ | ❌ | Parser has it, needs codegen |
| `**` power | ✅ | ✅ | ✅ | Working |
| `== != < > <= >=` | ✅ | ✅ | ✅ | Working |
| `and or not` | ✅ | ✅ | ✅ | Working |
| `in` (membership) | ❌ | ❌ | ❌ | **MISSING** - `x in list` |
| `is` (identity) | ⚠️ | ❌ | - | Parsed, not implemented |
| Unary `-` | ✅ | ✅ | ✅ | `Subtract(0, x)` |
| `+=  -=  *=  /=` | ✅ | ✅ | ✅ | Working |

## DATA STRUCTURES

| Feature | Parser | CodeGen | Runtime | Notes |
|---------|--------|---------|---------|-------|
| List literal `[1,2,3]` | ✅ | ✅ | ✅ | XArray.XCreate + XPush |
| Dict literal `{a:1}` | ✅ | ✅ | ⚠️ | XSHash, needs testing |
| Tuple `(1, 2)` | ❌ | ❌ | ⚠️ | **MISSING** parser |
| Index `a[i]` | ✅ | ✅ | ✅ | XArray.XGet |
| Index assign `a[i] = x` | ✅ | ✅ | ✅ | XArray.XSet |
| Slice `a[1:3]` | ❌ | ❌ | ❌ | **MISSING** - useful |
| Dict access `d[key]` | ❌ | ❌ | ⚠️ | Need to differentiate from list |
| Negative index `a[-1]` | ❌ | ❌ | ❌ | **MISSING** - useful |

## BUILT-IN FUNCTIONS

| Feature | Parser | CodeGen | Runtime | Notes |
|---------|--------|---------|---------|-------|
| `print()` | ✅ | ✅ | ✅ | Special-cased |
| `len()` | ✅ | ✅ | ✅ | AIMacro.Len |
| `range()` | ✅ | ✅ | ✅ | Optimized in for-loops |
| `str()` | ✅ | ✅ | ✅ | AIMacro.Str |
| `int()` | ✅ | ✅ | ✅ | AIMacro.Int |
| `abs()` | ✅ | ✅ | ✅ | AIMacro.Abs |
| `max()` | ✅ | ✅ | ✅ | AIMacro.Max (2 args only) |
| `min()` | ✅ | ✅ | ✅ | AIMacro.Min (2 args only) |
| `sum()` | ✅ | ✅ | ✅ | AIMacro.Sum |
| `input()` | ✅ | ✅ | ✅ | AIMacro.Input |
| `bool()` | ⚠️ | ⚠️ | ✅ | Exists but not mapped |
| `type()` | ❌ | ❌ | ❌ | **MISSING** |
| `isinstance()` | ❌ | ❌ | ❌ | Not planned (no types) |
| `sorted()` | ❌ | ❌ | ❌ | **MISSING** - useful |
| `reversed()` | ❌ | ❌ | ❌ | **MISSING** |
| `enumerate()` | ❌ | ❌ | ✅ | Runtime exists, need codegen |
| `zip()` | ❌ | ❌ | ✅ | Runtime exists, need codegen |
| `map()` | ❌ | ❌ | ❌ | Needs lambda first |
| `filter()` | ❌ | ❌ | ❌ | Needs lambda first |
| `any()` / `all()` | ❌ | ❌ | ❌ | **MISSING** - easy |
| `chr()` / `ord()` | ❌ | ❌ | ❌ | **MISSING** - easy |

## STRING METHODS

| Feature | Parser | CodeGen | Runtime | Notes |
|---------|--------|---------|---------|-------|
| `.upper()` | ✅ | ✅ | ✅ | Working |
| `.lower()` | ✅ | ✅ | ✅ | Working |
| `.split()` | ✅ | ✅ | ✅ | Working |
| `.find()` | ✅ | ✅ | ✅ | StringIndexOf |
| `.strip()` | ❌ | ❌ | ❌ | **MISSING** |
| `.replace()` | ❌ | ❌ | ❌ | **MISSING** |
| `.startswith()` | ❌ | ❌ | ❌ | **MISSING** |
| `.endswith()` | ❌ | ❌ | ❌ | **MISSING** |
| `.join()` | ❌ | ❌ | ❌ | **MISSING** |
| `f"string {var}"` | ❌ | ❌ | ❌ | **MISSING** - very useful |
| String concat `+` | ❌ | ❌ | ❌ | **MISSING** |

## LIST METHODS

| Feature | Parser | CodeGen | Runtime | Notes |
|---------|--------|---------|---------|-------|
| `.append()` | ✅ | ✅ | ✅ | XArray.XPush |
| `.pop()` | ✅ | ✅ | ✅ | XArray.XPop |
| `.insert()` | ⚠️ | ⚠️ | ⚠️ | Stub only |
| `.remove()` | ⚠️ | ⚠️ | ✅ | Runtime exists |
| `.index()` | ❌ | ❌ | ❌ | **MISSING** |
| `.count()` | ❌ | ❌ | ❌ | **MISSING** |
| `.sort()` | ❌ | ❌ | ❌ | **MISSING** |
| `.reverse()` | ❌ | ❌ | ❌ | **MISSING** |
| `.copy()` | ❌ | ❌ | ❌ | **MISSING** |
| `.clear()` | ❌ | ❌ | ❌ | **MISSING** |
| `.extend()` | ❌ | ❌ | ❌ | **MISSING** |

## MISSING BUT IMPORTANT

### High Priority (core Python feel)
1. **String concatenation** - `"hello" + " " + "world"`
2. **f-strings** - `f"Value is {x}"`
3. **`in` operator** - `if x in mylist:`
4. **Negative indexing** - `arr[-1]`
5. **Slicing** - `arr[1:3]`
6. **`any()` / `all()`** - trivial to add
7. **`chr()` / `ord()`** - trivial to add

### Medium Priority (nice to have)
1. **Lambda expressions** - `lambda x: x * 2`
2. **List comprehensions** - `[x*2 for x in range(10)]`
3. **Default arguments** - `def f(x=5):`
4. **`sorted()`** - return sorted copy
5. **String `.strip()`, `.replace()`, `.join()`**

### Low Priority (can skip)
1. Classes/objects
2. Exceptions (try/except)
3. Generators/yield
4. Decorators
5. Context managers (with)
6. Multiple assignment `a, b = 1, 2`

### Philosophy

AIMacro isn't trying to replace Python - it's trying to save it from itself. Keep Python's elegant syntax and extensive ecosystem, but fix the foundational mistakes that cause developers endless frustration.

Write code that reads like Python, compiles like C, and never breaks because someone's editor converted tabs to spaces.

---

*AIMacro: Because life's too short to debug whitespace.*
