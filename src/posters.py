"""Poster download, compression and optional rehosting."""
from __future__ import annotations

import hashlib
import logging
import mimetypes
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

import requests
from PIL import Image

try:
    from .http_client import create_retry_session
except ImportError:
    from http_client import create_retry_session

logger = logging.getLogger(__name__)
SEE_UPLOAD_URL = "https://s.ee/api/v1/file/upload"


def is_usable_poster_url(value: Optional[str]) -> bool:
    return bool(value and value.strip().startswith(("http://", "https://")))


class PosterService:
    def __init__(
        self,
        posters_dir: Path,
        *,
        image_host_token: Optional[str] = None,
        timeout: float = 30,
        cleanup: bool = True,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.posters_dir = posters_dir
        self.image_host_token = image_host_token
        self.timeout = timeout
        self.cleanup = cleanup
        self.session = session or create_retry_session()

    def _local_path(self, image_url: str, content_type: str = "") -> Path:
        name = Path(unquote(urlparse(image_url).path)).name
        if not name:
            name = hashlib.sha256(image_url.encode("utf-8")).hexdigest()[:20]
        if not Path(name).suffix:
            name += mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".jpg"
        return self.posters_dir / name

    def download(self, image_url: str) -> Path:
        response = self.session.get(
            image_url,
            headers={"Referer": "https://movie.douban.com/"},
            stream=True,
            timeout=self.timeout,
        )
        response.raise_for_status()
        self.posters_dir.mkdir(parents=True, exist_ok=True)
        path = self._local_path(image_url, response.headers.get("content-type", ""))
        with path.open("wb") as output:
            for chunk in response.iter_content(8192):
                if chunk:
                    output.write(chunk)
        return path

    @staticmethod
    def compress(path: Path, max_size_kb: int = 5000) -> None:
        if path.stat().st_size <= max_size_kb * 1024:
            return
        with Image.open(path) as image:
            ratio = (max_size_kb * 1024 / path.stat().st_size) ** 0.5
            resized = image.resize(
                (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
            ).convert("RGB")
            resized.save(path, format="JPEG", quality=88, optimize=True)

    def upload(self, path: Path) -> Optional[str]:
        if not self.image_host_token:
            return None
        self.compress(path)
        with path.open("rb") as image:
            response = self.session.post(
                SEE_UPLOAD_URL,
                files={"smfile": image},
                headers={"Authorization": self.image_host_token},
                timeout=max(self.timeout, 60),
            )
        response.raise_for_status()
        result = response.json()
        data = result.get("data")
        if isinstance(data, dict) and is_usable_poster_url(data.get("url")):
            return str(data["url"])
        repeated = result.get("images")
        if result.get("code") == "image_repeated" and repeated:
            value = repeated[0] if isinstance(repeated, list) else repeated
            return str(value) if is_usable_poster_url(str(value)) else None
        logger.warning("Image host rejected poster: %s", result)
        return None

    def rehost(self, image_url: str) -> Optional[str]:
        if not image_url or not self.image_host_token:
            return None
        path: Optional[Path] = None
        try:
            path = self.download(image_url)
            return self.upload(path)
        except (OSError, requests.RequestException, ValueError) as exc:
            logger.warning("Unable to rehost Douban poster: %s", exc)
            return None
        finally:
            if self.cleanup and path and path.exists():
                path.unlink()
