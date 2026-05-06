# Elderly Night Monitor

Raspberry Pi based night monitor for detecting when an elderly person moves from lying down to sitting or standing. It uses camera-based pose detection, local buzzer alerts, a MJPEG web dashboard, WiFi management, and optional local display output.

## Features

- Pi Camera or USB camera support.
- Pose classification: lying, sitting, standing, unknown.
- Configurable buzzer patterns for alert levels.
- Web dashboard with live stream, status, acknowledgement, camera rotation, WiFi controls, and system actions.
- Quiet hours to suppress buzzer alerts during configured periods.
- systemd service for automatic startup.
- Local-first operation with no cloud dependency.

## Repository Contents

- `main.py`: application entry point.
- `camera.py`: camera abstraction for Pi Camera and USB cameras.
- `detector.py`: pose detection and posture classification.
- `buzzer.py`: GPIO buzzer controller.
- `stream.py`: web dashboard and MJPEG server.
- `wifi.py`: NetworkManager integration.
- `config.py`: deployment configuration.
- `install.sh`: Python/system dependency installer.
- `setup_system.sh`: Raspberry Pi system configuration.
- `monitor.service`: systemd unit.
- `movenet_lightning.tflite`: included pose model artifact.
- `docs/`: deployment, security, and hardware notes.

Generated files such as logs, virtual environments, backups, local system inventories, APK builds, and credentials are intentionally excluded from Git.

## Quick Start

```bash
git clone <REPOSITORY_URL> elderly-monitor
cd elderly-monitor
bash install.sh
source venv/bin/activate
python main.py
```

Open the dashboard:

```text
http://<raspberry-pi-ip>:8080/
```

For a full Raspberry Pi deployment, follow [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Configuration

Edit `config.py` before installing as a service:

- Set `USE_PICAMERA2` for Pi Camera vs USB camera.
- Set `SIMULATE_GPIO = False` only when GPIO wiring is ready.
- Tune posture thresholds for the camera angle.
- Adjust quiet hours and stream port for the deployment.

## Security

This project is meant for trusted local networks. The dashboard has operational controls such as WiFi connect, reboot, shutdown, and live camera stream. Do not expose it directly to the internet.

See [docs/SECURITY.md](docs/SECURITY.md).

## Deploy as a Service

```bash
sudo bash setup_system.sh
sudo cp monitor.service /etc/systemd/system/monitor.service
sudo systemctl daemon-reload
sudo systemctl enable monitor.service
sudo systemctl start monitor.service
```

## License

No license has been declared yet. Add one before accepting external contributions.
