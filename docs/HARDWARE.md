# Hardware Setup

## Camera

The monitor supports:

- Raspberry Pi CSI camera through `picamera2`.
- USB camera through OpenCV.

Set the camera mode in `config.py`:

```python
USE_PICAMERA2 = True
CAMERA_INDEX = 0
```

Use `USE_PICAMERA2 = False` for USB cameras.

## Buzzer

The buzzer uses BCM GPIO numbering.

Default:

```python
BUZZER_PIN = 18
SIMULATE_GPIO = True
```

Set `SIMULATE_GPIO = False` only after wiring and testing the buzzer. Use a transistor/driver circuit when the buzzer current exceeds safe GPIO limits.

## Camera Placement

Place the camera with a stable side view of the bed. Tune these thresholds in `config.py` after testing:

```python
LYING_ANGLE_MAX = 35.0
SITTING_ANGLE_MAX = 68.0
```

Use the web UI camera rotation controls or create `.camera_rotation` locally with one of:

```text
0
90
180
270
```
