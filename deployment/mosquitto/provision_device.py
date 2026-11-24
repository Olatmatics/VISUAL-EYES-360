"""Add a device user to the Mosquitto password file.

Reads the one-time credential from the environment, never from argv, and
never prints it. Mosquitto's $7$ format is PBKDF2-HMAC-SHA512 with 100
iterations and a 12-byte salt.

  VE360_DEVICE_UID=FCC-XXXX VE360_MQTT_TOKEN=<token> python provision_device.py
  docker compose restart mqtt
"""

import base64
import hashlib
import os
import secrets
from pathlib import Path

PASSWD = Path(__file__).with_name("passwd")


def main() -> int:
    uid = os.environ.get("VE360_DEVICE_UID", "")
    token = os.environ.get("VE360_MQTT_TOKEN", "")
    if not uid or not token:
        print("Set VE360_DEVICE_UID and VE360_MQTT_TOKEN in the environment.")
        return 2
    if any(ch in uid for ch in ":\r\n"):
        print("Invalid VE360_DEVICE_UID.")
        return 2

    salt = secrets.token_bytes(12)
    digest = hashlib.pbkdf2_hmac("sha512", token.encode(), salt, 100)
    entry = f"{uid}:$7${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}\n"

    existing = PASSWD.read_text(encoding="utf-8").splitlines() if PASSWD.exists() else []
    kept = [line for line in existing if line and not line.startswith(f"{uid}:")]
    PASSWD.write_text("\n".join(kept + [entry.rstrip("\n")]) + "\n", encoding="utf-8")
    print(f"Provisioned MQTT user {uid}. Restart mqtt to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
