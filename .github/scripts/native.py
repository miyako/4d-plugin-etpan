"""Etpan's exact native outputs; never invalidate a bundle or resource sibling."""

import argparse
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess


PRODUCT = "etpan"
PLUGINS = Path("etpan.4dbase/Plugins")
BUNDLE = PLUGINS / "etpan.bundle"
CONTENTS = BUNDLE / "Contents"
WINDOWS_OUTPUT = Path("etpan.4dbase/plugins/etpan.bundle/contents/windows64/etpan.4DX")
WINDOWS_BINARY = CONTENTS / "Windows64/etpan.4DX"
OUTPUT_BUNDLES = (BUNDLE, PLUGINS / "Default/etpan.bundle")
MAC_FILES = tuple(bundle / relative for bundle in OUTPUT_BUNDLES for relative in (
    "Contents/MacOS/etpan", "Contents/Info.plist",
    "Contents/Resources/English.lproj/InfoPlist.strings",
))
MAC_DIRECTORIES = (
    *(bundle / "Contents/_CodeSignature" for bundle in OUTPUT_BUNDLES),
    Path("build/etpan.build"),
    PLUGINS / "etpan.build",
    PLUGINS / "Default/etpan.build",
)
XC_DATABASES = tuple(Path("build/XCBuildData") / name for name in (
    "build.db", "build.db-wal", "build.db-shm",
))
DEPENDENCY_FILES = (
    *(Path("a") / f"{name}.a" for name in ("libetpan", "libssl", "libcrypto")),
    *(Path("lib/windows64") / f"{name}.lib" for name in ("libetpan", "libssl", "libcrypto")),
    Path("include/mac/libetpan.h"),
)
DEPENDENCY_DIRECTORIES = (
    Path("include/mac/libetpan"), Path("include/windows/libetpan"),
    Path("build/deps"), Path("build/deps-win"),
)


def generated(path):
    """Publication exclusions are scoped to this project, not all of build/."""
    value = str(path)
    if "\\" in value or PurePosixPath(value).as_posix() != value:
        return False
    parts = PurePosixPath(value).parts
    if not parts or PurePosixPath(value).is_absolute() or any(p in (".", "..") for p in parts):
        return False
    files = (*MAC_FILES, *XC_DATABASES, *DEPENDENCY_FILES, WINDOWS_BINARY,
             WINDOWS_OUTPUT, Path("winbuild/etpan.4DX"))
    directories = (*MAC_DIRECTORIES, *DEPENDENCY_DIRECTORIES, Path("Objs/Release"))
    return (value in set(map(str, files))
            or any(value.startswith(str(directory) + "/") for directory in directories)
            or re.fullmatch(r"build/XCBuildData/[0-9a-f]{32}\.xcbuilddata/.+", value) is not None)


def is_link(path):
    return path.is_symlink() or (
        path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & 0x400
    )


def validate_paths(paths):
    root = Path.cwd().resolve()
    for path in paths:
        for parent in (path, *path.parents):
            if parent == Path("."):
                break
            if is_link(parent):
                raise ValueError(f"Refusing symlink output: {parent}")
        if not path.resolve().is_relative_to(root):
            raise ValueError(f"Output escapes checkout: {path}")
        if path.is_dir():
            for child in path.rglob("*"):
                if is_link(child):
                    raise ValueError(f"Refusing symlink output: {child}")


def prepare(platform):
    if platform == "macos":
        files = (*MAC_FILES, *XC_DATABASES)
        directories = MAC_DIRECTORIES
    else:
        files = (WINDOWS_OUTPUT, WINDOWS_BINARY)
        directories = (Path("Objs/Release"),)
    validate_paths((*files, *directories))
    for path in files:
        path.unlink(missing_ok=True)
    for path in directories:
        if path.exists():
            shutil.rmtree(path)


def require_file(path):
    validate_paths((path,))
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Expected nonempty native output: {path}")


def architectures(path):
    require_file(path)
    result = subprocess.run(["lipo", "-archs", str(path)], check=True,
                            capture_output=True, text=True)
    tokens = set(result.stdout.split())
    if not {"arm64", "x86_64"} <= tokens or "i386" in tokens:
        raise ValueError(f"Invalid universal architectures for {path}: {sorted(tokens)}")


def verify(version):
    import source_version

    binary = CONTENTS / "MacOS/etpan"
    architectures(binary)
    libraries = subprocess.run(["otool", "-L", str(binary)], check=True,
                               capture_output=True, text=True).stdout
    for line in libraries.splitlines():
        if not line.strip() or line.endswith(":"):
            continue
        if not re.match(r"^\s+(/usr/lib/|/System/Library/)", line):
            raise ValueError(f"Non-system runtime dependency: {line}")
    for library in (CONTENTS / "MacOS").glob("*.dylib"):
        architectures(library)
    for name in ("manifest.json", "constants.xlf"):
        source = Path(name)
        destination = CONTENTS / "Resources" / name
        if name == "manifest.json" or source.exists():
            require_file(destination)
            if destination.read_bytes() != source.read_bytes():
                raise ValueError(f"Copied resource differs from source: {destination}")
    if source_version.read() != version:
        raise ValueError("Selected source version changed during native build")
    source_version.verify_bundle(BUNDLE, Path.cwd())


def merge_windows():
    source = Path("winbuild/etpan.4DX")
    require_file(source)
    validate_paths((WINDOWS_BINARY,))
    WINDOWS_BINARY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, WINDOWS_BINARY)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare-macos", "prepare-windows",
                                            "verify", "merge-windows"))
    parser.add_argument("--version")
    args = parser.parse_args()
    if args.command.startswith("prepare-"):
        prepare(args.command.removeprefix("prepare-"))
    elif args.command == "merge-windows":
        merge_windows()
    else:
        if not args.version:
            parser.error("verify requires --version")
        verify(args.version)


if __name__ == "__main__":
    main()
