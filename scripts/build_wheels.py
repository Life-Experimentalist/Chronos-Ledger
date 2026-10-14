#!/usr/bin/env python3
# Copyright 2026 Chronos Ledger Contributors (Apache 2.0)

"""Build platform wheels for PyPI out of the release assets.

chronos is a Rust program with no Python in it. It is on PyPI because that is where
`uv tool install`, `uvx` and `pipx` look. Each wheel is a zip carrying one prebuilt
executable (under both command names) and enough metadata to describe it.

The binaries go in `<name>-<version>.data/scripts/`, which installers unpack straight
into the environment's `bin` or `Scripts` directory. That needs no Python shim, no
compiler and no build backend.

Standard library only: this runs in the publish workflow between the release assets
and the upload, and a wheel builder with its own pip install step is one more thing
that can break a release.

Usage: python scripts/build_wheels.py <tag> <assets-dir> <out-dir>
  tag         the release tag, for example v0.18.0
  assets-dir  holds chronos-<tag>-<os>-<arch>[.exe] and a .sha256 file for each
  out-dir     receives the .whl files
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import re
import sys
import zipfile
from pathlib import Path

DIST_NAME = "chronosledger"
COMMANDS = ("chronos", "chronosledger")
SUMMARY = "Install, upgrade, back up and diagnose a Chronos Ledger server"
HOMEPAGE = "https://chronos.vkrishna04.me"
REPOSITORY = "https://github.com/Life-Experimentalist/Chronos-Ledger"
KEYWORDS = "chronos-ledger,scheduling,attendance,docker-compose,cli,self-hosted"

# (asset os, asset arch) -> platform tags for the wheel.
#
# The Linux binaries are static musl builds, so they need no libc at all. That meets
# the manylinux policy trivially and is the literal musllinux case, so one binary
# carries both tag families and Debian and Alpine users get a wheel from one asset.
TARGETS = {
    ("linux", "x64"): [
        "manylinux_2_17_x86_64",
        "manylinux2014_x86_64",
        "musllinux_1_1_x86_64",
    ],
    ("linux", "arm64"): [
        "manylinux_2_17_aarch64",
        "manylinux2014_aarch64",
        "musllinux_1_1_aarch64",
    ],
    # The floors match what the Rust targets support: x86_64-apple-darwin runs back to
    # 10.12, and Apple silicon Macs did not exist before 11.0.
    ("darwin", "x64"): ["macosx_10_12_x86_64"],
    ("darwin", "arm64"): ["macosx_11_0_arm64"],
    ("windows", "x64"): ["win_amd64"],
    ("windows", "arm64"): ["win_arm64"],
}

CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: Apache Software License",
    "Operating System :: MacOS",
    "Operating System :: Microsoft :: Windows",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Rust",
    "Topic :: System :: Systems Administration",
]


def absolutize_readme(readme: str, tag: str) -> str:
    """Point every relative link and image in the README at GitHub.

    PyPI renders the description as it is, so a relative link is a 404 on the project
    page. Rewriting here keeps the file readable in the repository, where the relative
    form is the correct one. Pinned to the tag, so the page for 0.18.0 shows 0.18.0.
    """
    raw = f"{REPOSITORY.replace('github.com', 'raw.githubusercontent.com')}/{tag}"
    blob = f"{REPOSITORY}/blob/{tag}"
    absolute = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#)")

    def rewrite(target: str, base: str) -> str:
        return target if absolute.match(target) else f"{base}/{target.removeprefix('./')}"

    # Images first, so the second pass sees them as already absolute.
    readme = re.sub(
        r"(!\[[^\]]*\]\()([^)\s]+)(\))",
        lambda m: m[1] + rewrite(m[2], raw) + m[3],
        readme,
    )
    readme = re.sub(
        r"(\]\()([^)\s]+)(\))",
        lambda m: m[1] + rewrite(m[2], blob) + m[3],
        readme,
    )
    return re.sub(
        r'(<img\s[^>]*?\bsrc=")([^"]+)(")',
        lambda m: m[1] + rewrite(m[2], raw) + m[3],
        readme,
    )


def urlsafe_b64_nopad(data: bytes) -> str:
    """The digest encoding PEP 427 specifies for RECORD: urlsafe base64, no padding."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def read_verified_binary(assets: Path, tag: str, os_name: str, arch: str) -> bytes:
    """Read one release asset and check it against its .sha256 sidecar."""
    suffix = ".exe" if os_name == "windows" else ""
    asset = assets / f"chronos-{tag}-{os_name}-{arch}{suffix}"
    sidecar = asset.with_name(asset.name + ".sha256")
    if not asset.is_file():
        raise SystemExit(f"missing asset: {asset}")
    if not sidecar.is_file():
        raise SystemExit(f"missing checksum: {sidecar}")
    data = asset.read_bytes()
    want = sidecar.read_text(encoding="utf-8").split()[0].lower()
    got = hashlib.sha256(data).hexdigest()
    if want != got:
        raise SystemExit(f"checksum mismatch for {asset}: expected {want}, got {got}")
    return data


