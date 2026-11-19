"""Small offline example, or a public HTTPS download with checksum."""
import hashlib
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

from .paths import child_path, directories


def download_data(config, force=False):
    data_dir, _ = directories(config)
    settings = config.get("download", {})
    target = child_path(data_dir / "raw", settings.get("filename", "example.csv"))
    if target.exists() and not force:
        raise FileExistsError(f"File already exists: {target}; use --force to replace it")
    url = settings.get("url")
    checksum = settings.get("sha256")
    if url:
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.netloc or parts.username or parts.password or parts.query:
            raise ValueError("Use a public HTTPS URL without credentials or query parameters")
        if not isinstance(checksum, str) or len(checksum) != 64 or any(c not in "0123456789abcdefABCDEF" for c in checksum):
            raise ValueError("Remote downloads require a valid SHA-256 checksum")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temp_path = Path(stream.name)
            digest = hashlib.sha256()
            if url:
                with urlopen(url, timeout=60) as response:
                    if urlsplit(response.geturl()).scheme != "https":
                        raise ValueError("HTTPS is required after redirect")
                    while chunk := response.read(1024 * 1024):
                        stream.write(chunk)
                        digest.update(chunk)
                if digest.hexdigest() != checksum.lower():
                    raise ValueError("SHA-256 mismatch; downloaded file discarded")
            else:
                stream.write(b"value\n1\n2\n3\n4\n5\n")
        os.replace(temp_path, target)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return target
