"""Etpan's exact native outputs; never invalidate a bundle or resource sibling."""

import argparse
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
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
DEPENDENCY_REPOSITORIES = tuple(map(Path, (
    "build/deps/src/openssl", "build/deps/src/libetpan",
    "build/deps-win/openssl", "build/deps-win/libetpan",
)))
LIBETPAN_BUILD_ROOTS = tuple(
    Path("build/deps") / architecture / "libetpan-build"
    for architecture in ("arm64", "x86_64")
)
# Public headers and Libtool targets at pinned libetpan e02145e4fb755eae44b3acfdc8067b05bf7904ef.
LIBETPAN_HEADERS = {
    ".": "libetpan-config.h",
    "src/data-types": (
        "mmapstring.h mailstream.h mailstream_helper.h mail.h mailstream_low.h "
        "mailstream_socket.h mailstream_ssl.h mailstream_cfstream.h mailstream_compress.h "
        "mailstream_types.h carray.h clist.h chash.h charconv.h mailsem.h maillock.h"
    ),
    "src/driver/implementation/data-message": "data_message_driver.h",
    "src/driver/implementation/db": "dbdriver.h dbdriver_message.h dbdriver_types.h dbstorage.h",
    "src/driver/implementation/feed": "feeddriver.h feeddriver_message.h feeddriver_types.h feedstorage.h",
    "src/driver/implementation/hotmail": "hotmailstorage.h",
    "src/driver/implementation/imap": (
        "imapdriver.h imapdriver_message.h imapdriver_cached.h imapdriver_cached_message.h "
        "imapdriver_types.h imapstorage.h imapdriver_tools.h imapdriver_tools_private.h"
    ),
    "src/driver/implementation/maildir": (
        "maildirdriver.h maildirdriver_cached.h maildirdriver_cached_message.h "
        "maildirdriver_message.h maildirdriver_types.h maildirstorage.h"
    ),
    "src/driver/implementation/mbox": (
        "mboxdriver.h mboxdriver_cached.h mboxdriver_cached_message.h "
        "mboxdriver_message.h mboxdriver_types.h mboxstorage.h"
    ),
    "src/driver/implementation/mh": (
        "mhdriver.h mhdriver_cached.h mhdriver_cached_message.h "
        "mhdriver_message.h mhdriver_types.h mhstorage.h"
    ),
    "src/driver/implementation/mime-message": "mime_message_driver.h",
    "src/driver/implementation/nntp": (
        "nntpdriver.h nntpdriver_cached.h nntpdriver_cached_message.h "
        "nntpdriver_message.h nntpdriver_types.h nntpstorage.h"
    ),
    "src/driver/implementation/pop3": (
        "pop3driver.h pop3driver_cached.h pop3driver_cached_message.h "
        "pop3driver_message.h pop3driver_types.h pop3storage.h"
    ),
    "src/driver/interface": (
        "maildriver.h maildriver_types.h maildriver_types_helper.h maildriver_errors.h "
        "mailmessage.h mailmessage_types.h mailstorage.h mailstorage_types.h mailfolder.h"
    ),
    "src/driver/tools": "generic_cache_types.h mailthread.h mailthread_types.h",
    "src/engine": (
        "mailengine.h mailprivacy.h mailprivacy_gnupg.h mailprivacy_smime.h "
        "mailprivacy_types.h mailprivacy_tools.h"
    ),
    "src/low-level/feed": "newsfeed_types.h newsfeed.h newsfeed_item.h newsfeed_item_enclosure.h",
    "src/low-level/imap": (
        "mailimap_helper.h mailimap.h mailimap_types.h mailimap_types_helper.h mailimap_socket.h "
        "mailimap_ssl.h mailimap_extension.h mailimap_extension_types.h annotatemore.h "
        "annotatemore_types.h acl.h acl_types.h uidplus.h uidplus_types.h quota.h quota_parser.h "
        "quota_sender.h quota_types.h idle.h namespace.h namespace_parser.h namespace_sender.h "
        "namespace_types.h xlist.h xgmlabels.h xgmmsgid.h xgmthrid.h mailimap_id.h "
        "mailimap_id_types.h enable.h condstore.h condstore_types.h qresync.h qresync_types.h "
        "mailimap_sort.h mailimap_sort_types.h mailimap_compress.h mailimap_oauth2.h clientid.h"
    ),
    "src/low-level/imf": (
        "mailimf.h mailimf_types.h mailimf_write_file.h mailimf_types_helper.h "
        "mailimf_write_generic.h mailimf_write_mem.h"
    ),
    "src/low-level/maildir": "maildir.h maildir_types.h",
    "src/low-level/mbox": "mailmbox.h mailmbox_types.h",
    "src/low-level/mh": "mailmh.h",
    "src/low-level/mime": (
        "mailmime.h mailmime_types.h mailmime_content.h mailmime_decode.h mailmime_disposition.h "
        "mailmime_write_file.h mailmime_types_helper.h mailmime_write_generic.h mailmime_write_mem.h"
    ),
    "src/low-level/nntp": "newsnntp.h newsnntp_socket.h newsnntp_ssl.h newsnntp_types.h",
    "src/low-level/pop3": "mailpop3.h mailpop3_socket.h mailpop3_helper.h mailpop3_ssl.h mailpop3_types.h",
    "src/low-level/smtp": (
        "mailsmtp.h mailsmtp_helper.h mailsmtp_socket.h mailsmtp_ssl.h mailsmtp_types.h mailsmtp_oauth2.h"
    ),
    "src/main": "libetpan.h libetpan_version.h",
}
LIBETPAN_LIBRARIES = {
    "src": "libetpan.la",
    "src/data-types": "libdata-types.la",
    "src/driver": "libdriver.la",
    "src/driver/implementation": "libimplementation.la",
    "src/driver/implementation/data-message": "libdata-message.la",
    "src/driver/implementation/db": "libdb.la",
    "src/driver/implementation/feed": "libfeed.la",
    "src/driver/implementation/hotmail": "libhotmail.la",
    "src/driver/implementation/imap": "libimap.la",
    "src/driver/implementation/maildir": "libmaildir.la",
    "src/driver/implementation/mbox": "libmbox.la",
    "src/driver/implementation/mh": "libmh.la",
    "src/driver/implementation/mime-message": "libmime-message.la",
    "src/driver/implementation/nntp": "libnntp.la",
    "src/driver/implementation/pop3": "libpop3.la",
    "src/driver/interface": "libinterface.la",
    "src/driver/tools": "libtools.la",
    "src/engine": "libengine.la",
    "src/low-level": "liblow-level.la",
    "src/low-level/feed": "libfeed.la",
    "src/low-level/imap": "libimap.la",
    "src/low-level/imf": "libimf.la",
    "src/low-level/maildir": "libmaildir.la",
    "src/low-level/mbox": "libmbox.la",
    "src/low-level/mh": "libmh.la",
    "src/low-level/mime": "libmime.la",
    "src/low-level/nntp": "libnntp.la",
    "src/low-level/pop3": "libpop3.la",
    "src/low-level/smtp": "libsmtp.la",
    "src/main": "libmain.la",
}
LIBETPAN_SYMLINKS = {
    Path("include/libetpan") / name: (Path(directory) / name, True)
    for directory, names in LIBETPAN_HEADERS.items() for name in names.split()
}
LIBETPAN_SYMLINKS.update({
    Path(directory) / ".libs" / name: (Path(directory) / name, False)
    for directory, name in LIBETPAN_LIBRARIES.items()
})


