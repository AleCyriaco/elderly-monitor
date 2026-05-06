"""
Informações do sistema Raspberry Pi (sem dependências externas).
Usa /proc/ e /sys/ diretamente.
"""

import os
import threading
import time

# ── CPU usage em background (atualiza a cada 2s) ──────────────────────────
_cpu_pct: float = 0.0
_cpu_lock = threading.Lock()


def _read_stat():
    with open('/proc/stat') as f:
        vals = f.readline().split()[1:]
    total = sum(int(x) for x in vals)
    idle  = int(vals[3])
    return total, idle


def _cpu_worker():
    global _cpu_pct
    prev_total, prev_idle = _read_stat()
    while True:
        time.sleep(2)
        try:
            total, idle = _read_stat()
            dt = total - prev_total
            di = idle  - prev_idle
            if dt > 0:
                with _cpu_lock:
                    _cpu_pct = round(100.0 * (1.0 - di / dt), 1)
            prev_total, prev_idle = total, idle
        except Exception:
            pass


threading.Thread(target=_cpu_worker, daemon=True, name='sysinfo-cpu').start()


# ── Funções públicas ────────────────────────────────────────────────────────
def pi_model() -> str:
    for path in ('/proc/device-tree/model', '/sys/firmware/devicetree/base/model'):
        try:
            with open(path, 'rb') as f:
                return f.read().rstrip(b'\x00').decode(errors='replace').strip()
        except OSError:
            pass
    return 'Raspberry Pi'


def cpu_cores() -> int:
    return os.cpu_count() or 1


def cpu_percent() -> float:
    with _cpu_lock:
        return _cpu_pct


def ram_info() -> tuple[int, int]:
    """Retorna (usado_mb, total_mb)."""
    try:
        info: dict[str, int] = {}
        with open('/proc/meminfo') as f:
            for line in f:
                key, _, val = line.partition(':')
                info[key.strip()] = int(val.split()[0])  # kB
        total     = info.get('MemTotal',     0)
        available = info.get('MemAvailable', 0)
        return (total - available) // 1024, total // 1024
    except Exception:
        return 0, 0


def gpu_temp() -> float:
    """Temperatura do SoC (CPU/GPU compartilhado) em graus Celsius."""
    # /sys/class/thermal — disponível em todas as Pi
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except Exception:
        pass
    # fallback: vcgencmd
    try:
        import subprocess
        out = subprocess.check_output(['vcgencmd', 'measure_temp'],
                                      timeout=2, text=True)
        return float(out.strip().split('=')[1].replace("'C", ''))
    except Exception:
        return 0.0


def get_all() -> dict:
    used_mb, total_mb = ram_info()
    return {
        'model':      pi_model(),
        'cpu_cores':  cpu_cores(),
        'cpu_pct':    cpu_percent(),
        'ram_used':   used_mb,
        'ram_total':  total_mb,
        'gpu_temp':   gpu_temp(),
    }
