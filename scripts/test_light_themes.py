#!/usr/bin/env python3
"""Check source provenance, known Noctis styles, and semantic rule translation."""
import hashlib
import itertools
import json
import re
import unittest

import generate_light_themes as port


class LightThemeTests(unittest.TestCase):
    def test_source_snapshots(self):
        sources = json.loads((port.ROOT / "reference/sources.json").read_text())
        for name, digest in sources["files"].items():
            actual = hashlib.sha256((port.ROOT / "reference/noctis-10.40.0" / name).read_bytes()).hexdigest()
            self.assertEqual(actual, digest, name)

    def test_known_noctis_semantic_styles(self):
        # Explicit goldens from the original theme's VARIABLE, ANNOTATION,
        # FUNCTION, CONSTANT, TAG, KEYWORD and separate font-style rules.
        goldens = [
            ("parameter", [], "#fa8900ff", "normal", 700),
            ("property", [], "#fa8900ff", "italic", 400),
            ("property", ["readonly"], "#a88c00ff", "italic", 400),
            ("lifetime", [], "#b3694dff", "italic", 700),
            ("builtinType", [], "#b3694dff", "italic", 400),
            ("keyword", [], "#e64100ff", "normal", 400),
            ("keyword", ["controlFlow"], "#ff5792ff", "normal", 700),
            ("function", [], "#0095a8ff", None, None),
            ("variable", ["constant"], "#a88c00ff", None, None),
        ]
        for variant in port.VARIANTS:
            source = json.loads((port.ROOT / f"reference/noctis-10.40.0/{variant}.json").read_text())
            for token, modifiers, color, font, weight in goldens:
                with self.subTest(variant=variant, token=token, modifiers=modifiers):
                    style, _ = port.semantic_style(source, token, modifiers, rust=True)
                    self.assertEqual(style.get("color"), color)
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
            source = json.loads((port.ROOT / f"reference/noctis-10.40.0/{variant}.json").read_text())
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
        for variant in port.VARIANTS:
            source = json.loads((port.ROOT / f"reference/noctis-10.40.0/{variant}.json").read_text())
            theme = generated[port.ROOT / f"themes/{variant}-light.json"]["themes"][0]
            self.assertEqual(theme["appearance"], "light")
            for key, original in port.UI_MAP.items():
                self.assertEqual(theme["style"][key], port.color(source["colors"][original]))
            for value in re.findall(r'"(#[^"]+)"', json.dumps(theme)):
                self.assertRegex(value, r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")
            for flavor in ["standard", "rust"]:
                rules = generated[port.ROOT / f"settings/{flavor}-semantic.json"]["global_lsp_settings"]["semantic_token_rules"]
                for rule in rules:
                    self.assertIn(rule["style"][0], theme["style"]["syntax"])


if __name__ == "__main__":
    unittest.main()
