"""Пакет 17.11, №801: «Нода Лиры» не видела Radeon RX 6700 XT (12 ГБ) — узнавала только NVIDIA через nvidia-smi.
Теперь AMD и Intel: Windows — из реестра видеоадаптеров (64-битная память, а не AdapterRAM, который упирается в 4 ГБ),
Linux — из /sys (amdgpu). Встроенная графика не в счёт, берётся карта с наибольшей памятью."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import liranode  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


G = 1024 ** 3
g = liranode.gpu_other(reg=[{"DriverDesc": "AMD Radeon(TM) Graphics", "HardwareInformation.qwMemorySize": 512 * 1024 ** 2},
                            {"DriverDesc": "AMD Radeon RX 6700 XT", "HardwareInformation.qwMemorySize": 12 * G},
                            {"DriverDesc": "Microsoft Basic Display Adapter"}])
ok(g and g["name"] == "AMD Radeon RX 6700 XT" and g["mem_gb"] == 12.0, f"Windows: Radeon RX 6700 XT, 12 ГБ (встроенная не в счёт): {g}")
g = liranode.gpu_other(reg=[{"DriverDesc": "Intel(R) Arc(TM) A770 Graphics", "HardwareInformation.MemorySize": (16 * G).to_bytes(8, "little")}])
ok(g and g["mem_gb"] == 16.0, f"Windows: Intel Arc, память записана байтами: {g}")
ok(liranode.gpu_other(reg=[{"DriverDesc": "NVIDIA GeForce RTX 4090", "HardwareInformation.qwMemorySize": 24 * G}]) is None,
   "Windows: NVIDIA — не здесь (её знает nvidia-smi с температурой)")
ok(liranode.gpu_other(reg=[]) is None, "Windows: адаптеров нет — None")

d = Path(tempfile.mkdtemp())
def card(n, vendor, mem=None, name=None, busy=None, temp=None):
    p = d / f"card{n}" / "device"; p.mkdir(parents=True)
    (p / "vendor").write_text(vendor + "\n")
    if mem is not None: (p / "mem_info_vram_total").write_text(str(mem))
    if name: (p / "product_name").write_text(name)
    if busy is not None: (p / "gpu_busy_percent").write_text(str(busy))
    if temp is not None: (p / "hwmon/hwmon3").mkdir(parents=True); (p / "hwmon/hwmon3/temp1_input").write_text(str(temp * 1000))
(d / "card0-DP-1").mkdir()
card(0, "0x1002", 512 * 1024 ** 2, "AMD Raphael")
card(1, "0x1002", 12 * G, "Navi 22 [Radeon RX 6700 XT]", busy=7, temp=48)
card(2, "0x10de", 24 * G)
g = liranode.gpu_other(drm=str(d))
ok(g and g["mem_gb"] == 12.0 and "6700" in g["name"] and g["util"] == 7 and g["temp"] == 48,
   f"Linux: amdgpu — имя, память, загрузка и температура: {g}")
ok(liranode.gpu_other(drm=str(d / "нет")) is None, "Linux: нет /sys/class/drm — None")
ok(not liranode.node_vram_ok({"name": "RX 6700 XT", "mem_gb": 12.0}) and liranode.node_vram_ok({"name": "RX 7900 XTX", "mem_gb": 24.0}),
   "порог ноды для AMD — тот же, что для NVIDIA (16 ГБ)")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
