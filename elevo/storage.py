"""
Django storage backend that keeps uploaded media (avatars, resumes, chat files,
logos, proctoring snapshots) on Cloudinary.

Used in production because free web hosts wipe their local disk on every deploy
or restart. Enabled automatically when the CLOUDINARY_URL setting is present
(see settings_base.STORAGES).

Stored names keep Django's usual form (e.g. "resumes/cv_ab12cd34.pdf"), so the
database looks the same as with FileSystemStorage. Each name maps to a Cloudinary
asset deterministically:
  * images -> resource_type "image", public_id without the extension
  * audio/video -> resource_type "video", public_id without the extension
  * anything else (PDF, DOCX, TXT, ...) -> resource_type "raw", public_id with
    the extension, since raw assets are addressed by their full file name
"""
import os
import posixpath
import uuid

import cloudinary
import cloudinary.uploader
import cloudinary.utils
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "svg", "ico", "avif", "heic", "tif", "tiff"}
# Cloudinary stores audio under the "video" resource type.
VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "mkv", "mp3", "wav", "ogg", "m4a", "aac", "flac"}

REQUEST_TIMEOUT = 30


def cloudinary_location(name):
    """Return (resource_type, public_id, format) for a stored file name."""
    name = name.replace("\\", "/")
    stem, ext = posixpath.splitext(name)
    ext = ext.lstrip(".").lower()
    if ext in IMAGE_EXTENSIONS:
        return "image", stem, ext
    if ext in VIDEO_EXTENSIONS:
        return "video", stem, ext
    return "raw", name, None


@deconstructible
class CloudinaryMediaStorage(Storage):
    def __init__(self):
        url = getattr(settings, "CLOUDINARY_URL", "") or ""
        if url:
            os.environ["CLOUDINARY_URL"] = url
            cloudinary.reset_config()
        cloudinary.config(secure=True)

    # ---- naming -------------------------------------------------------
    def get_available_name(self, name, max_length=None):
        """
        Always add a short random suffix instead of checking for clashes,
        which would cost a network round trip per upload.
        """
        name = name.replace("\\", "/")
        directory, filename = posixpath.split(name)
        stem, ext = posixpath.splitext(filename)
        suffix = "_" + uuid.uuid4().hex[:8]
        candidate = posixpath.join(directory, f"{stem}{suffix}{ext}")
        if max_length and len(candidate) > max_length:
            overflow = len(candidate) - max_length
            stem = stem[: max(1, len(stem) - overflow)]
            candidate = posixpath.join(directory, f"{stem}{suffix}{ext}")
        return candidate

    # ---- writing ------------------------------------------------------
    def _save(self, name, content):
        name = name.replace("\\", "/")
        resource_type, public_id, _ = cloudinary_location(name)
        if hasattr(content, "seek"):
            content.seek(0)
        data = content.read()
        if isinstance(data, str):
            data = data.encode("utf-8")
        cloudinary.uploader.upload(
            (posixpath.basename(name), data),
            public_id=public_id,
            resource_type=resource_type,
            overwrite=True,
            invalidate=True,
            use_filename=False,
            unique_filename=False,
        )
        return name

    def delete(self, name):
        if not name:
            return
        resource_type, public_id, _ = cloudinary_location(name)
        cloudinary.uploader.destroy(public_id, resource_type=resource_type, invalidate=True)

    # ---- reading ------------------------------------------------------
    def url(self, name):
        resource_type, public_id, fmt = cloudinary_location(name)
        options = {"resource_type": resource_type, "secure": True}
        if fmt:
            options["format"] = fmt
        return cloudinary.utils.cloudinary_url(public_id, **options)[0]

    def _open(self, name, mode="rb"):
        response = requests.get(self.url(name), timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return ContentFile(response.content, name=name)

    def exists(self, name):
        try:
            response = requests.head(self.url(name), timeout=REQUEST_TIMEOUT, allow_redirects=True)
        except requests.RequestException:
            return False
        return response.status_code == 200

    def size(self, name):
        response = requests.head(self.url(name), timeout=REQUEST_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        return int(response.headers.get("Content-Length", 0))
