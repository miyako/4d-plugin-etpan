"""Exercise real picture wrappers and bundled SDK against a string-owning host."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "darwin", "requires the macOS SDK and Cocoa")
class StringOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.binary = Path(cls.temp.name) / "string-ownership"
        sdk = ROOT / "4D Plugin API"
        command = [
            "xcrun", "clang++", "-std=c++11", "-x", "objective-c++",
            "-include", "Carbon/Carbon.h",
            "-Wno-deprecated-declarations", "-Wno-return-type-c-linkage",
            "-I", str(sdk), "-I", str(sdk / "Classes"),
            str(ROOT / "tests/string_ownership.cpp"),
            str(sdk / "4DPluginAPI.c"),
            *(str(sdk / "Classes" / name) for name in (
                "C_PICTURE.cpp", "C_TEXT.cpp", "C_BLOB.cpp")),
            "-framework", "Cocoa", "-framework", "Carbon",
            "-o", str(cls.binary),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    def run_case(self, case):
        result = subprocess.run([str(self.binary), case], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_file_path_has_one_owner(self):
        self.run_case("path")

    def test_copy_format_has_one_owner(self):
        self.run_case("copy")


if __name__ == "__main__":
    unittest.main()
