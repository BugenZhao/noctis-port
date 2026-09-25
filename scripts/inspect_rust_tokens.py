#!/usr/bin/env python3
"""Query real rust-analyzer semantic tokens and render the complete Noctis catalog."""
import argparse
import collections
import html
import json
import queue
import subprocess
import threading
import time
from pathlib import Path

import generate_themes as port


class Lsp:
    def __init__(self, binary, root, log):
        self.log = log.open("wb")
        self.process = subprocess.Popen([str(binary)], cwd=root, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=self.log)
        self.incoming = queue.Queue()
        self.serial = 0
        self.quiescent = False
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        stream = self.process.stdout
        try:
            while True:
                headers = {}
                while line := stream.readline():
                    if line == b"\r\n":
                        break
                    k, v = line.decode().split(":", 1)
                    headers[k.lower()] = v.strip()
                if not line:
                    return
                payload = stream.read(int(headers["content-length"]))
                self.incoming.put(json.loads(payload))
        except Exception as error:
            self.incoming.put({"reader_error": str(error)})

    def send(self, message):
        data = json.dumps({"jsonrpc": "2.0", **message}).encode()
        self.process.stdin.write(f"Content-Length: {len(data)}\r\n\r\n".encode() + data)
        self.process.stdin.flush()

    def notify(self, method, params):
        self.send({"method": method, "params": params})

    def handle(self, message):
        if message.get("method") == "experimental/serverStatus":
            self.quiescent = message.get("params", {}).get("quiescent", False)
        if "method" in message and "id" in message:
            result = None
            if message["method"] == "workspace/configuration":
                result = [None] * len(message.get("params", {}).get("items", []))
            self.send({"id": message["id"], "result": result})
        if "reader_error" in message:
            raise RuntimeError(message["reader_error"])

    def request(self, method, params, timeout=45):
        self.serial += 1
        request_id = self.serial
        self.send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message = self.incoming.get(timeout=max(0.01, deadline - time.monotonic()))
            if message.get("id") == request_id and "method" not in message:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result")
            self.handle(message)
        raise TimeoutError(method)

    def wait_for_workspace(self):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            try:
                message = self.incoming.get(timeout=min(1, deadline - time.monotonic()))
                self.handle(message)
            except queue.Empty:
                if self.quiescent:
                    return
        raise TimeoutError("rust-analyzer workspace load")

    def close(self):
        try:
            self.request("shutdown", None, timeout=5)
            self.notify("exit", None)
            self.process.wait(timeout=5)
        finally:
            if self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=5)
            self.log.close()


