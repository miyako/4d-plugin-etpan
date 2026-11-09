"""Run real helper/workflow phases with no native, credential or network fallback."""

import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
from unittest import mock
import unittest

import yaml

from helper_support import Fixture, ROOT, cwd, original, source
import native


WORKFLOW = ROOT / ".github/workflows/release.yml"
CONTENTS = native.CONTENTS
STUB = r'''#!PYTHON
import json, os, pathlib, plistlib, shutil, sys
tool, args = pathlib.Path(sys.argv[0]).name, sys.argv[1:]
with open(os.environ["CALL_LOG"], "a") as out:
    out.write(json.dumps([tool, *args]) + "\n")
if os.environ.get("FAIL_TOOL") == tool:
    sys.exit(23)
c = pathlib.Path("etpan.4dbase/Plugins/etpan.bundle/Contents")
if tool == "python3":
    if "release.py" in args[0]:
        if os.environ.get("FAIL_PREFLIGHT") and args[1] == "preflight":
            sys.exit(19)
        if args[1] == "preflight":
            with open(os.environ["GITHUB_OUTPUT"], "a") as out:
                out.write("version=" + os.environ["VERSION"] + "\ntag=v" + os.environ["VERSION"] + "\n")
        sys.exit(0)
    os.execv(sys.executable, [sys.executable, *args])
elif tool == "xcodebuild":
    assert args[:6] == ["-project", "etpan.xcodeproj", "-target", "etpan", "-configuration", "Default"]
    for arg in ("ARCHS=arm64 x86_64", "ONLY_ACTIVE_ARCH=NO", "MACOSX_DEPLOYMENT_TARGET=11.5",
                "CODE_SIGNING_ALLOWED=NO",
                "CONFIGURATION_BUILD_DIR=" + str(pathlib.Path.cwd() / "etpan.4dbase/Plugins")):
        assert arg in args, args
    for suffix in ("MacOS/etpan", "Info.plist", "Resources/English.lproj/InfoPlist.strings",
                   "_CodeSignature/CodeResources"):
        assert not (c / suffix).exists(), suffix
    if not os.environ.get("MISDIRECTED_BUILD"):
        (c / "MacOS").mkdir(parents=True, exist_ok=True)
        (c / "MacOS/etpan").write_bytes(b"fresh-native-output")
        (c / "Info.plist").write_bytes(plistlib.dumps(
            {"CFBundleShortVersionString": os.environ["VERSION"]}, fmt=plistlib.FMT_BINARY))
        p = c / "Resources/English.lproj/InfoPlist.strings"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(pathlib.Path("English.lproj/InfoPlist.strings").read_bytes())
elif tool == "lipo":
    print(os.environ.get("DYLIB_ARCHES" if args[-1].endswith(".dylib") else "ARCHES",
                         "arm64 x86_64"))
elif tool == "otool":
    print(str(c / "MacOS/etpan") + " (architecture arm64):")
    print(os.environ.get("OTOOL", "\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0)"))
    print(str(c / "MacOS/etpan") + " (architecture x86_64):")
    print("\t/System/Library/Frameworks/Cocoa.framework/Versions/A/Cocoa (compatibility version 1.0.0)")
elif tool == "base64":
    assert sys.stdin.read() == "offline-certificate"
    pathlib.Path(args[args.index("-o") + 1]).write_bytes(b"offline-p12")
elif tool == "security":
    if args[0] == "find-identity":
        print("" if os.environ.get("MISSING_IDENTITY") else
              '  1) ABCDEF "Developer ID Application: Offline Fixture"')
elif tool == "codesign":
    if "--verify" in args:
        n = pathlib.Path("verify-count")
        count = int(n.read_text()) + 1 if n.exists() else 1
        n.write_text(str(count))
        if str(count) == os.environ.get("FAIL_VERIFY_AT"):
            sys.exit(9)
        sys.exit(9 if os.environ.get("FAIL_VERIFY") else 0)
    (c / "_CodeSignature").mkdir(parents=True, exist_ok=True)
    (c / "_CodeSignature/CodeResources").write_bytes(b"fresh-signature")
elif tool in ("ditto", "hdiutil"):
    pathlib.Path(args[-1]).write_bytes(b"offline-package")
elif tool == "xcrun":
    if args[:2] == ["notarytool", "submit"]:
        status = os.environ.get("NOTARY_STATUS", "Accepted")
        if os.environ.get("FAIL_DMG_NOTARY") and args[2].endswith(".dmg"):
            status = "Invalid"
        print("not-json" if status == "malformed" else
              json.dumps({"id": "offline-only", **({"status": status} if status != "missing" else {})}))
        sys.exit(int(os.environ.get("NOTARY_EXIT", "0")))
    if args[:2] == ["stapler", "staple"]:
        sys.exit(int(os.environ.get("STAPLE_EXIT", "0")))
elif tool == "plutil":
    print(json.load(sys.stdin)[args[1]])
else:
    sys.exit("Unexpected native stub: " + tool)
'''


