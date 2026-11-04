#!/bin/bash
# Builds the static libraries the Xcode project links from a/, as universal
# (arm64 + x86_64) archives, from pinned sources:
#   OpenSSL  -> a/libssl.a, a/libcrypto.a
#   libetpan -> a/libetpan.a, headers in include/mac/libetpan
# libetpan uses the system Cyrus SASL (/usr/lib/libsasl2), zlib and iconv,
# so the plugin also links -lsasl2 -lz -liconv. curl, expat, Berkeley DB and
# GnuTLS are disabled: the plugin only sends mail over SMTP.
#
# usage: scripts/build-macos-deps.sh [output-dir]   (default: a/)
# WORK (default build/deps) holds the per-arch builds; a rerun reuses them.
# Needs: Xcode command line tools, git, perl, autoconf, automake, libtool.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/a}"
WORK="${WORK:-$ROOT/build/deps}"
MIN="${MACOSX_DEPLOYMENT_TARGET:-11.5}"
JOBS="$(sysctl -n hw.ncpu)"

OPENSSL_TAG=openssl-3.5.9                                  # 3.5 LTS (long-term support), 2026-09-29
LIBETPAN_TAG=1.10.1                                        # 2026-06-14
LIBETPAN_SHA=e02145e4fb755eae44b3acfdc8067b05bf7904ef

# keep Homebrew headers and libraries out of the build
unset CPATH LIBRARY_PATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH
export PKG_CONFIG_LIBDIR=/nonexistent PKG_CONFIG_PATH=

# run <log file> <command...>: keep the output in the log, show its end
# (and configure's own log, when there is one) if the command fails
run() {
  local log="$1"; shift
  if ! "$@" >"$log" 2>&1; then
    echo "::error::$* failed, end of $log:" >&2
    tail -n 60 "$log" >&2
    for c in config.log ffbuild/config.log; do
      [ -f "$c" ] && { echo "--- end of $(pwd)/$c:" >&2; tail -n 80 "$c" >&2; }
    done
    return 1
  fi
}

# fetch <repo url> <commit sha or tag> <dir>
fetch() {
  # skip only a completed checkout (a failed fetch leaves an empty repo behind)
  if git -C "$3" rev-parse -q --verify HEAD >/dev/null 2>&1; then
    return 0
  fi
  mkdir -p "$3"
  git -C "$3" init -q
  local i
  for i in 1 2 3; do
    git -C "$3" fetch -q --depth 1 "$1" "$2" && break
    [ "$i" = 3 ] && return 1
    echo "fetch $1 failed, retrying"; sleep 10
  done
  git -C "$3" checkout -q FETCH_HEAD
}

SRC="$WORK/src"
fetch https://github.com/openssl/openssl.git "refs/tags/$OPENSSL_TAG" "$SRC/openssl"
fetch https://github.com/dinhvh/libetpan.git "$LIBETPAN_SHA" "$SRC/libetpan"

if [ ! -x "$SRC/libetpan/configure" ]; then
  (cd "$SRC/libetpan" && NOCONFIGURE=1 ./autogen.sh)
fi

build_arch() {
  local ARCH="$1" HOST TARGET
  case "$ARCH" in
    arm64)  HOST=aarch64-apple-darwin; TARGET=darwin64-arm64-cc ;;
    x86_64) HOST=x86_64-apple-darwin;  TARGET=darwin64-x86_64-cc ;;
  esac
  local D="$WORK/$ARCH"
  local SDK; SDK="$(xcrun --sdk macosx --show-sdk-path)"
  local FLAGS="-arch $ARCH -mmacosx-version-min=$MIN -isysroot $SDK"
  mkdir -p "$D"

  # OpenSSL: static only, no config file outside the bundle is read
  if [ ! -f "$D/openssl/lib/libcrypto.a" ]; then
    rm -rf "$D/openssl-build"
    rsync -a --exclude .git "$SRC/openssl/" "$D/openssl-build/"
    (cd "$D/openssl-build" &&
      run "$D/openssl-configure.log" ./Configure "$TARGET" no-shared no-tests no-docs no-apps \
        --prefix="$D/openssl" --openssldir=/var/empty/ssl --libdir=lib \
        "-mmacosx-version-min=$MIN" &&
      run "$D/openssl-make.log" make -j"$JOBS" &&
      run "$D/openssl-install.log" make install_sw)
  fi

  # libetpan: static, OpenSSL above, system SASL/zlib/iconv
  if [ ! -f "$D/libetpan/lib/libetpan.a" ]; then
    rm -rf "$D/libetpan-build"
    rsync -a --exclude .git "$SRC/libetpan/" "$D/libetpan-build/"
    (cd "$D/libetpan-build" &&
      run "$D/libetpan-configure.log" env CC=clang CFLAGS="$FLAGS -O2" LDFLAGS="$FLAGS" \
      ./configure --host="$HOST" --prefix="$D/libetpan" \
        --disable-shared --enable-static \
        --with-openssl="$D/openssl" --with-sasl=yes --without-gnutls \
        --disable-db --with-curl=no --with-expat=no --disable-lockfile &&
      grep -q '^#define USE_SSL 1' config.h &&
      grep -q '^#define USE_SASL 1' config.h &&
      run "$D/libetpan-make.log" make -j"$JOBS" &&
      run "$D/libetpan-install.log" make install)
  fi
}

build_arch arm64
build_arch x86_64

mkdir -p "$OUT"
for lib in libetpan:libetpan libssl:openssl libcrypto:openssl; do
  name="${lib%%:*}"; pkg="${lib##*:}"
  lipo -create "$WORK/arm64/$pkg/lib/$name.a" "$WORK/x86_64/$pkg/lib/$name.a" -output "$OUT/$name.a"
done

# headers (libetpan-config.h is generated per platform, so mac and windows differ)
rm -rf "$ROOT/include/mac/libetpan"
mkdir -p "$ROOT/include/mac"
cp -R "$WORK/arm64/libetpan/include/libetpan" "$ROOT/include/mac/libetpan"
cp "$WORK/arm64/libetpan/include/libetpan.h" "$ROOT/include/mac/libetpan.h" 2>/dev/null || true

for f in "$OUT"/libetpan.a "$OUT"/libssl.a "$OUT"/libcrypto.a; do
  archs="$(lipo -archs "$f")"
  echo "$f: $archs"
  case " $archs " in *" arm64 "*) ;; *) echo "missing arm64 in $f" >&2; exit 1 ;; esac
  case " $archs " in *" x86_64 "*) ;; *) echo "missing x86_64 in $f" >&2; exit 1 ;; esac
done