def zed_style(entries, token, modifiers):
    style = {}
    for entry in reversed(entries):
        if entry["token_type"] == token and set(entry["modifiers"]) <= set(modifiers):
            style.update(entry["style"])
    return style


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rust-analyzer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    root = port.ROOT / "examples/rust"
    path = root / "src/main.rs"
    source = path.read_text()
    client = Lsp(args.rust_analyzer, root, args.output.with_suffix(".lsp.log"))
    try:
        initialization = client.request("initialize", {
            "processId": None,
            "rootUri": root.as_uri(),
            "workspaceFolders": [{"uri": root.as_uri(), "name": "noctis-preview"}],
            "capabilities": {
                "window": {"workDoneProgress": True},
                "experimental": {"serverStatusNotification": True},
                "textDocument": {"semanticTokens": {
                    "requests": {"full": True}, "formats": ["relative"],
                    "tokenTypes": sorted(port.SEMANTICS["types"] | port.SEMANTICS["rust"]["types"]),
                    "tokenModifiers": ["declaration", "definition", "readonly", "static", "deprecated",
                                       "async", "documentation", "defaultLibrary", "constant", "mutable",
                                       "controlFlow", "public", "reference", "unsafe"],
                }},
            },
            "initializationOptions": {"checkOnSave": False},
        })
        client.notify("initialized", {})
        client.notify("textDocument/didOpen", {"textDocument": {
            "uri": path.as_uri(), "languageId": "rust", "version": 1, "text": source,
        }})
        client.wait_for_workspace()
        result = client.request("textDocument/semanticTokens/full", {"textDocument": {"uri": path.as_uri()}})
        legend = initialization["capabilities"]["semanticTokensProvider"]["legend"]
    finally:
        client.close()
    tokens = []
    line, column = 0, 0
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for text in lines:
        offsets.append(offsets[-1] + len(text))
    data = result["data"]
    for i in range(0, len(data), 5):
        dl, dc, length, kind, mask = data[i:i + 5]
        line += dl
        column = dc if dl else column + dc
        # Fixture text is ASCII, so byte, Python character and UTF-16 columns agree.
        assert source.isascii()
        start = offsets[line] + column
        modifiers = [m for bit, m in enumerate(legend["tokenModifiers"]) if mask & (1 << bit)]
        tokens.append({"start": start, "end": start + length, "text": source[start:start + length],
                       "type": legend["tokenTypes"][kind], "modifiers": modifiers})
    assert len(tokens) > 100, len(tokens)
    categories = collections.Counter(t["type"] for t in tokens)
    assert {"parameter", "property", "lifetime", "function", "keyword"} <= categories.keys(), categories

    panels = []
    summary = {"server": str(args.rust_analyzer), "token_count": len(tokens),
               "token_types": dict(categories), "theme_checks": {}, "native_zed_rendering": "not_verified"}
    for entry in port.CATALOG:
        variant = entry["id"]
        theme = json.loads((port.ROOT / "themes" / entry["file"]).read_text())["themes"][0]
        original = json.loads((port.SOURCE_DIR / entry["source"]).read_text())
        entries = port.semantic_entries(original, rust=True)
        parts, previous, mapped = [], 0, 0
        for token in tokens:
            assert token["start"] >= previous, "Overlapping tokens need a different renderer"
            parts.append(html.escape(source[previous:token["start"]]))
            actual = zed_style(entries, token["type"], token["modifiers"])
            expected, provenance = port.semantic_style(original, token["type"], token["modifiers"], rust=True)
            assert actual == expected, (variant, token, actual, expected)
            if actual:
                mapped += 1
            style = []
            for k, css in [("color", "color"), ("font_style", "font-style"), ("font_weight", "font-weight")]:
                if k in actual:
                    style.append(f"{css}:{actual[k]}")
            info = json.dumps({"token": token["text"], "type": token["type"], "modifiers": token["modifiers"],
                               "style": actual, "source": provenance}, ensure_ascii=False, indent=2)
            parts.append(f'<span tabindex="0" data-info="{html.escape(info, quote=True)}" style="{";".join(style)}">{html.escape(token["text"])}</span>')
            previous = token["end"]
        parts.append(html.escape(source[previous:]))
        s = theme["style"]
        panels.append(f'<section id="{variant}" class="theme" style="--bg:{s["editor.background"]};--fg:{s["editor.foreground"]};--bar:{s["tab_bar.background"]};--muted:{s["editor.line_number"]}"><h2>{theme["name"]}<small>Noctis {port.SOURCES["noctis_version"]} · {entry["appearance"]} · rust-analyzer semantic tokens</small></h2><pre>{"".join(parts)}</pre></section>')
        summary["theme_checks"][theme["name"]] = {"token_comparisons": len(tokens), "mapped_tokens": mapped, "mismatches": 0}
    buttons = "".join(f'<button data-theme="{e["id"]}">{html.escape(e["name"])}</button>' for e in port.CATALOG)
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Noctis semantic preview</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f5f5f4;color:#25252b;font:15px -apple-system,BlinkMacSystemFont,sans-serif}header{padding:20px 28px;border-bottom:1px solid #ddd}h1{font-size:22px;margin:0 0 8px}p{max-width:950px;line-height:1.5;margin:6px 0}nav{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}button{border:1px solid #bbb;background:white;padding:9px 15px;border-radius:7px;cursor:pointer}button.active{background:#25252b;color:white}main{display:grid;grid-template-columns:minmax(400px,1fr) 360px;gap:20px;padding:20px 28px}.theme{display:none;background:var(--bg);color:var(--fg);border:1px solid #ccc;border-radius:9px;overflow:hidden}.theme.active{display:block}h2{font-size:15px;background:var(--bar);margin:0;padding:14px 20px}small{display:block;font-size:11px;font-weight:400;margin-top:4px}pre{font:14px/1.6 'Iosevka Bugen',ui-monospace,monospace;margin:0;padding:20px;overflow:auto;tab-size:4}span[data-info]:hover,span[data-info]:focus{outline:1px solid #777;outline-offset:1px}aside{position:sticky;top:20px;align-self:start;background:white;border:1px solid #ddd;border-radius:9px;padding:16px}aside pre{padding:0;font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere}aside h3{margin:0 0 12px;font-size:14px}@media(max-width:850px){main{grid-template-columns:1fr;padding:12px}aside{position:static}} </style>
<header><h1>Noctis — all 11 original themes</h1><p><a href="https://github.com/BugenZhao/noctis-port">GitHub repository</a> · <a href="https://github.com/BugenZhao/noctis-port#install">Install in Zed</a> · <a href="https://github.com/BugenZhao/noctis-port/blob/main/docs/theme-port.md">Semantic setup and source mappings</a></p><p>Actual rust-analyzer tokens from the included Rust fixture, styled through the pinned VS Code/Noctis mappings. Click a token to inspect its type, modifiers and source rules.</p><p>This is an HTML semantic-color preview. Native Zed layout and Tree-sitter fallback rendering require editor verification.</p><nav>''' + buttons + '''</nav></header><main>''' + "".join(panels) + '''<aside><h3>Token inspector</h3><pre id="inspector">Select a colored token.</pre></aside></main><script>
function selectTheme(id){document.querySelectorAll('.theme').forEach(x=>x.classList.toggle('active',x.id===id));document.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x.dataset.theme===id))}document.querySelectorAll('button').forEach(b=>b.onclick=()=>selectTheme(b.dataset.theme));document.querySelectorAll('[data-info]').forEach(s=>{s.onclick=()=>document.getElementById('inspector').textContent=s.dataset.info;s.onfocus=s.onclick});selectTheme('lux');</script></html>'''
    args.output.write_text(document)
    args.output.with_suffix(".json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