class NativePreparationTests(Fixture):
    def test_selective_cleanup_preserves_bundle_default_and_build_siblings(self):
        protected = []
        for bundle in native.OUTPUT_BUNDLES:
            for path in ("Windows64/etpan.4DX", "MacOS/runtime.dylib",
                         "Resources/manifest.json", "Resources/constants.xlf",
                         "QuickLook/Thumbnail.png", "MacOS/etpan.html"):
                protected.append(self.write(bundle / "Contents" / path, b"preserved"))
        for path in (*native.MAC_FILES, *native.XC_DATABASES):
            self.write(path, b"stale")
        for path in native.MAC_DIRECTORIES:
            self.write(path / "stale.o", b"stale")
        protected.extend(self.write(path, b"preserved") for path in (
            "etpan.4dbase/Plugins/Default/keep", "build/deps/keep",
            "build/unrelated/keep", "build/XCBuildData/unrelated",
            "a/libetpan.a", "include/mac/libetpan/mail.h"))
        with cwd(self.root):
            native.prepare("macos")
            native.prepare("macos")
        for path in protected:
            self.assertEqual(path.read_bytes(), b"preserved")
        self.assertFalse(any((self.root / p).exists()
                             for p in (*native.MAC_FILES, *native.MAC_DIRECTORIES,
                                       *native.XC_DATABASES)))

    def test_windows_cleanup_is_leaf_only_and_preserves_debug(self):
        self.write(native.WINDOWS_OUTPUT, b"stale")
        self.write(native.WINDOWS_BINARY, b"stale")
        self.write("Objs/Release/stale.obj", b"stale")
        protected = [self.write(p, b"keep") for p in (
            "Objs/Debug/keep.obj", "etpan.4dbase/Plugins/Default/keep",
            str(CONTENTS / "QuickLook/Thumbnail.png"))]
        with cwd(self.root):
            native.prepare("windows")
        for p in protected:
            self.assertEqual(p.read_bytes(), b"keep")
        self.assertFalse((self.root / "Objs/Release").exists())
        self.assertFalse((self.root / native.WINDOWS_OUTPUT).exists())

    def test_all_symlinks_are_validated_before_any_deletion(self):
        first = self.write(native.MAC_FILES[0], b"must remain")
        destination = self.write("outside/keep", b"keep")
        for where in (native.MAC_FILES[-1], native.MAC_DIRECTORIES[-1],
                      native.OUTPUT_BUNDLES[-1]):
            with self.subTest(path=where):
                link = self.root / where
                if link.is_dir():
                    shutil.rmtree(link)
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(destination)
                with cwd(self.root), self.assertRaisesRegex(ValueError, "symlink"):
                    native.prepare("macos")
                self.assertEqual(first.read_bytes(), b"must remain")
                link.unlink()
        nested = self.root / native.MAC_DIRECTORIES[0] / "nested-link"
        nested.parent.mkdir(parents=True)
        nested.symlink_to(destination)
        with cwd(self.root), self.assertRaisesRegex(ValueError, "symlink"):
            native.prepare("macos")
        self.assertEqual(first.read_bytes(), b"must remain")

    def test_cleanup_io_error_is_fatal(self):
        self.write(native.MAC_FILES[0], b"stale")
        with cwd(self.root), mock.patch.object(Path, "unlink", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                native.prepare("macos")

    def test_generated_allowlist_boundaries(self):
        yes = (*native.MAC_FILES, *native.XC_DATABASES, *native.DEPENDENCY_FILES,
               native.WINDOWS_BINARY, native.WINDOWS_OUTPUT, Path("winbuild/etpan.4DX"),
               *(p / "generated" for p in (*native.MAC_DIRECTORIES,
                                          *native.DEPENDENCY_DIRECTORIES)),
               Path("Objs/Release/etpan.obj"),
               Path("build/XCBuildData/" + "a" * 32 + ".xcbuilddata/manifest.json"))
        for path in yes:
            self.assertTrue(native.generated(str(path)), path)
        for path in (
            *map(str, source.SOURCE_PATHS), "build/source.cpp", "a/unexpected.a",
            "winbuild/nested/etpan.4DX", "build/XCBuildData/build.db-evil",
            "build/XCBuildData/unrelated", "build/etpan.build-evil/file",
            "Objs/Debug/etpan.obj", "include/mac/unexpected.h",
            str(CONTENTS / "MacOS/runtime.dylib"), str(CONTENTS / "Resources/manifest.json"),
            str(CONTENTS / "QuickLook/Thumbnail.png"), "../build/deps/escape",
            "build/deps/../source", "/build/deps/file", "build\\deps\\file",
        ):
            self.assertFalse(native.generated(path), path)


class NativeWorkflowTests(Fixture):
    def setUp(self):
        super().setUp()
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        self.tools = self.root / "tools"
        self.tools.mkdir()
        self.log = self.root / "calls.jsonl"
        for tool in ("python3", "xcodebuild", "lipo", "otool", "base64", "security",
                     "codesign", "ditto", "hdiutil", "xcrun", "plutil"):
            path = self.tools / tool
            path.write_text(STUB.replace("PYTHON", sys.executable))
            path.chmod(0o755)
        for tool in ("ls", "grep", "head", "sed", "sort"):
            target = shutil.which(tool)
            self.assertIsNotNone(target)
            (self.tools / tool).symlink_to(target)
        self.pwsh = shutil.which("pwsh")
        self.assertIsNotNone(self.pwsh, "PowerShell is required; native suite must not skip")
        self.workflow = yaml.load(WORKFLOW.read_bytes(), Loader=yaml.BaseLoader)
        self.sources(self.checkout)
        shutil.copytree(ROOT / ".github/scripts", self.checkout / ".github/scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.version = source.read(self.checkout)
        self.env = {
            "PATH": str(self.tools), "HOME": str(self.checkout),
            "CALL_LOG": str(self.log), "VERSION": self.version,
            "PRODUCT_NAME": "etpan", "MACOS_DEPLOYMENT_TARGET": "11.5",
            "GITHUB_SHA": "a" * 40, "GITHUB_ENV": str(self.checkout / "github-env"),
            "GITHUB_OUTPUT": str(self.checkout / "github-output"),
            "BUNDLE_PATH": str(native.BUNDLE), "KEYCHAIN_PATH": "offline.keychain",
            "RUNNER_TEMP": str(self.checkout), "CERT_BASE64": "offline-certificate",
            "CERT_PASSWORD": "offline-only", "KEYCHAIN_PASSWORD": "offline-only",
            "APPLE_ID": "offline@example.invalid", "TEAM_ID": "OFFLINEONLY",
            "APP_PASSWORD": "offline-only", "GH_TOKEN": "offline-only",
            "ZIP_PATH": f"etpan-{self.version}.zip", "DMG_PATH": f"etpan-{self.version}.dmg",
            "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C",
        }
        for path in ("manifest.json", "constants.xlf"):
            (self.checkout / path).write_bytes((ROOT / path).read_bytes())
        for path in native.DEPENDENCY_FILES[:3]:
            self.write_at(path, b"offline-library")
        for name in ("manifest.json", "constants.xlf"):
            self.write_at(CONTENTS / "Resources" / name, (ROOT / name).read_bytes())
        for suffix in ("MacOS/etpan", "Info.plist",
                       "Resources/English.lproj/InfoPlist.strings", "_CodeSignature/CodeResources"):
            self.write_at(CONTENTS / suffix, b"stale-output")
        for suffix in ("MacOS/runtime.dylib", "QuickLook/Thumbnail.png",
                       "Windows64/etpan.html"):
            self.write_at(CONTENTS / suffix, b"preserved-resource")
        self.write_at("etpan.4dbase/Plugins/Default/keep", b"preserved-resource")
        self.write_at("winbuild/etpan.4DX", b"fresh-windows")

    def write_at(self, path, data):
        target = self.checkout / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def run_step(self, name, job="build-macos", success=True, prefix=""):
        steps = self.workflow["jobs"][job]["steps"]
        step = next(s for s in steps if s.get("name") == name)
        values = {"env.PRODUCT_NAME": "etpan", "env.MACOS_DEPLOYMENT_TARGET": "11.5",
                  "needs.version.outputs.version": self.version}
        script = re.sub(r"\$\{\{\s*(.*?)\s*\}\}", lambda m: values[m[1]], step["run"])
        if step.get("shell") == "pwsh":
            command = [self.pwsh, "-NoProfile", "-NonInteractive", "-Command", prefix + script]
        else:
            command = ["/bin/bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", prefix + script]
        result = subprocess.run(command, cwd=self.checkout, env=self.env,
                                capture_output=True, text=True, timeout=30)
        if success is True:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        elif success is False:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def build(self):
        return self.run_step("build macOS plugin (universal)")

    def test_actual_version_step_reads_source_and_checks_before_native_work(self):
        self.run_step("read selected source and reject existing publication", "version")
        self.assertEqual((self.checkout / "github-output").read_text(),
                         f"version={self.version}\ntag=v{self.version}\n")
        self.assertTrue(any(c[0] == "python3" and c[1:] == [
            ".github/scripts/release.py", "preflight", "--sha", "a" * 40] for c in self.calls()))

    def reset_artifacts(self):
        for suffix in ("zip", "dmg"):
            (self.checkout / f"etpan-{self.version}.{suffix}").unlink(missing_ok=True)
        (self.checkout / "github-env").unlink(missing_ok=True)
        (self.checkout / "verify-count").unlink(missing_ok=True)

    def pipeline(self):
        for name in ("initial clean source and publication check", "check prebuilt libraries",
                     "import Developer ID certificate", "store notarytool credentials",
                     "build macOS plugin (universal)", "verify universal binary",
                     "merge Windows binaries into the bundle", "codesign",
                     "package, notarize & staple", "create GitHub Release"):
            result = self.run_step(name, success=None)
            if result.returncode:
                return result
        return result

    def test_actual_build_metadata_resources_and_merge(self):
        self.build()
        self.run_step("verify universal binary")
        self.run_step("merge Windows binaries into the bundle")
        self.assertEqual((self.checkout / CONTENTS / "MacOS/etpan").read_bytes(), b"fresh-native-output")
        self.assertEqual((self.checkout / native.WINDOWS_BINARY).read_bytes(), b"fresh-windows")
        for path in ("MacOS/runtime.dylib", "QuickLook/Thumbnail.png", "Windows64/etpan.html"):
            self.assertEqual((self.checkout / CONTENTS / path).read_bytes(), b"preserved-resource")
        self.assertEqual((self.checkout / "etpan.4dbase/Plugins/Default/keep").read_bytes(),
                         b"preserved-resource")

    def test_empty_missing_misdirected_and_cleanup_failures_stop_build(self):
        self.env["MISDIRECTED_BUILD"] = "1"
        self.build()
        self.run_step("verify universal binary", success=False)
        del self.env["MISDIRECTED_BUILD"]
        self.build()
        binary = self.checkout / CONTENTS / "MacOS/etpan"
        binary.write_bytes(b"")
        self.run_step("verify universal binary", success=False)
        binary.unlink()
        binary.mkdir()
        self.log.unlink()
        self.run_step("build macOS plugin (universal)", success=False)
        self.assertFalse(any(c[0] == "xcodebuild" for c in self.calls()))

    def test_exact_architecture_tokens_i386_ban_and_runtime_policy(self):
        self.build()
        for arches in ("", "arm64", "arm64e x86_64", "arm64 x86_64h", "arm64 x86_64 i386"):
            with self.subTest(arches=arches):
                self.env["ARCHES"] = arches
                self.run_step("verify universal binary", success=False)
        self.env["ARCHES"] = "arm64 x86_64 arm64e"
        self.run_step("verify universal binary")
        for arches in ("arm64e x86_64", "arm64 x86_64h", "arm64 x86_64 i386"):
            self.env["DYLIB_ARCHES"] = arches
            self.run_step("verify universal binary", success=False)
        self.env["DYLIB_ARCHES"] = "arm64 x86_64 arm64e"
        self.run_step("verify universal binary")
        for library in ("@rpath/libssl.dylib", "/opt/homebrew/lib/libetpan.dylib",
                        "/usr/library/evil.dylib", "/System/Library-evil/lib.dylib"):
            self.env["OTOOL"] = "\t" + library + " (compatibility version 1.0.0)"
            self.run_step("verify universal binary", success=False)

    def test_resource_and_fresh_metadata_reject_drift(self):
        self.build()
        for suffix in ("Resources/manifest.json", "Resources/constants.xlf", "Info.plist",
                       "Resources/English.lproj/InfoPlist.strings"):
            path = self.checkout / CONTENTS / suffix
            saved = path.read_bytes()
            for data in (None, b"", b"corrupted"):
                with self.subTest(suffix=suffix, data=data):
                    if data is None:
                        path.unlink()
                    else:
                        path.write_bytes(data)
                    self.run_step("verify universal binary", success=False)
                    path.write_bytes(saved)
        path = self.checkout / CONTENTS / "Info.plist"
        path.write_bytes(plistlib.dumps({"CFBundleShortVersionString": "999.0.0"}))
        self.run_step("verify universal binary", success=False)

    def test_exact_windows_artifact_no_recursive_fallback(self):
        (self.checkout / "winbuild/etpan.4DX").unlink()
        self.write_at("winbuild/nested/etpan.4DX", b"decoy")
        self.run_step("merge Windows binaries into the bundle", success=False)
        self.write_at("winbuild/etpan.4DX", b"")
        self.run_step("merge Windows binaries into the bundle", success=False)
        (self.checkout / "winbuild/etpan.4DX").unlink()
        (self.checkout / "winbuild/etpan.4DX").symlink_to(self.checkout / "winbuild/nested/etpan.4DX")
        self.run_step("merge Windows binaries into the bundle", success=False)

    def test_actual_credentials_use_only_synthetic_isolated_keychain(self):
        self.run_step("import Developer ID certificate")
        self.run_step("store notarytool credentials")
        self.assertEqual((self.checkout / "certificate.p12").read_bytes(), b"offline-p12")
        calls = self.calls()
        self.assertTrue(any(c[0:2] == ["security", "set-key-partition-list"] for c in calls))
        self.assertTrue(any(c[0:3] == ["xcrun", "notarytool", "store-credentials"] for c in calls))

    def test_strict_sign_notary_and_staple_success(self):
        result = self.pipeline()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.calls()
        sign = next(i for i, c in enumerate(calls) if c[0] == "codesign" and "--sign" in c)
        package = next(i for i, c in enumerate(calls) if c[0] == "ditto")
        staple = next(i for i, c in enumerate(calls) if c[:3] == ["xcrun", "stapler", "staple"])
        publish = next(i for i, c in enumerate(calls) if c[0] == "python3" and c[2] == "publish")
        self.assertLess(sign, package)
        self.assertLess(package, staple)
        self.assertLess(staple, publish)
        final_verify = max(i for i, c in enumerate(calls) if c[0] == "codesign" and "--verify" in c)
        self.assertLess(staple, final_verify)
        self.assertLess(final_verify, publish)
        self.assertEqual(sum(c[:3] == ["xcrun", "notarytool", "submit"] for c in calls), 2)
        for c in calls:
            if c[0] == "codesign" and "--verify" in c:
                self.assertIn("--strict", c)
                self.assertIn("--deep", c)
        self.assertEqual((self.checkout / CONTENTS / "_CodeSignature/CodeResources").read_bytes(),
                         b"fresh-signature")

    def test_all_native_failure_paths_never_publish(self):
        cases = [{"FAIL_TOOL": tool} for tool in ("base64", "security", "xcrun", "xcodebuild",
                                                 "lipo", "otool", "codesign", "ditto", "hdiutil")]
        cases += [{"FAIL_PREFLIGHT": "1"}, {"MISSING_IDENTITY": "1"}, {"FAIL_VERIFY": "1"},
                  {"MISDIRECTED_BUILD": "1"}, {"ARCHES": "arm64e x86_64"},
                  {"DYLIB_ARCHES": "arm64 x86_64h"}, {"OTOOL": "\t@rpath/evil.dylib"},
                  {"NOTARY_EXIT": "5", "NOTARY_STATUS": "Accepted"},
                  {"FAIL_DMG_NOTARY": "1"}, {"FAIL_VERIFY_AT": "2"},
                  *({"NOTARY_STATUS": s} for s in ("Invalid", "In Progress", "missing", "malformed")),
                  {"STAPLE_EXIT": "1"}]
        baseline = dict(self.env)
        for case in cases:
            with self.subTest(case=case):
                self.reset_artifacts()
                self.log.unlink(missing_ok=True)
                self.env = {**baseline, **case}
                result = self.pipeline()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertFalse(any(c[0] == "python3" and len(c) > 2 and c[2] == "publish"
                                     for c in self.calls()))

    def test_missing_dependency_stops_before_credentials(self):
        (self.checkout / "a/libssl.a").unlink()
        result = self.pipeline()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0] in ("security", "xcodebuild", "codesign") for c in self.calls()))

    def test_actual_powershell_cleanup_failure_and_normalization(self):
        self.write_at(native.WINDOWS_OUTPUT, b"fresh-msbuild")
        self.run_step("normalize windows output to canonical case", "build-windows")
        self.assertEqual((self.checkout / native.WINDOWS_BINARY).read_bytes(), b"fresh-msbuild")
        self.run_step("clean stale outputs", "build-windows")
        self.assertFalse((self.checkout / native.WINDOWS_OUTPUT).exists())
        self.write_at("wrong/nested/etpan.4DX", b"decoy")
        self.run_step("normalize windows output to canonical case", "build-windows", success=False)
        self.write_at(native.WINDOWS_OUTPUT, b"")
        self.run_step("normalize windows output to canonical case", "build-windows", success=False)
        self.write_at(native.WINDOWS_OUTPUT, b"fresh-msbuild")
        self.env["FAIL_TOOL"] = "python3"
        self.run_step("clean stale outputs", "build-windows", success=False)
        self.assertTrue((self.checkout / native.WINDOWS_OUTPUT).exists())

    def test_powershell_copy_failure_is_fatal(self):
        self.write_at(native.WINDOWS_OUTPUT, b"fresh-msbuild")
        # Force the copy branch even on case-insensitive APFS, then inject an
        # ordinary PowerShell I/O error (never invoke an external native tool).
        prefix = r'''
function Resolve-Path {
  [CmdletBinding()] param([string]$LiteralPath)
  if ($LiteralPath -cmatch '/Plugins/') {
    [pscustomobject]@{ Path = "different-canonical-path" }
  } else {
    Microsoft.PowerShell.Management\Resolve-Path @PSBoundParameters
  }
}
function Copy-Item { throw "offline copy failure" }
'''
        result = self.run_step("normalize windows output to canonical case", "build-windows",
                               success=False, prefix=prefix)
        self.assertIn("offline copy failure", result.stderr)

    def test_powershell_symlink_rejected_without_copy(self):
        target = self.write_at("unrelated/payload", b"keep")
        output = self.checkout / native.WINDOWS_OUTPUT
        output.parent.mkdir(parents=True, exist_ok=True)
        output.symlink_to(target)
        self.run_step("normalize windows output to canonical case", "build-windows", success=False)
        self.run_step("clean stale outputs", "build-windows", success=False)
        self.assertEqual(target.read_bytes(), b"keep")


