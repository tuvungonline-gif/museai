import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location("retention_canvas", Path(__file__).resolve().parents[1] / "canvas_server.py")
canvas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(canvas)


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.media = self.root / "media"
        self.media.mkdir()
        self.now = 2_000_000_000

    def tearDown(self):
        self.temp.cleanup()

    def file(self, name, age_hours, folder=None):
        p = (folder or self.media) / name
        p.write_bytes(b"media-data")
        stamp = self.now - age_hours * 3600
        os.utime(p, (stamp, stamp))
        return p

    def test_removes_expired_media_only(self):
        expired = self.file("old.mp4", 25)
        recent = self.file("recent.png", 23)
        boundary = self.file("boundary.jpg", 24)
        account = self.file("accounts.json", 100)
        partial = self.file("download.mp4.crdownload", 100)
        child = self.media / "archive"
        child.mkdir()
        nested = self.file("keep.mp4", 100, child)
        outside = self.file("outside.mp4", 100, self.root)
        link = self.media / "linked.mp4"
        try:
            link.symlink_to(outside)
        except OSError:
            link = None  # Standard Windows accounts may lack symlink privileges.
        removed, size = canvas._remove_expired_media(self.media, 24, self.now)
        self.assertEqual((removed, size), (1, 10))
        self.assertFalse(expired.exists())
        for p in (recent, boundary, account, partial, nested, outside):
            self.assertTrue(p.exists(), str(p))
        if link is not None:
            self.assertTrue(link.is_symlink())

    def test_rejects_zero_and_negative_retention(self):
        old = self.file("old.mp4", 100)
        for hours in (0, -1):
            with self.assertRaises(ValueError):
                canvas._remove_expired_media(self.media, hours, self.now)
        self.assertTrue(old.exists())

    def test_does_not_follow_linked_media_directory(self):
        link = self.root / "linked-media"
        try:
            link.symlink_to(self.media, target_is_directory=True)
        except OSError:
            self.skipTest("This Windows account cannot create symbolic links")
        old = self.file("old.mp4", 100)
        self.assertEqual(canvas._remove_expired_media(link, 24, self.now), (0, 0))
        self.assertTrue(old.exists())


if __name__ == "__main__":
    unittest.main()