def metadata(version: str, readme: str) -> str:
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {DIST_NAME}",
        f"Version: {version}",
        f"Summary: {SUMMARY}",
        "License: Apache-2.0",
        f"Keywords: {KEYWORDS}",
        f"Project-URL: Homepage, {HOMEPAGE}",
        f"Project-URL: Documentation, {REPOSITORY}/blob/v{version}/docs/cli.md",
        f"Project-URL: Source, {REPOSITORY}",
        f"Project-URL: Issues, {REPOSITORY}/issues",
        f"Project-URL: Changelog, {REPOSITORY}/blob/main/CHANGELOG.md",
    ]
    lines += [f"Classifier: {c}" for c in CLASSIFIERS]
    lines += [
        # Nothing in the wheel is executed by Python, so there is no floor worth naming
        # beyond a Python that understands modern wheel tags.
        "Requires-Python: >=3.8",
        "Description-Content-Type: text/markdown",
        "",
        readme,
    ]
    return "\n".join(lines)


def wheel_file(tags: list[str]) -> str:
    lines = [
        "Wheel-Version: 1.0",
        "Generator: chronosledger build_wheels.py",
        # False: the wheel is platform specific and holds no pure Python.
        "Root-Is-Purelib: false",
    ]
    lines += [f"Tag: py3-none-{tag}" for tag in tags]
    return "\n".join(lines) + "\n"


def build_wheel(
    out_dir: Path,
    version: str,
    tags: list[str],
    binary: bytes,
    exe_suffix: str,
    readme: str,
    license_text: str,
) -> Path:
    dist_info = f"{DIST_NAME}-{version}.dist-info"
    data_scripts = f"{DIST_NAME}-{version}.data/scripts"

    entries: list[tuple[str, bytes, int]] = []

    # Both names are real files, never a symlink: wheels cannot carry links, and an
    # install with only one name would make half the docs wrong.
    for name in COMMANDS:
        entries.append((f"{data_scripts}/{name}{exe_suffix}", binary, 0o755))

    entries.append((f"{dist_info}/METADATA", metadata(version, readme).encode(), 0o644))
    entries.append((f"{dist_info}/WHEEL", wheel_file(tags).encode(), 0o644))
    entries.append((f"{dist_info}/licenses/LICENSE", license_text.encode(), 0o644))

    record_rows = [
        (path, f"sha256={urlsafe_b64_nopad(hashlib.sha256(blob).digest())}", len(blob))
        for path, blob, _ in entries
    ]
    # RECORD cannot hash itself; PEP 427 gives its own row empty fields.
    record_rows.append((f"{dist_info}/RECORD", "", ""))
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(record_rows)
    entries.append((f"{dist_info}/RECORD", buf.getvalue().encode(), 0o644))

    path = out_dir / f"{DIST_NAME}-{version}-py3-none-{'.'.join(tags)}.whl"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, blob, mode in entries:
            # A fixed timestamp keeps the wheel byte-identical across rebuilds of the
            # same assets, so running a release again produces the same files.
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            # 0o100000 is S_IFREG. Without the file-type bits some extractors read the
            # entry as typeless and drop the permission bits with it, which would land
            # the binaries without the executable bit.
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, blob)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tag", help="release tag, for example v0.18.0")
    parser.add_argument("assets", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()

    if not re.fullmatch(r"v\d+\.\d+\.\d+", args.tag):
        raise SystemExit(f"tag must look like v1.2.3, got: {args.tag}")
    version = args.tag[1:]

    repo_root = Path(__file__).resolve().parent.parent
    readme = absolutize_readme(
        (repo_root / "cli" / "README.md").read_text(encoding="utf-8"), args.tag
    )
    license_text = (repo_root / "LICENSE").read_text(encoding="utf-8")

    args.out.mkdir(parents=True, exist_ok=True)

    for (os_name, arch), tags in TARGETS.items():
        path = build_wheel(
            out_dir=args.out,
            version=version,
            tags=tags,
            binary=read_verified_binary(args.assets, args.tag, os_name, arch),
            exe_suffix=".exe" if os_name == "windows" else "",
            readme=readme,
            license_text=license_text,
        )
        print(f"built {path.name} ({path.stat().st_size / 1024:.0f} KiB)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