class NativeContractTests(unittest.TestCase):
    def test_manual_immutable_cross_ref_workflow(self):
        workflow = yaml.load(WORKFLOW.read_bytes(), Loader=yaml.BaseLoader)
        self.assertEqual(workflow["name"], "Build")
        self.assertEqual(workflow["on"], {"workflow_dispatch": ""})
        self.assertEqual(workflow["concurrency"],
                         {"group": "release-publication", "cancel-in-progress": "false"})
        self.assertEqual(set(workflow["jobs"]), {"version", "build-windows", "build-macos"})
        self.assertEqual(workflow["jobs"]["build-macos"]["needs"], ["version", "build-windows"])
        for job in workflow["jobs"].values():
            self.assertNotIn("if", job)
            checkout = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@"))
            self.assertEqual(checkout["with"]["ref"], "${{ github.sha }}")
        for job in ("build-windows", "build-macos"):
            runs = [s for s in workflow["jobs"][job]["steps"] if "run" in s]
            self.assertIn("release.py preflight", runs[0]["run"])
            self.assertIn('--sha "$GITHUB_SHA"', runs[0]["run"])
        self.assertIn("release.py preflight", workflow["jobs"]["version"]["steps"][-1]["run"])
        self.assertIn("release.py publish", workflow["jobs"]["build-macos"]["steps"][-1]["run"])

    def test_native_topology_dependencies_cache_and_cmd_preserved(self):
        before = yaml.load(original(".github/workflows/release.yml"), Loader=yaml.BaseLoader)
        after = yaml.load(WORKFLOW.read_bytes(), Loader=yaml.BaseLoader)
        for job in before["jobs"]:
            self.assertEqual(before["jobs"][job]["runs-on"], after["jobs"][job]["runs-on"])
            for step in before["jobs"][job]["steps"]:
                if step.get("name") in (
                    "restore prebuilt libraries", "build prebuilt libraries (cache miss)",
                    "save prebuilt libraries", "build x64", "upload windows binaries",
                    "download windows binaries", "import Developer ID certificate",
                ):
                    actual = next(s for s in after["jobs"][job]["steps"]
                                  if s.get("name") == step["name"])
                    self.assertEqual(actual, step)
        self.assertEqual(after["env"]["MACOS_DEPLOYMENT_TARGET"], "11.5")
        for path in ("etpan.vcxproj", "scripts/build-macos-deps.sh", "scripts/build-windows-deps.ps1",
                     "manifest.json", "constants.xlf",
                     str(CONTENTS / "Info.plist"),
                     str(CONTENTS / "Resources/English.lproj/InfoPlist.strings"),
                     str(CONTENTS / "Windows64/etpan.4DX")):
            self.assertEqual((ROOT / path).read_bytes(), original(path), path)


if __name__ == "__main__":
    unittest.main()
