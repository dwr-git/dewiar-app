#!/usr/bin/env python3
"""Стенд гипотез — запуск из командной строки (вся логика — core/stand.py; там же описание и примеры)."""
import runpy
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent / "core"
sys.path.insert(0, str(CORE))
runpy.run_path(str(CORE / "stand.py"), run_name="__main__")
