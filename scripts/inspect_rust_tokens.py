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
import audit_semantic_rules as zed


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rust-analyzer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tokens-output", type=Path,
                        help="Save actual LSP tokens for the full Zed mapping audit")
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
    if args.tokens_output:
        args.tokens_output.parent.mkdir(parents=True, exist_ok=True)
        args.tokens_output.write_text(json.dumps({"legend": legend, "tokens": tokens}, indent=2) + "\n")

    panels = []
    mapping = json.loads((port.ROOT / "reference/generated-mapping.json").read_text())["themes"]
    summary = {"server": str(args.rust_analyzer), "token_count": len(tokens),
               "token_types": dict(categories), "mapping": "Zed 1.21.0 built-in rules + mutable/self refinements",
               "custom_theme_rules": len(port.MUT_SELF_RULES), "theme_checks": {}, "native_zed_rendering": "not_verified"}
    for entry in port.CATALOG:
        variant = entry["id"]
        theme = json.loads((port.ROOT / "themes" / entry["file"]).read_text())["themes"][0]
        syntax = theme["style"]["syntax"]
        parts, previous, mapped, changed = [], 0, 0, 0
        for index, token in enumerate(tokens):
            assert token["start"] >= previous, "Overlapping tokens need a different renderer"
            parts.append(html.escape(source[previous:token["start"]]))
            profiles = {}
            for mode, rules in [("native", zed.builtin_rules(True)),
                                ("custom", port.MUT_SELF_RULES + zed.builtin_rules(True))]:
                actual = zed.render(syntax, rules, token["type"], token["modifiers"]) or {}
                assert actual, (theme["name"], mode, token)
                provenance = []
                for rule in rules:
                    if rule.get("token_type") not in (None, token["type"]):
                        continue
                    if not set(rule.get("token_modifiers", [])) <= set(token["modifiers"]):
                        continue
                    name = next((n for n in rule.get("style", []) if n in syntax), None)
                    if name:
                        provenance.append({"zed_rule": rule, "theme_style": name,
                                           "noctis_source": mapping[theme["name"]]["captures"].get(name)})
                css = ";".join(f"{key.replace('_', '-')}:{value}" for key, value in actual.items()
                               if key in ("color", "font_style", "font_weight"))
                profiles[mode] = {"css": css, "info": {
                    "mode": "Custom rules on" if mode == "custom" else "Zed defaults",
                    "token": token["text"], "type": token["type"], "modifiers": token["modifiers"],
                    "style": actual, "source": provenance,
                }}
            mapped += 1
            changed += profiles["native"]["info"]["style"] != profiles["custom"]["info"]["style"]
            data = html.escape(json.dumps(profiles, ensure_ascii=False, separators=(",", ":")), quote=True)
            parts.append(f'<span tabindex="0" data-token="{index}" data-variants="{data}" style="{profiles["custom"]["css"]}">{html.escape(token["text"])}</span>')
            previous = token["end"]
        parts.append(html.escape(source[previous:]))
        s = theme["style"]
        panels.append(f'<section id="{variant}" class="theme" data-changed="{changed}" data-total="{len(tokens)}" style="--bg:{s["editor.background"]};--fg:{s["editor.foreground"]};--bar:{s["tab_bar.background"]};--muted:{s["editor.line_number"]}"><h2>{theme["name"]}<small>Noctis {port.SOURCES["noctis_version"]} · {entry["appearance"]} · rust-analyzer semantic tokens</small></h2><pre>{"".join(parts)}</pre></section>')
        assert mapped == len(tokens), (theme["name"], mapped, len(tokens))
        summary["theme_checks"][theme["name"]] = {"tokens": len(tokens), "mapped_tokens": mapped, "changed_tokens": changed}
    buttons = "".join(f'<button data-theme="{e["id"]}">{html.escape(e["name"])}</button>' for e in port.CATALOG)
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Noctis semantic preview</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f5f5f4;color:#25252b;font:15px -apple-system,BlinkMacSystemFont,sans-serif}header{padding:20px 28px;border-bottom:1px solid #ddd}h1{font-size:22px;margin:0 0 8px}p{max-width:950px;line-height:1.5;margin:6px 0}nav{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}button{border:1px solid #bbb;background:white;padding:9px 15px;border-radius:7px;cursor:pointer}button.active{background:#25252b;color:white}main{display:grid;grid-template-columns:minmax(400px,1fr) 360px;gap:20px;padding:20px 28px}.theme{display:none;background:var(--bg);color:var(--fg);border:1px solid #ccc;border-radius:9px;overflow:hidden}.theme.active{display:block}h2{font-size:15px;background:var(--bar);margin:0;padding:14px 20px}small{display:block;font-size:11px;font-weight:400;margin-top:4px}pre{font:14px/1.6 'Iosevka Bugen',ui-monospace,monospace;margin:0;padding:20px;overflow:auto;tab-size:4}span[data-variants]:hover,span[data-variants]:focus{outline:1px solid #777;outline-offset:1px}aside{position:sticky;top:20px;align-self:start;background:white;border:1px solid #ddd;border-radius:9px;padding:16px}aside pre{padding:0;font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere}aside h3{margin:0 0 12px;font-size:14px}.rule-toggle{display:flex;align-items:center;gap:10px;font-weight:600;cursor:pointer}.rule-toggle input{width:18px;height:18px;accent-color:#25252b}.rule-help{font-size:13px;color:#555;margin:10px 0}.rule-status{font-size:13px;margin:8px 0 18px;padding-bottom:16px;border-bottom:1px solid #ddd}@media(max-width:850px){aside{grid-row:1}}@media(max-width:850px){main{grid-template-columns:1fr;padding:12px}aside{position:static}} </style>
<header><h1>Noctis — all 11 original themes</h1><p><a href="https://github.com/BugenZhao/noctis-port">GitHub repository</a> · <a href="https://github.com/BugenZhao/noctis-port#install">Install in Zed</a> · <a href="https://github.com/BugenZhao/noctis-port/blob/main/docs/theme-port.md">Semantic setup and source mappings</a></p><p>Actual rust-analyzer tokens → Zed 1.21 built-in Rust and default mappings → Noctis theme styles. Toggle the three custom rules in the side panel to compare mutable tokens, self and Self. Click a token to inspect the full mapping and source colors.</p><p>This is an HTML semantic-color preview. Native Zed layout and Tree-sitter fallback rendering require editor verification.</p><nav>''' + buttons + '''</nav></header><main>''' + "".join(panels) + '''<aside><h3>Highlighting</h3><label class="rule-toggle" for="custom-rules"><input id="custom-rules" type="checkbox" checked aria-describedby="rule-help rule-status">Enable custom rules</label><p class="rule-help" id="rule-help">Mutable tokens, self and Self. Turn off to compare Zed defaults.</p><p class="rule-status" id="rule-status" role="status" aria-live="polite"></p><h3>Token inspector</h3><pre id="inspector">Select a colored token.</pre></aside></main><script>
const toggle = document.getElementById('custom-rules');
const inspector = document.getElementById('inspector');
const spans = [...document.querySelectorAll('[data-variants]')];
const profiles = new Map(spans.map(span => [span, JSON.parse(span.dataset.variants)]));
let selectedToken = null;
function mode() { return toggle.checked ? 'custom' : 'native'; }
function updateInspector() {
  const token = selectedToken === null ? null : document.querySelector('.theme.active [data-token="' + selectedToken + '"]');
  inspector.textContent = token ? JSON.stringify(profiles.get(token)[mode()].info, null, 2) : 'Select a colored token.';
}
function updateStatus() {
  const panel = document.querySelector('.theme.active');
  document.getElementById('rule-status').textContent = (toggle.checked ? 'Custom rules on' : 'Zed defaults') + ' · ' + panel.dataset.changed + ' of ' + panel.dataset.total + ' tokens differ between modes.';
}
function selectTheme(id) {
  document.querySelectorAll('.theme').forEach(panel => panel.classList.toggle('active', panel.id === id));
  document.querySelectorAll('button[data-theme]').forEach(button => {
    const active = button.dataset.theme === id;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  updateInspector();
  updateStatus();
}
toggle.addEventListener('change', () => {
  spans.forEach(span => { span.style.cssText = profiles.get(span)[mode()].css; });
  updateInspector();
  updateStatus();
});
document.querySelectorAll('button[data-theme]').forEach(button => { button.onclick = () => selectTheme(button.dataset.theme); });
spans.forEach(span => {
  span.onclick = span.onfocus = () => { selectedToken = span.dataset.token; updateInspector(); };
});
selectTheme('lux');
</script></html>'''
    args.output.write_text(document)
    args.output.with_suffix(".json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
