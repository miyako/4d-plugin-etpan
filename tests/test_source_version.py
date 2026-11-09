"""Byte-preserving coordinated metadata tests against immutable intake and live source."""

from pathlib import Path
import plistlib
import re
import stat
import subprocess
import sys
from unittest.mock import patch

from helper_support import Fixture, ROOT, INTAKE, original, source


class SourceVersionTests(Fixture):
    def setUp(self):
        super().setUp()
        self.sources()
        self.version = source.read(self.root)

    def snapshot(self):
        return {path: ((self.root / path).read_bytes(), stat.S_IMODE((self.root / path).stat().st_mode))
                for path in source.SOURCE_PATHS if (self.root / path).exists()}

    def reject(self):
        before = self.snapshot()
        with patch.object(Path, "write_bytes") as write:
            with self.assertRaises((ValueError, UnicodeError, OSError)):
                source.read(self.root)
            with self.assertRaises((ValueError, UnicodeError, OSError)):
                source.bump("patch", self.root)
        write.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def modify(self, path, transform):
        target = self.root / path
        target.write_bytes(transform(target.read_bytes()))

    def plist(self, **fields):
        target = self.root / source.PLIST
        data = plistlib.loads(target.read_bytes())
        data.update(fields)
        target.write_bytes(plistlib.dumps(data))

    def test_exact_intake_authority_and_serialization(self):
        self.assertEqual(INTAKE, "1b81b7977f009889fab154879d3793b4234a6c02")
        self.assertEqual(source.SETTING_COUNT, 3)
        data = original(source.LOCALIZED)
        self.assertIn(b"\r", data)
        self.assertNotIn(b"\n", data)
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r", original(source.PLIST))
        plist = plistlib.loads(original(source.PLIST))
        self.assertEqual(plist[source.SHORT], "1.1.0")
        self.assertNotIn(source.BUILD, plist)
        fields = source.project_settings(original(source.PROJECT).decode())
        for key in source.KEYS:
            version = "1.1.0" if key == "MARKETING_VERSION" else "1.0.0"
            self.assertEqual([value for value, _, _ in fields[key]], [version] * 3)
        self.assertIn(b'CFBundleShortVersionString = "1.0";', data)
        self.assertIn(b"etpan version 1.0, Copyright 2017 miyako.", data)

    def test_explicit_intake_policy_and_narrow_source_alignment(self):
        header = original(".github/workflows/bump-version.yml").decode()
        self.assertIn("MARKETING_VERSION/CURRENT_PROJECT_VERSION AND Info.plist", header)
        self.assertIn("CFBundleShortVersionString/CFBundleVersion", header)
        version = source.read(ROOT).encode()
        for path in source.SOURCE_PATHS:
            expected = original(path)
            if path == source.PROJECT:
                expected = expected.replace(
                    b"MARKETING_VERSION = 1.1.0;", b"MARKETING_VERSION = " + version + b";"
                ).replace(
                    b"CURRENT_PROJECT_VERSION = 1.0.0;",
                    b"CURRENT_PROJECT_VERSION = " + version + b";",
                )
            elif path == source.PLIST:
                expected = expected.replace(b"<string>1.1.0</string>",
                                            b"<string>" + version + b"</string>")
            else:
                expected = expected.replace(
                    b'CFBundleShortVersionString = "1.0";',
                    b'CFBundleShortVersionString = "' + version + b'";',
                ).replace(b"etpan version 1.0,", b"etpan version " + version + b",")
            self.assertEqual((ROOT / path).read_bytes(), expected, path)

    def test_original_native_resource_copy_and_configuration_names(self):
        project = original(source.PROJECT).decode()
        self.assertIn("path = English.lproj/InfoPlist.strings;", project)
        self.assertIn("lastKnownFileType = text.plist.strings;", project)
        self.assertIn("/* InfoPlist.strings in Resources */", project)
        self.assertIn("isa = PBXResourcesBuildPhase;", project)
        self.assertIn("isa = PBXVariantGroup;", project)
        self.assertIn("INFOPLIST_FILE = Info.plist;", project)
        for name in ("Development", "Deployment", "Default"):
            self.assertEqual(project.count(f"name = {name};"), 2)

    def test_live_and_stable_all_bump_modes_exact_bytes_modes_and_absence(self):
        for version in (self.version, "3.2.1"):
            for mode in ("major", "minor", "patch"):
                with self.subTest(version=version, mode=mode):
                    self.sources()
                    for path in source.SOURCE_PATHS:
                        self.modify(path, lambda data: data.replace(self.version.encode(), version.encode()))
                        (self.root / path).chmod(0o750)
                    before = self.snapshot()
                    parts = list(map(int, version.split(".")))
                    index = ("major", "minor", "patch").index(mode)
                    parts[index] += 1
                    parts[index + 1:] = [0] * (2 - index)
                    expected = ".".join(map(str, parts))
                    self.assertEqual(source.bump(mode, self.root), expected)
                    self.assertEqual(source.read(self.root), expected)
                    for path, (raw, filemode) in before.items():
                        self.assertEqual((self.root / path).read_bytes(),
                                         raw.replace(version.encode(), expected.encode()))
                        self.assertEqual(stat.S_IMODE((self.root / path).stat().st_mode), filemode)
                    self.assertNotIn(source.BUILD, plistlib.loads((self.root / source.PLIST).read_bytes()))

    def test_canonical_versions_missing_extra_drift_and_cycles_never_write(self):
        for key in source.KEYS:
            for value in ("1.2", "7", "01.2.3", "v1.2.3", "1.2.3-rc", "$(UNKNOWN)", "",
                          f"$({key})", f"${{{key}}}", "900.800.700"):
                with self.subTest(key=key, value=value):
                    self.sources()
                    self.modify(source.PROJECT, lambda data: data.replace(
                        f"{key} = {self.version};".encode(), f"{key} = {value};".encode(), 1))
                    self.reject()
            self.sources()
            self.modify(source.PROJECT, lambda data: data.replace(
                f"{key} = {self.version};".encode(), b"", 1))
            self.reject()
            self.sources()
            self.modify(source.PROJECT, lambda data: data + f"\n{key} = {self.version};".encode())
            self.reject()
        self.sources()
        self.modify(source.PROJECT, lambda data: data.replace(
            f"MARKETING_VERSION = {self.version};".encode(),
            b"MARKETING_VERSION = $(CURRENT_PROJECT_VERSION);").replace(
            f"CURRENT_PROJECT_VERSION = {self.version};".encode(),
            b"CURRENT_PROJECT_VERSION = ${MARKETING_VERSION};"))
        self.reject()

    def test_duplicate_replacing_missing_assignment_still_rejected(self):
        for quoted in (False, True):
            self.sources()
            raw = (self.root / source.PROJECT).read_bytes()
            token = f"MARKETING_VERSION = {self.version};".encode()
            replacement = (f'"MARKETING_VERSION" = "{self.version}";' if quoted
                           else token.decode()).encode()
            first = raw.index(token)
            second = raw.index(token, first + len(token))
            raw = raw[:second] + raw[second:].replace(token, b"", 1)
            raw = raw[:first] + replacement + b" " + raw[first:]
            (self.root / source.PROJECT).write_bytes(raw)
            self.reject()

    def test_duplicates_after_other_inline_assignments_and_scope_mismatch(self):
        for key in source.KEYS:
            for quoted in (False, True):
                self.sources()
                name = f'"{key}"' if quoted else key
                self.modify(source.PROJECT, lambda raw: raw.replace(
                    f"{key} = {self.version};".encode(),
                    (f'OTHER = "not a version"; {name} = "{self.version}"; '
                     f"{key} = {self.version};").encode(), 1))
                self.reject()
        self.sources()
        token = f"CURRENT_PROJECT_VERSION = {self.version};".encode()
        self.modify(source.PROJECT, lambda raw: raw.replace(token, b"", 1) + token)
        self.reject()

    def test_quoted_inline_scoped_assignments_and_noise(self):
        value = self.version
        project = "/* ignored MARKETING_VERSION = 0.0.0; */\n{\n"
        for index in range(3):
            project += (f'config{index} = {{ OTHER = "CURRENT_PROJECT_VERSION = 9.9.9;"; '
                        f'"MARKETING_VERSION" = "{value}"; CURRENT_PROJECT_VERSION = {value}; }};\r\n')
        project += "}\n// MARKETING_VERSION = 8.8.8;\r"
        (self.root / source.PROJECT).write_bytes(project.encode())
        new = source.bump("patch", self.root)
        self.assertEqual((self.root / source.PROJECT).read_bytes(),
                         project.replace(value, new).encode())
        for noise in ("/* unterminated", '"unterminated', "}", "{"):
            self.sources()
            self.modify(source.PROJECT, lambda data: data + noise.encode())
            self.reject()

    def test_recursive_references_both_syntaxes_preserved(self):
        for referencing, target in (source.KEYS, tuple(reversed(source.KEYS))):
            for reference in (f"$({target})", f"${{{target}}}"):
                for quoted in (False, True):
                    self.sources()
                    replacement = f'"{reference}"' if quoted else reference
                    self.modify(source.PROJECT, lambda data: data.replace(
                        f"{referencing} = {self.version};".encode(),
                        f"{referencing} = {replacement};".encode()))
                    for plist_ref in source.REFERENCES:
                        self.plist(**{source.SHORT: plist_ref, source.BUILD: plist_ref})
                        new = source.bump("patch", self.root)
                        self.assertIn(reference.encode(), (self.root / source.PROJECT).read_bytes())
                        actual = plistlib.loads((self.root / source.PLIST).read_bytes())
                        self.assertEqual(actual[source.SHORT], plist_ref)
                        self.assertEqual(actual[source.BUILD], plist_ref)
                        self.assertEqual(source.read(self.root), new)
                        # Re-establish the selected fixture for the next reference.
                        self.sources()
                        self.modify(source.PROJECT, lambda data: data.replace(
                            f"{referencing} = {self.version};".encode(),
                            f"{referencing} = {replacement};".encode()))

    def test_required_short_optional_build_and_invalid_plist_zero_writes(self):
        for key in (source.SHORT, source.BUILD):
            for bad in (True, 123, [], {}, "", "$(UNKNOWN)", "01.2.3", "900.800.700"):
                self.sources()
                self.plist(**{key: bad})
                self.reject()
        for fields in ({}, {source.BUILD: self.version}):
            self.sources()
            (self.root / source.PLIST).write_bytes(plistlib.dumps(fields))
            self.reject()
        self.sources()
        self.plist(**{source.BUILD: self.version})
        new = source.bump("minor", self.root)
        self.assertEqual(plistlib.loads((self.root / source.PLIST).read_bytes())[source.BUILD], new)
        for raw in (b"not plist", plistlib.dumps([]),
                    plistlib.dumps({source.SHORT: self.version}, fmt=plistlib.FMT_BINARY)):
            self.sources()
            (self.root / source.PLIST).write_bytes(raw)
            self.reject()

    def test_missing_localized_keys_and_invalid_optional_build_never_write(self):
        for key in (source.SHORT, source.INFO):
            self.sources()
            value = source.text(self.root / source.LOCALIZED)
            value = re.sub(rf'{key}\s*=\s*"[^"]*";', "", value)
            (self.root / source.LOCALIZED).write_bytes(value.encode())
            self.reject()
        for value in ("01.2.3", "1.1", "1.1.0-beta", "$(UNKNOWN)", "900.800.700"):
            self.sources()
            self.modify(source.LOCALIZED, lambda raw: raw
                        + f'CFBundleVersion = "{value}";'.encode())
            self.reject()
        self.sources()
        self.modify(source.LOCALIZED, lambda raw: raw
                    + (f'CFBundleVersion = "{self.version}"; '
                       f'"CFBundleVersion" = "{self.version}";').encode())
        self.reject()

    def test_duplicate_xml_localized_keys_and_unknown_serialization(self):
        for key in (source.SHORT, source.BUILD, "CFBundleIdentifier"):
            self.sources()
            self.plist(**{key: self.version})
            self.modify(source.PLIST, lambda raw: raw.replace(
                b"</dict>", f"<key>{key}</key><string>{self.version}</string></dict>".encode()))
            self.reject()
        for key in (source.SHORT, source.INFO, "CFBundleName"):
            for quoted in (False, True):
                self.sources()
                token = f'"{key}"' if quoted else key
                self.modify(source.LOCALIZED, lambda raw: raw + f'{token} = "{self.version}";'.encode())
                self.reject()
        for old, new in (("Copyright 2017", "Copyright 2021"),
                         ("etpan version ", "Other Product version ")):
            self.sources()
            self.modify(source.LOCALIZED, lambda raw: raw.replace(old.encode(), new.encode()))
            self.reject()
        for raw in (b"broken", b'CFBundleShortVersionString = "unterminated'):
            self.sources()
            (self.root / source.LOCALIZED).write_bytes(raw)
            self.reject()

    def test_encoding_newlines_quotes_comments_unrelated_bytes(self):
        encodings = (("utf-8", b""), ("utf-8", b"\xef\xbb\xbf"),
                     ("utf-16-le", b"\xff\xfe"), ("utf-16-be", b"\xfe\xff"),
                     ("utf-16-le", b""), ("utf-16-be", b""))
        for codec, bom in encodings:
            for ending in ("\r", "\n", "\r\n", "mixed"):
                self.sources()
                originals = {}
                for path in source.SOURCE_PATHS:
                    value = source.text(self.root / path)
                    if path == source.PLIST and codec.startswith("utf-16"):
                        value = value.replace('encoding="UTF-8"', 'encoding="UTF-16"')
                    lines = value.splitlines()
                    value = "".join(line + (("\r", "\r\n", "\n")[i % 3]
                                            if ending == "mixed" else ending)
                                    for i, line in enumerate(lines))
                    raw = bom + value.encode(codec)
                    (self.root / path).write_bytes(raw)
                    originals[path] = raw
                new = source.bump("patch", self.root)
                for path, raw in originals.items():
                    self.assertEqual((self.root / path).read_bytes(),
                                     raw.replace(self.version.encode(codec), new.encode(codec)))
        self.sources()
        noise = f"<!-- <key>{source.SHORT}</key><string>9.9.9</string> -->"
        self.modify(source.PLIST, lambda raw: raw.replace(b"</dict>", noise.encode() + b"</dict>"))
        self.plist(**{"UnrelatedVersion": self.version})
        before = (self.root / source.PLIST).read_bytes()
        source.bump("patch", self.root)
        self.assertIn(f"<string>{self.version}</string>".encode(),
                      (self.root / source.PLIST).read_bytes())
        self.assertNotEqual(before, (self.root / source.PLIST).read_bytes())

    def test_missing_source_invalid_encoding_and_mode_never_write(self):
        for path in source.SOURCE_PATHS:
            self.sources()
            (self.root / path).unlink()
            self.reject()
            self.sources()
            (self.root / path).write_bytes(b"\xffbroken")
            self.reject()
        self.sources()
        before = self.snapshot()
        with self.assertRaises(ValueError):
            source.bump("other", self.root)
        self.assertEqual(before, self.snapshot())

    def test_candidate_revalidation_precedes_every_write(self):
        original_inspect = source.inspect_data
        calls = 0

        def validate(data):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("Reject rendered metadata")
            return original_inspect(data)

        before = self.snapshot()
        with patch.object(source, "inspect_data", side_effect=validate):
            with patch.object(Path, "write_bytes") as write:
                with self.assertRaises(ValueError):
                    source.mutate("patch", self.root)
                write.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_individual_source_encodings_and_unrelated_lexical_noise(self):
        encodings = (("utf-16-le", b""), ("utf-8", b"\xef\xbb\xbf"),
                     ("utf-16-be", b"\xfe\xff"))
        for path, (codec, bom) in zip(source.SOURCE_PATHS, encodings):
            value = source.text(self.root / path)
            (self.root / path).write_bytes(bom + value.encode(codec))
        value = source.text(self.root / source.PROJECT)
        noise = ('\r/* MARKETING_VERSION = 9.9.9; */\n'
                 'IGNORED = "CURRENT_PROJECT_VERSION = 8.8.8;";\r\n')
        (self.root / source.PROJECT).write_bytes((value + noise).encode("utf-16-le"))
        value = source.text(self.root / source.LOCALIZED)
        noise = ('\r// CFBundleShortVersionString = "9.9.9";\r'
                 'Other = "CFBundleVersion = \\"8.8.8\\";";\n')
        (self.root / source.LOCALIZED).write_bytes(b"\xfe\xff" + (value + noise).encode("utf-16-be"))
        before = self.snapshot()
        new = source.mutate("minor", self.root)
        self.assertEqual(source.inspect(self.root)[0], new)
        for (path, (codec, _)) in zip(source.SOURCE_PATHS, encodings):
            self.assertEqual((self.root / path).read_bytes(), before[path][0].replace(
                self.version.encode(codec), new.encode(codec)))

    def test_localized_version_references_and_optional_build_preserved(self):
        self.modify(source.LOCALIZED, lambda raw: raw.replace(
            f'{source.SHORT} = "{self.version}"'.encode(),
            f'{source.SHORT} = "$(MARKETING_VERSION)"'.encode())
            + b'CFBundleVersion = "${CURRENT_PROJECT_VERSION}";\r')
        source.bump("patch", self.root)
        raw = (self.root / source.LOCALIZED).read_bytes()
        self.assertIn(b'$(MARKETING_VERSION)', raw)
        self.assertIn(b'${CURRENT_PROJECT_VERSION}', raw)

    def test_built_binary_xml_utf16_metadata_and_optional_absence(self):
        bundle = self.root / "bundle"
        contents = bundle / "Contents"
        localized = contents / "Resources" / source.LOCALIZED
        localized.parent.mkdir(parents=True)
        expected = {key: value[0] for key, value in
                    source.localized_fields(source.text(self.root / source.LOCALIZED)).items()}
        for fmt in (plistlib.FMT_BINARY, plistlib.FMT_XML):
            (contents / "Info.plist").write_bytes(plistlib.dumps(
                {source.SHORT: self.version}, fmt=fmt))
            for style in ("strings", "utf-16", "utf-16-be", "xml", "binary"):
                if style in ("xml", "binary"):
                    raw = plistlib.dumps(expected, fmt=(
                        plistlib.FMT_XML if style == "xml" else plistlib.FMT_BINARY))
                else:
                    value = source.text(self.root / source.LOCALIZED)
                    raw = value.encode("utf-8" if style == "strings" else style)
                    if style == "utf-16-be":
                        raw = b"\xfe\xff" + raw
                localized.write_bytes(raw)
                source.verify_bundle(bundle, self.root)
                localized.write_bytes(plistlib.dumps({**expected, source.INFO: "wrong"}, fmt=fmt))
                with self.assertRaises(ValueError):
                    source.verify_bundle(bundle, self.root)
        localized.write_bytes(plistlib.dumps(expected))
        for data in ({}, [], {source.SHORT: self.version, source.BUILD: self.version},
                     {source.SHORT: "900.800.700"}):
            (contents / "Info.plist").write_bytes(plistlib.dumps(data))
            with self.assertRaises(ValueError):
                source.verify_bundle(bundle, self.root)
        (contents / "Info.plist").write_bytes(
            f'{source.SHORT} = "{self.version}";'.encode())
        with self.assertRaises(ValueError):
            source.verify_bundle(bundle, self.root)

    def test_built_resolved_references_optional_build_and_localization_fail_closed(self):
        self.plist(**{source.SHORT: "$(MARKETING_VERSION)",
                      source.BUILD: "${CURRENT_PROJECT_VERSION}"})
        self.modify(source.LOCALIZED, lambda raw: raw.replace(
            f'{source.SHORT} = "{self.version}"'.encode(),
            f'{source.SHORT} = "${{CURRENT_PROJECT_VERSION}}"'.encode())
            + b'CFBundleVersion = "$(MARKETING_VERSION)";')
        bundle = self.root / "built.bundle"
        info = bundle / "Contents/Info.plist"
        localized = bundle / "Contents/Resources" / source.LOCALIZED
        localized.parent.mkdir(parents=True)
        expected = {
            source.SHORT: self.version, source.BUILD: self.version,
            source.INFO: source.INFO_PREFIX + self.version + source.INFO_SUFFIX,
        }
        info.write_bytes(plistlib.dumps({source.SHORT: self.version, source.BUILD: self.version}))
        localized.write_bytes(plistlib.dumps(expected, fmt=plistlib.FMT_BINARY))
        source.validate_built(bundle, self.root)
        for fields in ({}, [], {source.SHORT: self.version}, {**expected, source.BUILD: "0.0.0"},
                       {**expected, source.SHORT: "$(MARKETING_VERSION)"},
                       {**expected, source.INFO: "wrong"}):
            localized.write_bytes(plistlib.dumps(fields))
            with self.assertRaises(ValueError):
                source.validate_built(bundle, self.root)
        localized.write_bytes(plistlib.dumps(expected))
        self.modify(localized, lambda raw: raw.replace(
            b"</dict>", f"<key>{source.SHORT}</key><string>{self.version}</string></dict>".encode()))
        with self.assertRaises(ValueError):
            source.validate_built(bundle, self.root)
        localized.write_bytes(plistlib.dumps(expected))
        for fields in ({source.SHORT: self.version}, {source.SHORT: self.version, source.BUILD: True},
                       {source.SHORT: self.version, source.BUILD: "$(CURRENT_PROJECT_VERSION)"}):
            info.write_bytes(plistlib.dumps(fields, fmt=plistlib.FMT_BINARY))
            with self.assertRaises(ValueError):
                source.validate_built(bundle, self.root)
        info.write_bytes(plistlib.dumps({source.SHORT: self.version, source.BUILD: self.version}))
        self.modify(info, lambda raw: raw.replace(
            b"</dict>", f"<key>{source.BUILD}</key><string>{self.version}</string></dict>".encode()))
        with self.assertRaises(ValueError):
            source.validate_built(bundle, self.root)

    def test_cli_dynamic_read_and_mutation(self):
        script = ROOT / ".github/scripts/source_version.py"
        result = subprocess.run([sys.executable, str(script)], cwd=self.root,
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), self.version)
        expected = source.mutate("patch", self.root)
        self.sources()
        result = subprocess.run([sys.executable, str(script), "--bump", "patch"],
                                cwd=self.root, capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), expected)
        self.assertEqual(source.read(self.root), expected)

    def test_prebuilt_native_dependency_and_4d_counters_untouched(self):
        excluded = {
            "etpan.4dbase/Plugins/etpan.bundle/Contents/Info.plist": b"old prebuilt",
            "etpan.4dbase/Plugins/etpan.bundle/Contents/Resources/English.lproj/InfoPlist.strings":
                b"\xff\xfeold prebuilt",
            "manifest.json": b'{"version":"1.0","id":20000}',
            "constants.xlf": b'<xliff version="1.0"/>',
            "etpan.4dbase/Project/Sources/catalog.4DCatalog": b"4D counter",
            "etpan.4dbase/Plugins/etpan.bundle/Contents/Windows64/etpan.4DX": b"stub",
            "a/library.a": b"dependency",
        }
        for path, raw in excluded.items():
            self.write(path, raw)
        source.bump("major", self.root)
        for path, raw in excluded.items():
            self.assertEqual((self.root / path).read_bytes(), raw)
