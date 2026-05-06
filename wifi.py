"""
Gerenciamento de WiFi via nmcli (NetworkManager).
Requer que o usuário tenha permissão sudo para nmcli (configurado em setup_system.sh).
"""

import subprocess
import logging

log = logging.getLogger("monitor")


def _run(*cmd, timeout=20) -> tuple[int, str, str]:
    try:
        r = subprocess.run(
            list(cmd), capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, '', 'Timeout ao executar nmcli'
    except FileNotFoundError:
        return -1, '', 'nmcli não encontrado — instale NetworkManager'


def current_ssid() -> str | None:
    """Retorna o SSID da conexão WiFi atual, ou None."""
    _, out, _ = _run('nmcli', '-t', '-f', 'DEVICE,STATE,CONNECTION', 'dev')
    for line in out.splitlines():
        parts = line.split(':')
        if len(parts) >= 3 and parts[1] == 'connected' and 'eth' not in parts[0]:
            return parts[2] or None
    return None


def current_ip() -> str | None:
    """Retorna o IP do adaptador WiFi, ou None."""
    _, out, _ = _run('nmcli', '-t', '-f', 'IP4.ADDRESS', 'dev', 'show', 'wlan0')
    for line in out.splitlines():
        if 'IP4.ADDRESS' in line:
            # formato: IP4.ADDRESS[1]:<ip-local>/24
            addr = line.split(':', 1)[-1].split('/')[0]
            return addr
    return None


def scan_networks() -> list[dict]:
    """
    Escaneia redes WiFi próximas.
    Retorna lista de dicts: {ssid, signal, security, connected}
    """
    connected = current_ssid() or ''

    code, out, err = _run(
        'nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY', 'dev', 'wifi', 'list',
        '--rescan', 'yes', timeout=15,
    )
    if code != 0:
        log.warning(f"WiFi scan falhou: {err}")
        return []

    networks: list[dict] = []
    seen: set[str] = set()

    for line in out.splitlines():
        parts = line.split(':')
        ssid  = parts[0].strip() if parts else ''
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)

        try:
            signal = int(parts[1]) if len(parts) > 1 and parts[1].strip().lstrip('-').isdigit() else 0
        except (ValueError, IndexError):
            signal = 0

        raw_sec = parts[2].strip() if len(parts) > 2 else ''
        security = 'Aberta' if raw_sec in ('--', '') else raw_sec

        networks.append({
            'ssid':      ssid,
            'signal':    signal,
            'security':  security,
            'connected': ssid == connected,
        })

    networks.sort(key=lambda x: (-x['signal'], x['ssid']))
    return networks


def connect(ssid: str, password: str) -> tuple[bool, str]:
    """
    Conecta a uma rede WiFi.
    Retorna (sucesso: bool, mensagem: str).
    """
    if password:
        code, out, err = _run(
            'sudo', 'nmcli', 'dev', 'wifi', 'connect', ssid,
            'password', password, timeout=30,
        )
    else:
        code, out, err = _run(
            'sudo', 'nmcli', 'dev', 'wifi', 'connect', ssid, timeout=30,
        )

    success = code == 0
    message = out if success else (err or out or f'Código de erro: {code}')
    if success:
        log.info(f"WiFi conectado: {ssid}")
    else:
        log.warning(f"WiFi falhou ({ssid}): {message}")
    return success, message


def disconnect() -> tuple[bool, str]:
    """Desconecta a interface WiFi."""
    code, out, err = _run('sudo', 'nmcli', 'dev', 'disconnect', 'wlan0', timeout=15)
    return code == 0, out or err
