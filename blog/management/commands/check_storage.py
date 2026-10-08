import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Upload, read back, and delete a small test file to verify media storage works."

    def handle(self, *args, **options):
        default_storage = storages["default"]
        backend = type(default_storage)
        self.stdout.write(f"Storage backend: {backend.__module__}.{backend.__name__}")

        name = f"storage-check/{uuid.uuid4().hex}.txt"
        payload = b"hello from check_storage"
        try:
            saved_name = default_storage.save(name, ContentFile(payload))
            self.stdout.write(f"Uploaded:  {saved_name}")
            self.stdout.write(f"Public URL: {default_storage.url(saved_name)}")

            with default_storage.open(saved_name) as f:
                if f.read() != payload:
                    raise CommandError("Read back different content than was uploaded.")
            self.stdout.write("Read back: OK")

            default_storage.delete(saved_name)
            self.stdout.write("Deleted:   OK")
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f"Storage check failed: {type(exc).__name__}: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("Media storage is working."))
