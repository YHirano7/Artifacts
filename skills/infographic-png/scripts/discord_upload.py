"""Upload a PNG (or any file) to a Discord webhook as a direct attachment.

Usage:
    set DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...   (Windows cmd)
    export DISCORD_WEBHOOK_URL=...                                 (bash)
    python discord_upload.py <file_path> [content]

Uses only urllib — avoids curl, which mangles UTF-8 through the shell.
The image is sent as a plain attachment (no embeds), so Discord does not
downscale the preview.
"""
import json
import os
import sys
import urllib.request
import uuid


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    content = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(path)
    url = os.environ["DISCORD_WEBHOOK_URL"]
    filename = os.path.basename(path)

    payload = json.dumps(
        {"content": content, "attachments": [{"id": 0, "filename": filename}]},
        ensure_ascii=False,
    )
    boundary = uuid.uuid4().hex
    body = b""
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\n'
        f"Content-Type: application/json\r\n\r\n"
    ).encode() + payload.encode("utf-8") + b"\r\n"
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="files[0]"; '
        f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'
    ).encode()
    with open(path, "rb") as f:
        body += f.read()
    body += f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        url + ("&" if "?" in url else "?") + "wait=true",
        data=body,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        print("status:", r.status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
