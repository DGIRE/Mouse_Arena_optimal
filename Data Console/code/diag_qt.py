#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diag_qt.py -- pinpoint the PySide6 / Qt6 DLL load failure on this machine.

Run with the vras interpreter:
  "C:\\Projects\\Repos\\Agentic Research\\Research Setup\\vras\\Scripts\\python.exe" diag_qt.py

Reports: which C++ runtime Python already loaded (and from where), then tries to
load PySide6's runtime + Qt6 DLLs one by one and shows the FIRST that fails.
"""
import ctypes
import os
import sys
from ctypes import wintypes

PS = r"C:\Projects\Repos\Agentic Research\Research Setup\vras\Lib\site-packages\PySide6"

print("=== environment ===")
print("python      :", sys.version.replace("\n", " "))
print("executable  :", sys.executable)
print("base_prefix :", sys.base_prefix)
print("PySide6 dir :", PS, "(exists)" if os.path.isdir(PS) else "(MISSING)")
print()

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.GetModuleHandleW.restype = wintypes.HMODULE
k.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
k.GetModuleFileNameW.restype = wintypes.DWORD
k.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]


def where(name):
    h = k.GetModuleHandleW(name)
    if not h:
        return "(not loaded)"
    buf = ctypes.create_unicode_buffer(600)
    k.GetModuleFileNameW(h, buf, 600)
    return buf.value


print("=== C++ runtime already loaded by Python at startup ===")
for rt in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll"):
    print(f"  {rt:22} -> {where(rt)}")
print()

print("=== loading PySide6's own DLLs by absolute path (first failure stops) ===")
for dll in ("msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
            "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll",
            "Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll"):
    p = os.path.join(PS, dll)
    if not os.path.isfile(p):
        print(f"  MISS {dll}  (not present in PySide6 dir)")
        continue
    try:
        ctypes.WinDLL(p)
        print(f"  OK   {dll}")
    except OSError as e:
        print(f"  FAIL {dll}  ->  {e}")
        break
print()
print("msvcp140 now loaded from :", where("msvcp140.dll"))
print("Qt6Core  now loaded from :", where("Qt6Core.dll"))
