#!/usr/bin/env python3
"""Preview any generated Noctis theme in an isolated Zed profile (Zed 1.21+)."""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
catalog = json.loads((ROOT / "reference/theme-catalog.json").read_text())
choices = [entry["name"] for entry in catalog]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--theme", choices=choices, default="Noctis Lux")
parser.add_argument("--data-dir", type=Path, default=ROOT / "preview-data")
parser.add_argument("--rust-analyzer", type=Path, help="Use an existing language-server binary")
parser.add_argument("--zed-app", type=Path, help="Use a specific installed Zed app bundle")
parser.add_argument("--prepare-only", action="store_true")
args = parser.parse_args()
config = args.data_dir.resolve() / "config"
(config / "themes").mkdir(parents=True, exist_ok=True)
for entry in catalog:
    shutil.copyfile(ROOT / "themes" / entry["file"], config / "themes" / entry["file"])
# Remove aliases left by an earlier preview profile.
for old_name in ["hibernus-light.json", "lilac-light.json", "lux-light.json"]:
    (config / "themes" / old_name).unlink(missing_ok=True)
settings = {
    "semantic_tokens": "combined",
    "theme": args.theme,
    "buffer_font_family": "Iosevka Bugen",
    "buffer_font_size": 14,
    "disable_ai": True,
    "restore_on_startup": "none",
    "autosave": "off",
    "telemetry": {"metrics": False, "diagnostics": False},
}
if args.rust_analyzer:
    settings["lsp"] = {"rust-analyzer": {
        "binary": {"path": str(args.rust_analyzer.resolve())},
        "initialization_options": {"checkOnSave": False},
    }}
(config / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
command = ["zed", "--foreground", "--user-data-dir", str(args.data_dir.resolve()), "-n",
           str(ROOT / "examples/rust"), str(ROOT / "examples/rust/src/main.rs")]
if args.zed_app:
    command[1:1] = ["--zed", str(args.zed_app.resolve())]
print("Preview configuration:", config)
if not args.prepare_only:
    # macOS's single-instance check is bundle-based, even with a separate data
    # directory. Stateless mode permits a genuinely separate preview process.
    environment = dict(os.environ, ZED_STATELESS="1")
    with (args.data_dir / "preview.log").open("ab") as log:
        process = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=log, start_new_session=True)
    (args.data_dir / "preview.pid").write_text(str(process.pid) + "\n")
    print("Preview process:", process.pid)
