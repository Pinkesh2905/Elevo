"""
One-time copy of local uploads (MEDIA_ROOT) to Cloudinary, keeping each file's
stored name, so database rows that point at "avatars/x.png" etc. keep working
after switching to CloudinaryMediaStorage.

Usage (CLOUDINARY_URL must be set, e.g. in .env):
    python manage.py upload_media_to_cloudinary --dry-run
    python manage.py upload_media_to_cloudinary
"""
import os
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from elevo.storage import CloudinaryMediaStorage, cloudinary_location


class Command(BaseCommand):
    help = "Upload every file under MEDIA_ROOT to Cloudinary, keeping its stored name."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="List what would be uploaded.")

    def handle(self, *args, **options):
        if not getattr(settings, "CLOUDINARY_URL", ""):
            raise CommandError("CLOUDINARY_URL is not set.")
        root = Path(settings.MEDIA_ROOT)
        if not root.is_dir():
            raise CommandError(f"MEDIA_ROOT does not exist: {root}")

        storage = CloudinaryMediaStorage()
        files = sorted(p for p in root.rglob("*") if p.is_file())
        uploaded = failed = 0
        for path in files:
            name = path.relative_to(root).as_posix()
            resource_type, public_id, _ = cloudinary_location(name)
            if options["dry_run"]:
                self.stdout.write(f"[dry-run] {name} -> {resource_type}:{public_id}")
                continue
            try:
                with open(path, "rb") as fh:
                    storage._save(name, File(fh, name=os.path.basename(name)))
                uploaded += 1
                self.stdout.write(f"  uploaded {name}")
            except Exception as exc:  # keep going; report at the end
                failed += 1
                self.stderr.write(f"  FAILED {name}: {exc}")

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f"{len(files)} files would be uploaded."))
        else:
            style = self.style.SUCCESS if not failed else self.style.WARNING
            self.stdout.write(style(f"Uploaded {uploaded} files, {failed} failed."))
