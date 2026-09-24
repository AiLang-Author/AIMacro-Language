#!/usr/bin/env bash
# Restore CodeGen1 and apply compile tranche patches on grokasaurus2.
set -euo pipefail
cd "$(dirname "$0")/.."
git fetch origin grokasaurus2
git checkout grokasaurus2
git pull --ff-only origin grokasaurus2 || true
git checkout 65dd589 -- \
  Librarys/AIMacro/Library.AIMacroCodeGen1.ailang \
  Librarys/AIMacro/Library.AIMacroCodeGen2.ailang \
  Librarys/AIMacro/Library.AIMacroCodeGen4.ailang \
  Librarys/AIMacro/Library.AIMacro.ailang
patch -p1 < AIMacro/patches/compile_module_const_codegen1.patch
patch -p1 < AIMacro/patches/compile_module_const_codegen2.patch
patch -p1 < AIMacro/patches/compile_frozenset_codegen4.patch
patch -p1 < AIMacro/patches/compile_frozenset_runtime.patch
git add Librarys/AIMacro/Library.AIMacro*.ailang
git status -sb
echo "Review and: git commit && git push origin grokasaurus2"
