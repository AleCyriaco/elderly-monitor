# Deployment Guide

This guide installs the elderly monitor on a Raspberry Pi from a clean clone.

## Target Hardware

- Raspberry Pi 4 or newer recommended.
- Raspberry Pi OS 64-bit recommended.
- Pi Camera Module or USB camera.
- Optional active buzzer connected to the configured BCM GPIO pin.
- Local network access for the web dashboard.

## 1. Prepare the Raspberry Pi

Create or use a non-root user. The examples below use `monitor`, but any user works if you update the service file.

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip network-manager
```

Clone the repository:

```bash
cd /home/monitor
git clone <REPOSITORY_URL> elderly-monitor
cd elderly-monitor
```

## 2. Install Dependencies

Run the installer:

```bash
bash install.sh
```

For Raspberry Pi OS, install camera support if it is not already present:

```bash
sudo apt-get install -y python3-picamera2 libcamera-apps
```

## 3. Configure the Monitor

Edit `config.py` for your hardware:

```bash
nano config.py
```

Important settings:

- `USE_PICAMERA2`: `True` for Pi Camera, `False` for USB camera.
- `CAMERA_INDEX`: USB camera index when `USE_PICAMERA2=False`.
- `BUZZER_PIN`: BCM GPIO pin for the buzzer.
- `SIMULATE_GPIO`: keep `True` while testing without GPIO hardware.
- `STREAM_PORT`: web dashboard port.
- `LYING_ANGLE_MAX` and `SITTING_ANGLE_MAX`: posture thresholds.

## 4. Configure System Permissions

The web UI can manage WiFi and system power actions. Run the system setup script only on a trusted local device:

```bash
sudo bash setup_system.sh
```

Review the sudoers file created by the script before exposing the device to any network you do not control.

## 5. Run Manually

```bash
source venv/bin/activate
python main.py
```

Open the dashboard from another device on the same network:

```text
http://<raspberry-pi-ip>:8080/
```

## 6. Install as a Service

Copy and enable the systemd unit. If your deployment user or path is different from `/home/monitor/elderly-monitor`, edit `monitor.service` first.

```bash
sudo cp monitor.service /etc/systemd/system/monitor.service
sudo systemctl daemon-reload
sudo systemctl enable monitor.service
sudo systemctl start monitor.service
```

Check status and logs:

```bash
sudo systemctl status monitor.service
journalctl -u monitor.service -f
```

## 7. Updating a Deployment

```bash
cd /home/monitor/elderly-monitor
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart monitor.service
```

## 8. Backup and Restore

For a source-only backup:

```bash
rsync -aH --exclude venv --exclude __pycache__ --exclude '*.log' \
  /home/monitor/elderly-monitor/ ./elderly-monitor-backup/
```

For a full migration, preserve:

- Repository contents.
- Local `config.py` changes.
- Optional `.camera_rotation`.
- The installed `monitor.service` if customized.
- Any generated Android app artifact kept outside Git.