def dependency_repository(path):
    """Git reports these nested dependency checkouts as directory markers."""
    return str(path) in {str(directory) + "/" for directory in DEPENDENCY_REPOSITORIES}


def generated(path):
    """Publication exclusions are scoped to this project, not all of build/."""
    value = str(path)
    if dependency_repository(value):
        return True
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


def generated_symlink(path):
    """Validate only the pinned macOS dependency link farms, without rewriting bytes."""
    value = str(path)
    if "\\" in value or PurePosixPath(value).as_posix() != value:
        return False
    relative = Path(value)
    match = next(
        ((root, relative.relative_to(root)) for root in LIBETPAN_BUILD_ROOTS
         if relative.is_relative_to(root)),
        None,
    )
    if match is None or match[1] not in LIBETPAN_SYMLINKS:
        return False
    build_root, entry = match
    for ancestor in relative.parents:
        if is_link(ancestor):
            raise ValueError(f"Dependency link has a symlink ancestor: {ancestor}")
    if not relative.is_symlink():
        return False
    checkout = Path.cwd().resolve()
    target_relative, absolute = LIBETPAN_SYMLINKS[entry]
    target = checkout / build_root / target_relative
    expected = str(target) if absolute else "../" + target.name
    if os.readlink(relative) != expected:
        raise ValueError(f"Unexpected dependency symlink target: {relative}")
    for ancestor in (target, *target.parents):
        if is_link(ancestor):
            raise ValueError(f"Dependency link target has a symlink component: {ancestor}")
    if not stat.S_ISREG(target.lstat().st_mode):
        raise ValueError(f"Dependency link target is not a regular file: {target}")
    if relative.resolve(strict=True) != target or not target.is_relative_to(checkout / build_root):
        raise ValueError(f"Dependency link target escapes its build root: {relative}")
    return True


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


def architectures(path, *, reject_i386=False):
    require_file(path)
    result = subprocess.run(["lipo", "-archs", str(path)], check=True,
                            capture_output=True, text=True)
    tokens = set(result.stdout.split())
    if not {"arm64", "x86_64"} <= tokens or (reject_i386 and "i386" in tokens):
        raise ValueError(f"Invalid universal architectures for {path}: {sorted(tokens)}")


def verify(version):
    import source_version

    binary = CONTENTS / "MacOS/etpan"
    architectures(binary, reject_i386=True)
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
