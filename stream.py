"""
Servidor HTTP:
  GET  /                    → interface web (estado + stream + WiFi)
  GET  /stream.mjpg         → stream MJPEG ao vivo
  GET  /status              → JSON {"state", "alert"}
  GET  /ack                 → silencia buzzer ACK_SILENCE_SEC
  GET  /wifi/status         → JSON {ssid, ip}
  GET  /wifi/scan           → JSON lista de redes
  POST /wifi/connect        → JSON body {ssid, password}
  POST /system/reboot       → reinicia a Raspberry Pi
  POST /system/shutdown     → desliga a Raspberry Pi
  GET  /download/monitor.apk → APK Android
"""

import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer as HTTPServer

import cv2
import numpy as np

import config
import wifi as wifi_mod
import sysinfo
import rotation as rotation_mod

_APK_PATH = os.path.join(os.path.dirname(__file__), 'monitor.apk')

_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <title>Monitor Noturno</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    * { -webkit-tap-highlight-color: transparent; }

    body {
      background: #0d0d0d; color: #ddd;
      font-family: -apple-system, 'Segoe UI', Arial, sans-serif;
      display: flex; flex-direction: column; align-items: stretch;
      min-height: 100dvh;
      padding: max(12px, env(safe-area-inset-top))
               max(12px, env(safe-area-inset-right))
               max(16px, env(safe-area-inset-bottom))
               max(12px, env(safe-area-inset-left));
      gap: 10px;
    }

    h1 {
      font-size: 0.7rem; color: #444;
      letter-spacing: 0.12em; text-transform: uppercase; text-align: center;
    }

    /* ── Cards ──────────────────────────────────────────── */
    .card {
      background: #181818; border: 2px solid #282828; border-radius: 14px;
      padding: 14px 16px;
    }

    /* ── Estado ─────────────────────────────────────────── */
    #status-box {
      display: flex; align-items: center; justify-content: center;
      gap: 12px; padding: 22px 16px;
      transition: border-color 0.3s;
    }
    #status-box.alerting {
      animation: pulse-border 1.1s ease-in-out infinite;
    }
    @keyframes pulse-border {
      0%,100% { opacity: 1; }
      50%      { opacity: 0.55; }
    }
    #icon        { font-size: clamp(2.6rem, 13vw, 4.2rem); line-height: 1; user-select: none; }
    #state-label { font-size: clamp(2.2rem, 12vw, 3.8rem); font-weight: 900; transition: color 0.3s; }
    .DEITADO { color: #27ae60; }
    .SENTADO { color: #e67e22; }
    .EM_PE   { color: #e74c3c; }
    .UNKNOWN { color: #444; }

    /* ── Sub-linha de alerta ─────────────────────────────── */
    #sub {
      min-height: 1.3em; text-align: center;
      font-size: clamp(0.82rem, 3.5vw, 0.95rem);
      font-weight: 700; color: #e74c3c; letter-spacing: 0.04em;
    }

    /* ── Botão ACK ───────────────────────────────────────── */
    #btn-ack {
      display: none; width: 100%; padding: 17px;
      font-size: clamp(1rem, 4.5vw, 1.1rem); font-weight: 700;
      border-radius: 14px; cursor: pointer; border: none;
      background: #922b21; color: #fff; touch-action: manipulation;
      transition: background 0.15s;
    }
    #btn-ack.visible { display: block; }
    #btn-ack:active  { background: #7b241c; }

    /* ── Barra de áudio ──────────────────────────────────── */
    #audio-bar { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    #audio-status { font-size: 0.82rem; color: #666; }
    #audio-status.on { color: #27ae60; }

    /* ── Botões genéricos ────────────────────────────────── */
    .btn-sm {
      min-height: 44px; padding: 8px 18px;
      font-size: 0.88rem; border-radius: 10px; cursor: pointer;
      border: 1px solid #333; background: #222; color: #aaa;
      touch-action: manipulation; white-space: nowrap;
    }
    .btn-sm:active { background: #2e2e2e; }
    .btn-sm.active { border-color: #e74c3c; color: #e74c3c; }

    /* ── Aviso wake lock ─────────────────────────────────── */
    #wakelock-warn {
      display: none;
      background: #2a1800; border: 1px solid #7a4000; border-radius: 10px;
      padding: 10px 14px; font-size: 0.78rem; color: #e0a040; text-align: center;
    }

    /* ── Stream ──────────────────────────────────────────── */
    #stream-img {
      width: 100%; display: block;
      border-radius: 12px; border: 2px solid #1e1e1e;
    }

    /* ── WiFi ────────────────────────────────────────────── */
    #wifi-header {
      display: flex; justify-content: space-between; align-items: center;
      cursor: pointer; user-select: none; min-height: 44px;
    }
    #wifi-header h3  { font-size: 0.9rem; color: #aaa; font-weight: 600; }
    #wifi-current    { font-size: 0.76rem; color: #27ae60; }
    #wifi-chevron    { color: #555; font-size: 0.8rem; transition: transform 0.2s; }
    #wifi-body       { display: none; margin-top: 10px; }
    #wifi-body.open  { display: block; }
    #wifi-chevron.open { transform: rotate(180deg); }

    .wifi-btns { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }

    .wifi-net {
      display: flex; align-items: center; gap: 12px;
      min-height: 52px; padding: 10px 12px;
      border-radius: 10px; cursor: pointer; touch-action: manipulation;
      border: 1px solid transparent; margin-bottom: 6px; background: #111;
    }
    .wifi-net:active    { background: #161616; }
    .wifi-net.selected  { border-color: #3498db; background: #0d1a26; }
    .wifi-net.connected { border-color: #27ae60; }
    .wifi-signal        { font-size: 1rem; }
    .wifi-name          { flex: 1; font-size: 0.92rem; color: #ddd; }
    .wifi-sec           { font-size: 0.7rem; color: #666; }
    .wifi-conn-badge    { font-size: 0.7rem; color: #27ae60; }

    #wifi-connect-form {
      background: #0f0f0f; border: 1px solid #2a2a2a;
      border-radius: 10px; padding: 14px; margin-top: 8px; display: none;
    }
    #wifi-connect-form.open { display: block; }
    #wifi-connect-form label { font-size: 0.82rem; color: #888; display: block; margin-bottom: 8px; }
    #wifi-pw {
      width: 100%; padding: 13px 14px;
      background: #1a1a1a; border: 1px solid #333; border-radius: 9px;
      color: #eee; font-size: 1rem; /* ≥16px evita zoom automático no iOS */
      margin-bottom: 12px; -webkit-appearance: none;
    }
    .wifi-form-btns { display: flex; gap: 8px; }
    .btn-connect {
      flex: 1; padding: 14px; font-size: 0.95rem; border-radius: 10px;
      cursor: pointer; border: none; background: #2980b9; color: #fff;
      font-weight: 700; touch-action: manipulation;
    }
    .btn-connect:active   { background: #2471a3; }
    .btn-connect:disabled { background: #333; cursor: default; }
    .btn-cancel {
      padding: 14px 18px; border-radius: 10px; cursor: pointer;
      background: #222; border: 1px solid #333; color: #888;
      font-size: 0.9rem; touch-action: manipulation;
    }

    #wifi-msg { font-size: 0.82rem; margin-top: 10px; min-height: 1.2em; }
    #wifi-msg.ok  { color: #27ae60; }
    #wifi-msg.err { color: #e74c3c; }

    /* ── Barra de hardware ───────────────────────────────── */
    #hw-bar {
      display: flex; flex-direction: column; gap: 6px;
      padding: 10px 14px;
      background: #161616; border: 1px solid #2a2a2a; border-radius: 10px;
    }
    .hw-item {
      display: flex; align-items: center; justify-content: space-between;
      gap: 8px;
    }
    .hw-label { font-size: 0.72rem; color: #666; text-transform: uppercase;
                letter-spacing: 0.05em; min-width: 36px; }
    .hw-val   { font-size: 0.85rem; font-weight: 700; color: #ccc; text-align: right; }

    /* ── Botões de rotação ───────────────────────────────── */
    .btn-rot {
      flex: 1; min-height: 44px; padding: 8px 4px;
      font-size: 0.9rem; font-weight: 600; border-radius: 10px;
      cursor: pointer; border: 1px solid #333; background: #1e1e1e; color: #666;
      touch-action: manipulation; transition: all 0.15s;
    }
    .btn-rot:active   { background: #2a2a2a; }
    .btn-rot.active   { border-color: #3498db; background: #0d1a26; color: #3498db; }

    /* ── Botões de sistema ───────────────────────────────── */
    .btn-sys {
      flex: 1; min-height: 48px; padding: 12px 8px;
      font-size: 0.9rem; font-weight: 600; border-radius: 10px;
      cursor: pointer; border: none; touch-action: manipulation;
      transition: opacity 0.15s;
    }
    .btn-sys:active  { opacity: 0.75; }
    .btn-reboot      { background: #7d5a00; color: #ffd166; }
    .btn-shutdown    { background: #5a0000; color: #ff6b6b; }

    /* ── Toast de ativação de áudio ─────────────────────── */
    #audio-toast {
      position: fixed; bottom: max(16px, env(safe-area-inset-bottom));
      left: 50%; transform: translateX(-50%);
      z-index: 200; cursor: pointer;
      background: #1a3a1a; border: 1px solid #2d6a2d; border-radius: 50px;
      padding: 12px 22px; display: flex; align-items: center; gap: 10px;
      font-size: 0.88rem; color: #4caf50; font-weight: 600;
      box-shadow: 0 4px 20px rgba(0,0,0,0.6);
      white-space: nowrap;
      transition: opacity 0.4s;
    }
    #audio-toast.hidden { opacity: 0; pointer-events: none; }
  </style>
</head>
<body>

  <!-- Toast de ativação (não bloqueia a página) -->
  <div id="audio-toast" onclick="initAudio()">
    <span>🔔</span><span>Toque para ativar alertas sonoros</span>
  </div>

  <h1>Monitor Noturno</h1>

  <!-- Info do hardware -->
  <div id="hw-bar">
    <div class="hw-item">
      <span class="hw-label">CPU</span>
      <span class="hw-val" id="hw-cpu">–</span>
    </div>
    <div class="hw-item">
      <span class="hw-label">RAM</span>
      <span class="hw-val" id="hw-ram">–</span>
    </div>
    <div class="hw-item">
      <span class="hw-label">GPU</span>
      <span class="hw-val" id="hw-gpu">–</span>
    </div>
  </div>

  <!-- Estado -->
  <div class="card" id="status-box">
    <div id="icon">❓</div>
    <div id="state-label" class="UNKNOWN">AGUARDANDO</div>
  </div>

  <div id="sub"></div>

  <!-- ACK (aparece só quando há alerta) -->
  <button id="btn-ack" onclick="sendAck()">✅ Reconhecer alerta</button>

  <!-- Áudio / Mute -->
  <div class="card" id="audio-bar">
    <div id="audio-status">⏳ Aguardando ativação...</div>
    <button class="btn-sm" id="btn-mute" onclick="toggleMute()">🔇 Silenciar</button>
  </div>

  <!-- Aviso se wake lock não suportado -->
  <div id="wakelock-warn">
    ⚠️ Seu browser não suporta manter a tela acesa automaticamente.<br>
    Ative <b>Não desligar a tela</b> nas configurações do celular.
  </div>

  <!-- Stream da câmera -->
  <img id="stream-img" src="/stream.mjpg" alt="câmera ao vivo">

  <!-- Rotação da câmera -->
  <div class="card" style="padding:12px 16px;">
    <div style="font-size:0.78rem;color:#666;margin-bottom:10px;">🎥 Rotação da câmera</div>
    <div style="display:flex;gap:8px;justify-content:center;">
      <button class="btn-rot" data-deg="0"   onclick="setRotation(0)"  >0°</button>
      <button class="btn-rot" data-deg="90"  onclick="setRotation(90)" >90°</button>
      <button class="btn-rot" data-deg="180" onclick="setRotation(180)">180°</button>
      <button class="btn-rot" data-deg="270" onclick="setRotation(270)">270°</button>
    </div>
    <div id="rot-msg" style="font-size:0.75rem;color:#555;text-align:center;margin-top:8px;min-height:1em;"></div>
  </div>

  <!-- Sistema -->
  <div class="card" id="sys-card">
    <div id="sys-header" onclick="toggleSys()"
         style="display:flex;justify-content:space-between;align-items:center;
                cursor:pointer;user-select:none;min-height:44px;">
      <h3 style="font-size:0.9rem;color:#aaa;font-weight:600;">⚙️ Sistema</h3>
      <span id="sys-chevron" style="color:#555;font-size:0.8rem;transition:transform 0.2s;">▼</span>
    </div>
    <div id="sys-body" style="display:none;margin-top:12px;">
      <div style="display:flex;gap:10px;">
        <button class="btn-sys btn-reboot"  onclick="sysAction('reboot')">🔄 Reiniciar Pi</button>
        <button class="btn-sys btn-shutdown" onclick="sysAction('shutdown')">⏻ Desligar Pi</button>
      </div>
      <div id="sys-msg" style="font-size:0.8rem;margin-top:8px;min-height:1.2em;"></div>
    </div>
  </div>

  <!-- App Android -->
  <a href="/download/monitor.apk" download="MonitorNoturno.apk"
     style="display:flex;align-items:center;justify-content:center;gap:10px;
            background:#1a3a1a;border:1px solid #2d6a2d;border-radius:14px;
            padding:14px 18px;text-decoration:none;color:#4caf50;font-weight:600;
            font-size:0.95rem;">
    <span style="font-size:1.4rem">📱</span>
    <span>Baixar app Android<br><small style="font-weight:400;color:#666;font-size:0.75rem">Alertas em segundo plano • tela bloqueada</small></span>
  </a>

  <!-- WiFi -->
  <div class="card">
    <div id="wifi-header" onclick="toggleWifi()">
      <h3>📶 WiFi &nbsp;<span id="wifi-current"></span></h3>
      <span id="wifi-chevron">▼</span>
    </div>
    <div id="wifi-body">
      <div class="wifi-btns">
        <button class="btn-sm" onclick="scanWifi()" id="btn-scan">🔍 Escanear redes</button>
        <button class="btn-sm" onclick="disconnectWifi()" id="btn-disc" style="display:none">Desconectar</button>
      </div>
      <div id="wifi-list"></div>
      <div id="wifi-connect-form">
        <label>Senha para <strong id="wifi-form-ssid"></strong></label>
        <input type="password" id="wifi-pw" placeholder="Senha da rede WiFi..." autocomplete="off">
        <div class="wifi-form-btns">
          <button class="btn-connect" id="btn-connect" onclick="connectWifi()">Conectar</button>
          <button class="btn-cancel" onclick="cancelConnect()">Cancelar</button>
        </div>
        <div id="wifi-msg"></div>
      </div>
    </div>
  </div>

  <script>
  // ── Estado global ────────────────────────────────────────────────────────
  let audioCtx    = null;
  let audioOn     = false;
  let muted       = false;
  let lastState   = '';
  let sittingTmr  = null;
  let standingTmr = null;
  let wifiOpen    = false;
  let selSsid     = '';

  const ICONS  = { 'DEITADO':'😴', 'SENTADO':'🧍', 'EM PÉ':'🚶' };
  const CSS    = { 'DEITADO':'DEITADO', 'SENTADO':'SENTADO', 'EM PÉ':'EM_PE' };
  const BORDER = { 'DEITADO':'#27ae60', 'SENTADO':'#e67e22', 'EM PÉ':'#e74c3c' };

  // ── Wake Lock ────────────────────────────────────────────────────────────
  let wakeLock = null;
  async function requestWakeLock() {
    if (!('wakeLock' in navigator)) {
      document.getElementById('wakelock-warn').style.display = 'block'; return;
    }
    try {
      wakeLock = await navigator.wakeLock.request('screen');
      wakeLock.addEventListener('release', () => { wakeLock = null; });
      document.getElementById('wakelock-warn').style.display = 'none';
    } catch(e) {
      document.getElementById('wakelock-warn').style.display = 'block';
    }
  }
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && audioOn && !muted && !wakeLock)
      requestWakeLock();
  });

  // ── Ativação de áudio ────────────────────────────────────────────────────
  // Ativa no primeiro toque em qualquer lugar da página
  function _firstTouch() {
    document.removeEventListener('touchstart', _firstTouch);
    document.removeEventListener('click',      _firstTouch);
    initAudio();
  }
  document.addEventListener('touchstart', _firstTouch, { passive: true });
  document.addEventListener('click',      _firstTouch);

  function initAudio() {
    const toast = document.getElementById('audio-toast');
    try {
      if (!audioCtx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) throw new Error('sem suporte');
        audioCtx = new AC();
      }
      if (audioCtx.state === 'suspended') audioCtx.resume();
      audioOn = true;
      toast.classList.add('hidden');
      requestWakeLock();
      tone(880, 0.08, 0.15, 'sine', 0);
      if      (lastState === 'SENTADO') startSittingAlert();
      else if (lastState === 'EM PÉ')   startStandingAlert();
    } catch(e) {
      audioOn = false;
      console.warn('AudioContext:', e);
    }
    updateAudioStatus();
  }
  function toggleMute() {
    muted = !muted;
    const btn = document.getElementById('btn-mute');
    btn.classList.toggle('active', muted);
    btn.textContent = muted ? '🔔 Ativar som' : '🔇 Silenciar';
    if (muted) { stopAlerts(); }
    else {
      if      (lastState === 'SENTADO') startSittingAlert();
      else if (lastState === 'EM PÉ')   startStandingAlert();
    }
    updateAudioStatus();
  }
  function updateAudioStatus() {
    const el    = document.getElementById('audio-status');
    const toast = document.getElementById('audio-toast');
    if (!audioOn) {
      el.textContent = '⏳ Toque em qualquer lugar para ativar';
      el.className   = '';
      toast.classList.remove('hidden');
      return;
    }
    toast.classList.add('hidden');
    if (muted) { el.textContent = '🔇 Alertas silenciados'; el.className = ''; }
    else       { el.textContent = '🔔 Alertas sonoros ativos'; el.className = 'on'; }
  }

  // ── Gerador de tom ───────────────────────────────────────────────────────
  function tone(freq, dur, vol=0.4, type='sine', off=0) {
    if (!audioOn || muted || !audioCtx) return;
    const t = audioCtx.currentTime + off;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain); gain.connect(audioCtx.destination);
    osc.type = type; osc.frequency.value = freq;
    gain.gain.setValueAtTime(vol, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + dur);
    osc.start(t); osc.stop(t + dur + 0.01);
  }

  // ── Alertas sonoros ──────────────────────────────────────────────────────
  function startSittingAlert() {
    stopAlerts();
    const fn = () => {
      tone(440, 0.35, 0.45, 'sine', 0.0);
      tone(370, 0.35, 0.40, 'sine', 0.5);
    };
    fn(); sittingTmr = setInterval(fn, 12000);
  }
  function startStandingAlert() {
    stopAlerts();
    const fn = () => {
      tone(1050, 0.10, 0.50, 'square', 0.00);
      tone(1050, 0.10, 0.50, 'square', 0.18);
      tone(1050, 0.10, 0.50, 'square', 0.36);
      tone(1300, 0.15, 0.55, 'square', 0.54);
    };
    fn(); standingTmr = setInterval(fn, 3000);
  }
  function stopAlerts() {
    if (sittingTmr)  { clearInterval(sittingTmr);  sittingTmr  = null; }
    if (standingTmr) { clearInterval(standingTmr); standingTmr = null; }
  }

  // ── ACK ──────────────────────────────────────────────────────────────────
  async function sendAck() {
    await fetch('/ack');
    stopAlerts();
    document.getElementById('btn-ack').classList.remove('visible');
    document.getElementById('status-box').classList.remove('alerting');
    document.getElementById('sub').textContent = '';
  }

  // ── Poll estado ──────────────────────────────────────────────────────────
  async function poll() {
    try {
      const d = await fetch('/status').then(r => r.json());
      const display = (d.state === 'DESCONHECIDO') ? 'DEITADO' : d.state;
      const box = document.getElementById('status-box');
      document.getElementById('state-label').textContent = display;
      document.getElementById('icon').textContent        = ICONS[display] || '😴';
      document.getElementById('state-label').className   = CSS[display]   || 'DEITADO';
      box.style.borderColor = BORDER[display] || '#27ae60';
      // Alerta ativo → pulsar + botão ACK
      const alerting = d.alert && display !== 'DEITADO';
      box.classList.toggle('alerting', alerting);
      document.getElementById('btn-ack').classList.toggle('visible', alerting);
      document.getElementById('sub').textContent = alerting ? '⚠️ ALERTA ATIVO' : '';
      if (d.state !== lastState) {
        if      (display === 'DEITADO') stopAlerts();
        else if (d.state === 'SENTADO') startSittingAlert();
        else if (d.state === 'EM PÉ')  startStandingAlert();
        lastState = d.state;
      }
    } catch(e) {
      document.getElementById('sub').textContent = '⚡ sem conexão';
    }
  }
  poll(); setInterval(poll, 1500);

  // ── WiFi UI ──────────────────────────────────────────────────────────────
  function toggleWifi() {
    wifiOpen = !wifiOpen;
    document.getElementById('wifi-body').classList.toggle('open', wifiOpen);
    document.getElementById('wifi-chevron').classList.toggle('open', wifiOpen);
    if (wifiOpen) refreshWifiStatus();
  }
  async function refreshWifiStatus() {
    try {
      const d = await fetch('/wifi/status').then(r => r.json());
      const el = document.getElementById('wifi-current');
      if (d.ssid) {
        el.textContent = '✓ ' + d.ssid + (d.ip ? ' (' + d.ip + ')' : '');
        document.getElementById('btn-disc').style.display = 'inline-block';
      } else {
        el.textContent = 'desconectado';
        document.getElementById('btn-disc').style.display = 'none';
      }
    } catch(e) {}
  }
  refreshWifiStatus(); setInterval(refreshWifiStatus, 8000);

  async function scanWifi() {
    const btn = document.getElementById('btn-scan');
    btn.textContent = '⏳ Escaneando...'; btn.disabled = true;
    document.getElementById('wifi-list').innerHTML = '';
    cancelConnect();
    try {
      const nets = await fetch('/wifi/scan').then(r => r.json());
      renderNetworks(nets);
    } catch(e) {
      document.getElementById('wifi-list').innerHTML =
        '<div style="color:#e74c3c;font-size:0.82rem">Erro ao escanear</div>';
    }
    btn.textContent = '🔍 Escanear redes'; btn.disabled = false;
  }
  function signalIcon(pct) {
    if (pct >= 75) return '▂▄▆█';
    if (pct >= 50) return '▂▄▆░';
    if (pct >= 25) return '▂▄░░';
    return '▂░░░';
  }
  function renderNetworks(nets) {
    const list = document.getElementById('wifi-list');
    if (!nets.length) {
      list.innerHTML = '<div style="color:#666;font-size:0.82rem">Nenhuma rede encontrada</div>';
      return;
    }
    list.innerHTML = nets.map(n => `
      <div class="wifi-net${n.connected ? ' connected' : ''}"
           onclick="selectNet('${n.ssid.replace(/'/g,"\\'")}','${n.security}')">
        <span class="wifi-signal">${signalIcon(n.signal)}</span>
        <span class="wifi-name">${n.ssid}</span>
        <span class="wifi-sec">${n.security}</span>
        ${n.connected ? '<span class="wifi-conn-badge">✓</span>' : ''}
      </div>`).join('');
  }
  function selectNet(ssid, security) {
    selSsid = ssid;
    document.querySelectorAll('.wifi-net').forEach(el =>
      el.classList.toggle('selected', el.querySelector('.wifi-name').textContent === ssid));
    document.getElementById('wifi-form-ssid').textContent = ssid;
    document.getElementById('wifi-connect-form').classList.add('open');
    const pw = document.getElementById('wifi-pw');
    pw.placeholder = security === 'Aberta' ? 'Rede aberta — sem senha' : 'Senha da rede WiFi...';
    pw.value = ''; pw.focus();
    document.getElementById('wifi-msg').textContent = '';
    document.getElementById('wifi-msg').className = '';
  }
  function cancelConnect() {
    selSsid = '';
    document.getElementById('wifi-connect-form').classList.remove('open');
    document.getElementById('wifi-msg').textContent = '';
    document.querySelectorAll('.wifi-net').forEach(el => el.classList.remove('selected'));
  }
  async function connectWifi() {
    if (!selSsid) return;
    const pw  = document.getElementById('wifi-pw').value;
    const btn = document.getElementById('btn-connect');
    const msg = document.getElementById('wifi-msg');
    btn.disabled = true; btn.textContent = 'Conectando...';
    msg.textContent = ''; msg.className = '';
    try {
      const r = await fetch('/wifi/connect', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ssid: selSsid, password: pw}),
      });
      const d = await r.json();
      if (d.ok) {
        msg.textContent = '✅ Conectado!'; msg.className = 'ok';
        setTimeout(() => { cancelConnect(); refreshWifiStatus(); }, 2000);
      } else {
        msg.textContent = '❌ ' + (d.message || 'Falha'); msg.className = 'err';
      }
    } catch(e) {
      msg.textContent = '❌ Erro de comunicação'; msg.className = 'err';
    }
    btn.disabled = false; btn.textContent = 'Conectar';
  }
  async function disconnectWifi() {
    if (!confirm('Desconectar do WiFi atual?')) return;
    await fetch('/wifi/disconnect', {method: 'POST'});
    setTimeout(refreshWifiStatus, 2000);
  }
  document.getElementById('wifi-pw').addEventListener('keydown', e => {
    if (e.key === 'Enter') connectWifi();
  });

  // ── Hardware info ────────────────────────────────────────────────────────
  async function pollHW() {
    try {
      const d = await fetch('/system/info').then(r => r.json());
      // CPU
      const cpu = d.cpu_pct ?? 0;
      const cpuEl = document.getElementById('hw-cpu');
      cpuEl.textContent = cpu.toFixed(0) + '% de ' + (d.cpu_cores ?? '?') + ' cores';
      cpuEl.style.color = cpu > 80 ? '#e74c3c' : cpu > 50 ? '#e67e22' : '#ccc';
      // RAM: "50% usado de 3.7 GB"
      const used = d.ram_used ?? 0; const total = d.ram_total ?? 1;
      const ramPct = Math.round(100 * used / total);
      const totalGB = (total / 1024).toFixed(1);
      const ramEl = document.getElementById('hw-ram');
      ramEl.textContent = ramPct + '% usado de ' + totalGB + ' GB';
      ramEl.style.color = ramPct > 85 ? '#e74c3c' : ramPct > 65 ? '#e67e22' : '#ccc';
      // GPU: temperatura do SoC (CPU/GPU compartilhados na Pi)
      const gpuEl = document.getElementById('hw-gpu');
      const temp = d.gpu_temp ?? 0;
      gpuEl.textContent = temp.toFixed(0) + '°C';
      gpuEl.style.color = temp > 80 ? '#e74c3c' : temp > 65 ? '#e67e22' : '#ccc';
      // Sincroniza rotação
      if (d.rotation !== undefined) highlightRotation(d.rotation);
    } catch(e) {
      document.getElementById('hw-cpu').textContent = 'erro';
      console.warn('pollHW:', e);
    }
  }
  pollHW(); setInterval(pollHW, 5000);

  // ── Rotação da câmera ────────────────────────────────────────────────────
  function highlightRotation(deg) {
    document.querySelectorAll('.btn-rot').forEach(b => {
      b.classList.toggle('active', parseInt(b.dataset.deg) === deg);
    });
  }
  async function setRotation(deg) {
    highlightRotation(deg);
    const msg = document.getElementById('rot-msg');
    msg.style.color = '#aaa'; msg.textContent = '⏳ Aplicando…';
    try {
      const r = await fetch('/camera/rotation', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({rotation: deg}),
      });
      const d = await r.json();
      // Rotação é aplicada server-side em cada frame — reconecta o stream
      const img = document.getElementById('stream-img');
      img.src = '/stream.mjpg';
      msg.style.color = '#27ae60';
      msg.textContent = '✅ ' + d.rotation + '° aplicado';
      setTimeout(() => { msg.textContent = ''; }, 3000);
    } catch(e) {
      msg.style.color = '#e74c3c'; msg.textContent = '❌ Erro ao aplicar';
    }
  }

  // ── Sistema ──────────────────────────────────────────────────────────────
  let sysOpen = false;
  function toggleSys() {
    sysOpen = !sysOpen;
    document.getElementById('sys-body').style.display   = sysOpen ? 'block' : 'none';
    document.getElementById('sys-chevron').style.transform = sysOpen ? 'rotate(180deg)' : '';
  }
  async function sysAction(action) {
    const labels  = { reboot: 'reiniciar', shutdown: 'desligar' };
    const confirm = window.confirm(
      action === 'reboot'
        ? '🔄 Reiniciar a Raspberry Pi?\\nO monitor ficará offline por ~30 segundos.'
        : '⏻ Desligar a Raspberry Pi?\\nSerá necessário ligar manualmente depois.'
    );
    if (!confirm) return;

    const msg = document.getElementById('sys-msg');
    msg.style.color = '#aaa';
    msg.textContent = '⏳ Enviando comando...';
    try {
      const r = await fetch('/system/' + action, { method: 'POST' });
      const d = await r.json();
      if (d.ok) {
        msg.style.color = '#e67e22';
        msg.textContent = action === 'reboot'
          ? '🔄 Reiniciando… aguarde ~30s e recarregue a página.'
          : '⏻ Desligando… até logo.';
      } else {
        msg.style.color = '#e74c3c';
        msg.textContent = '❌ ' + (d.message || 'Erro');
      }
    } catch(e) {
      msg.style.color = '#e74c3c';
      msg.textContent = '❌ Sem resposta (normal se estiver desligando)';
    }
  }
  </script>
</body>
</html>"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        srv: "MJPEGServer" = self.server.app  # type: ignore[attr-defined]
        path = self.path.split('?')[0]  # ignora query params

        if path in ('/', '/index.html'):
            body = _HTML.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(body)
            return

        elif path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Content-Type',
                             'multipart/x-mixed-replace; boundary=--boundary')
            self.end_headers()
            try:
                while True:
                    frame = srv.get_frame()
                    if frame is None:
                        time.sleep(0.05)
                        continue
                    _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
                    data = jpeg.tobytes()
                    self.wfile.write(
                        b'--boundary\r\nContent-Type: image/jpeg\r\n'
                        + f'Content-Length: {len(data)}\r\n\r\n'.encode()
                        + data + b'\r\n'
                    )
                    time.sleep(1 / config.FPS_CAP)
            except (BrokenPipeError, ConnectionResetError):
                pass

        elif path == '/status':
            payload = json.dumps({'state': srv.current_state, 'alert': srv.alert_active}).encode()
            self._respond(200, 'application/json', payload)

        elif path == '/ack':
            srv.trigger_ack()
            self._respond(200, 'application/json', b'{"ok":true}')

        elif path == '/system/info':
            info = sysinfo.get_all()
            info['rotation'] = rotation_mod.get()
            self._respond(200, 'application/json', json.dumps(info).encode())

        elif path == '/wifi/status':
            ssid = wifi_mod.current_ssid()
            ip   = wifi_mod.current_ip() if ssid else None
            self._respond(200, 'application/json',
                          json.dumps({'ssid': ssid, 'ip': ip}).encode())

        elif path == '/wifi/scan':
            nets = wifi_mod.scan_networks()
            self._respond(200, 'application/json', json.dumps(nets).encode())

        elif path == '/download/monitor.apk':
            if os.path.exists(_APK_PATH):
                with open(_APK_PATH, 'rb') as f:
                    data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/vnd.android.package-archive')
                self.send_header('Content-Disposition', 'attachment; filename="MonitorNoturno.apk"')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(404, 'APK não encontrado')

        else:
            self.send_error(404)

    def do_POST(self):
        path = self.path.split('?')[0]
        if path == '/wifi/connect':
            length = int(self.headers.get('Content-Length', 0))
            body   = json.loads(self.rfile.read(length) or b'{}')
            ssid   = body.get('ssid', '')
            pw     = body.get('password', '')
            if not ssid:
                self._respond(400, 'application/json', b'{"ok":false,"message":"ssid vazio"}')
                return
            ok, msg = wifi_mod.connect(ssid, pw)
            self._respond(200, 'application/json',
                          json.dumps({'ok': ok, 'message': msg}).encode())

        elif path == '/wifi/disconnect':
            ok, msg = wifi_mod.disconnect()
            self._respond(200, 'application/json',
                          json.dumps({'ok': ok, 'message': msg}).encode())

        elif path == '/camera/rotation':
            length = int(self.headers.get('Content-Length', 0))
            body   = json.loads(self.rfile.read(length) or b'{}')
            deg    = int(body.get('rotation', 0))
            rotation_mod.set_rotation(deg)
            self._respond(200, 'application/json',
                          json.dumps({'ok': True, 'rotation': rotation_mod.get()}).encode())

        elif path in ('/system/reboot', '/system/shutdown'):
            cmd = 'reboot' if path == '/system/reboot' else 'poweroff'
            try:
                self._respond(200, 'application/json', b'{"ok":true}')
                # Pequeno atraso para garantir que a resposta chegue ao cliente
                threading.Timer(1.5, lambda: subprocess.Popen(
                    ['sudo', cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )).start()
            except Exception as e:
                self._respond(500, 'application/json',
                              json.dumps({'ok': False, 'message': str(e)}).encode())

        else:
            self.send_error(404)

    def _respond(self, code: int, ctype: str, body: bytes):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class MJPEGServer:
    def __init__(self, on_ack=None):
        self._frame: np.ndarray | None = None
        self._lock  = threading.Lock()
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.current_state = 'DESCONHECIDO'
        self.alert_active  = False
        self._on_ack       = on_ack

    def update_frame(self, frame: np.ndarray):
        with self._lock:
            self._frame = frame.copy()

    def update_state(self, state: str, alert: bool):
        self.current_state = state
        self.alert_active  = alert

    def get_frame(self) -> np.ndarray | None:
        with self._lock:
            return self._frame

    def trigger_ack(self):
        if self._on_ack:
            self._on_ack()

    def start(self):
        if not config.STREAM_ENABLED:
            return
        server = HTTPServer(('0.0.0.0', config.STREAM_PORT), _Handler)
        server.app = self  # type: ignore[attr-defined]
        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever, daemon=True, name='mjpeg-server')
        self._thread.start()

    def stop(self):
        if self._server:
            self._server.shutdown()
