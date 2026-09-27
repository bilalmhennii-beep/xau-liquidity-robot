#!/usr/bin/env python3
"""Download XAUUSD M1 history from Dukascopy using dukascopy-node.

Prerequisite: Node.js + npx.
Raw market data stays out of git.
"""
from __future__ import annotations
import argparse, subprocess
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--from-date", default="2015-01-01")
    p.add_argument("--to-date", default="2026-09-26")
    p.add_argument("--out", default="data/raw")
    a=p.parse_args()
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    cmd=["npx","dukascopy-node","-i","xauusd","-from",a.from_date,"-to",a.to_date,"-t","m1","-f","csv","-dir",str(out)]
    print(" ".join(cmd))
    subprocess.run(cmd,check=True)

if __name__=="__main__":
    main()
