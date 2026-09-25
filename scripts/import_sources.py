#!/usr/bin/env python3
"""Snapshot every theme advertised by a locally installed VS Code Noctis extension."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIGHT_ALIASES = {"hibernus": "Hibernus Light", "lilac": "Lilac Light", "lux": "Lux Light"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extension", type=Path, required=True)
    args = parser.parse_args()
    extension = args.extension.resolve()
    package = json.loads((extension / "package.json").read_text())
    assert package["publisher"] == "liviuschera" and package["name"] == "noctis"
    version = package["version"]
    output = ROOT / "reference" / f"noctis-{version}"
    output.mkdir(parents=True, exist_ok=True)
    catalog, hashes, seen = [], {}, set()
    for entry in package["contributes"]["themes"]:
        source = (extension / entry["path"]).resolve()
        source.relative_to(extension)
        stem = source.stem
        assert stem not in seen, stem
        seen.add(stem)
        shutil.copyfile(source, output / source.name)
        hashes[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
        # VS Code registers appearance through package.json uiTheme. Noctis
        # Lilac's JSON has a stale type=dark despite being registered as vs.
        appearance = {"vs": "light", "vs-dark": "dark"}[entry["uiTheme"]]
        aliases = []
        if stem in LIGHT_ALIASES:
            aliases.append({"file": f"{stem}-light.json", "name": LIGHT_ALIASES[stem]})
        catalog.append({"id": stem, "source": source.name, "name": entry["label"],
                        "appearance": appearance, "file": source.name, "aliases": aliases})
    shutil.copyfile(extension / "LICENSE.md", output / "LICENSE.md")
    metadata = {"noctis_version": version, "upstream": "https://github.com/liviuschera/noctis",
                "zed_version": "1.21.0", "files": hashes}
    (ROOT / "reference/sources.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (ROOT / "reference/theme-catalog.json").write_text(json.dumps(catalog, indent=2) + "\n")
    manifest = {"name": package["name"], "publisher": package["publisher"], "version": version,
                "contributes": {"themes": package["contributes"]["themes"]}}
    (output / "package-themes.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Snapshotted Noctis {version}: {len(catalog)} canonical themes.")


if __name__ == "__main__":
    main()
