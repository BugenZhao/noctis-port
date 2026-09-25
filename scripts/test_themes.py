#!/usr/bin/env python3
"""Check source provenance, known Noctis styles, and semantic rule translation."""
import hashlib
import itertools
import json
import re
import unittest

import generate_themes as port


class ThemeTests(unittest.TestCase):
    def test_source_snapshots(self):
        sources = json.loads((port.ROOT / "reference/sources.json").read_text())
        for name, digest in sources["files"].items():
            actual = hashlib.sha256((port.SOURCE_DIR / name).read_bytes()).hexdigest()
            self.assertEqual(actual, digest, name)

    def test_known_noctis_semantic_styles(self):
        # Explicit goldens from the original theme's VARIABLE, ANNOTATION,
        # FUNCTION, CONSTANT, TAG, KEYWORD and separate font-style rules.
        goldens = [
            ("parameter", [], "VARIABLE", "normal", 700),
            ("property", [], "VARIABLE", "italic", 400),
            ("property", ["readonly"], "CONSTANT", "italic", 400),
            ("lifetime", [], "ANNOTATION", "italic", 700),
            ("builtinType", [], "ANNOTATION", "italic", 400),
            ("keyword", [], "TAG", "normal", 400),
            ("keyword", ["controlFlow"], "KEYWORD", "normal", 700),
            ("function", [], "FUNCTION", None, None),
            ("variable", ["constant"], "CONSTANT", None, None),
        ]
        for variant in port.VARIANTS:
            source = json.loads((port.SOURCE_DIR / f"{variant}.json").read_text())
            palette = {rule["name"]: rule["settings"].get("foreground") for rule in source["tokenColors"]}
            for token, modifiers, palette_key, font, weight in goldens:
                with self.subTest(variant=variant, token=token, modifiers=modifiers):
                    style, _ = port.semantic_style(source, token, modifiers, rust=True)
                    self.assertEqual(style.get("color"), port.color(palette[palette_key]))
                    self.assertEqual(style.get("font_style"), font)
                    self.assertEqual(style.get("font_weight"), weight)

    def test_separate_foreground_and_font_precedence(self):
        theme = {"tokenColors": [
            {"scope": ["variable"], "settings": {"foreground": "#123456", "fontStyle": "bold"}},
            {"scope": ["variable.parameter"], "settings": {"fontStyle": "italic"}},
            {"scope": ["variable.parameter"], "settings": {"foreground": "#abcdef"}},
        ]}
        style, _ = port.resolve_scopes(theme, [["variable.parameter.rust"]])
        self.assertEqual(style, {"color": "#abcdefff", "font_style": "italic", "font_weight": 400})
        theme["tokenColors"].append({"scope": ["variable.parameter"], "settings": {"fontStyle": ""}})
        style, _ = port.resolve_scopes(theme, [["variable.parameter.rust"]])
        self.assertEqual(style["font_style"], "normal")
        self.assertEqual(style["font_weight"], 400)

    def test_contextual_scopes_do_not_leak(self):
        theme = {"tokenColors": [
            {"scope": ["source.ocaml variable.parameter"], "settings": {"foreground": "#abcdef"}},
            {"scope": ["variable"], "settings": {"foreground": "#123456"}},
        ]}
        self.assertEqual(port.resolve_scopes(theme, [["variable.parameter"]])[0]["color"], "#123456ff")
        self.assertEqual(port.resolve_scopes(theme, [["source.ocaml", "variable.parameter"]])[0]["color"], "#abcdefff")

    def test_vscode_resolution_equals_generated_zed_rule_order(self):
        # Zed 1.21 merges matched rules in reverse order, with earlier rules
        # taking precedence independently per style property. Exercise modifier
        # combinations that overlap (e.g. readonly + constant + defaultLibrary).
        count = 0
        for variant in port.VARIANTS:
            source = json.loads((port.SOURCE_DIR / f"{variant}.json").read_text())
            for rust in [False, True]:
                entries = port.semantic_entries(source, rust)
                types = port.SEMANTICS["types"] | (port.SEMANTICS["rust"]["types"] if rust else {})
                modifiers = ["readonly", "defaultLibrary", "constant", "controlFlow", "mutable", "declaration"]
                for token in types:
                    for flags in itertools.product([False, True], repeat=len(modifiers)):
                        combo = {m for m, present in zip(modifiers, flags) if present}
                        actual = {}
                        for entry in reversed(entries):
                            if entry["token_type"] == token and set(entry["modifiers"]) <= combo:
                                actual.update(entry["style"])
                        expected, _ = port.semantic_style(source, token, combo, rust)
                        self.assertEqual(actual, expected, (variant, rust, token, combo))
                        count += 1
        print(f"Compared {count} token/modifier/theme cases.")

    def test_generated_files_colors_and_ui_mapping(self):
        generated = port.generate()
        for path, content in generated.items():
            self.assertEqual(json.loads(path.read_text()), content, str(path))
        for entry in port.CATALOG:
            source = json.loads((port.SOURCE_DIR / entry["source"]).read_text())
            theme = generated[port.ROOT / "themes" / entry["file"]]["themes"][0]
            self.assertEqual(theme["appearance"], entry["appearance"])
            for key, original in (port.UI_MAP | port.ADAPTED_UI_MAP).items():
                self.assertEqual(theme["style"][key], port.color(source["colors"][original]))
            for value in re.findall(r'"(#[^"]+)"', json.dumps(theme)):
                self.assertRegex(value, r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")
            for flavor in ["standard", "rust"]:
                rules = generated[port.ROOT / f"settings/{flavor}-semantic.json"]["global_lsp_settings"]["semantic_token_rules"]
                for rule in rules:
                    self.assertIn(rule["style"][0], theme["style"]["syntax"])

    def test_catalog_matches_vscode_manifest_exactly(self):
        package = json.loads((port.SOURCE_DIR / "package-themes.json").read_text())
        advertised = {theme["label"]: theme for theme in package["contributes"]["themes"]}
        self.assertEqual({e["name"] for e in port.CATALOG}, set(advertised))
        self.assertEqual(len(port.CATALOG), 11)
        self.assertEqual(sum(e["appearance"] == "light" for e in port.CATALOG), 3)
        self.assertEqual(sum(e["appearance"] == "dark" for e in port.CATALOG), 8)
        generated = port.generate()
        outputs = set()
        for entry in port.CATALOG:
            expected = "light" if advertised[entry["name"]]["uiTheme"] == "vs" else "dark"
            self.assertEqual(entry["appearance"], expected)
            canonical = generated[port.ROOT / "themes" / entry["file"]]["themes"][0]
            outputs.add(entry["file"])
            self.assertEqual(canonical["name"], entry["name"])
            self.assertNotIn("aliases", entry)
        self.assertEqual(outputs, {p.name for p in (port.ROOT / "themes").glob("*.json")})

    def test_original_light_palette_regressions(self):
        theme = json.loads((port.ROOT / "themes/lux.json").read_text())["themes"][0]
        self.assertEqual(theme["style"]["syntax"]["variable.parameter"],
                         {"color": "#fa8900ff", "font_style": "normal", "font_weight": 700})
        self.assertEqual(theme["style"]["syntax"]["lifetime"],
                         {"color": "#b3694dff", "font_style": "italic", "font_weight": 700})
        self.assertEqual(theme["style"]["editor.background"], "#fef8ecff")


if __name__ == "__main__":
    unittest.main()
