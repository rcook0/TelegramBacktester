from __future__ import annotations
import subprocess, sys, os
from typing import List, Tuple

def run_module(module: str, args: List[str], *, capture: bool = True) -> Tuple[int, str]:
    cmd = [sys.executable, "-m", module] + list(args)
    if capture:
        p = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return p.returncode, p.stdout
    p = subprocess.run(cmd, check=False)
    return p.returncode, ""

def ensure_ok(code: int, out: str, label: str) -> None:
    if code != 0:
        raise RuntimeError(f"{label} failed (exit={code})\n{out[-4000:]}")
