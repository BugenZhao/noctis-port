#!/usr/bin/env python3
"""Differential-test our audit using Zed's unmodified convert_token function.

Pass the pinned crates/editor/src/semantic_tokens.rs as --source. Only GPUI/LSP
container types are stubbed; the actual renderer function is compiled by rustc.
This checks semantic overlays, not native layout or Tree-sitter composition.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import audit_semantic_rules as audit
import generate_themes as port

SOURCE_SHA256 = "994bd60433d9dfcda697641cf8deb751c8a6d439ac909da75adca64040ee0f5a"
STUBS = r'''
#![allow(dead_code)]
use std::collections::BTreeMap;
#[derive(Clone, Copy, Debug, PartialEq)] enum FontStyle { Normal, Italic }
#[derive(Clone, Copy, Debug, PartialEq)] struct FontWeight(u16);
impl FontWeight { const NORMAL: Self = Self(400); const BOLD: Self = Self(700); }
#[derive(Clone, Copy, Debug, PartialEq, Default)]
struct UnderlineStyle { thickness: f32, color: Option<u32> }
type StrikethroughStyle = UnderlineStyle;
#[derive(Clone, Copy, Debug, PartialEq, Default)]
struct HighlightStyle {
    color: Option<u32>, background_color: Option<u32>, font_weight: Option<FontWeight>,
    font_style: Option<FontStyle>, underline: Option<UnderlineStyle>,
    strikethrough: Option<StrikethroughStyle>,
}
#[derive(Clone, Copy)] enum SemanticTokenColorOverride { InheritForeground(bool), Replace(u32) }
#[derive(Clone, Copy)] enum SemanticTokenFontStyle { Normal, Italic }
#[derive(Clone, Copy)] enum SemanticTokenFontWeight { Normal, Bold }
#[derive(Clone, Default)] struct SemanticTokenRule {
    token_type: Option<String>, token_modifiers: Vec<String>, style: Vec<String>,
    foreground_color: Option<u32>, background_color: Option<u32>,
    font_weight: Option<SemanticTokenFontWeight>, font_style: Option<SemanticTokenFontStyle>,
    underline: Option<SemanticTokenColorOverride>, strikethrough: Option<SemanticTokenColorOverride>,
}
impl SemanticTokenRule {
    fn no_style_defined(&self) -> bool {
        self.style.is_empty() && self.foreground_color.is_none() && self.background_color.is_none()
        && self.font_weight.is_none() && self.font_style.is_none()
        && self.underline.is_none() && self.strikethrough.is_none()
    }
}
struct SyntaxTheme { styles: BTreeMap<String, HighlightStyle> }
impl SyntaxTheme {
    fn style_for_name(&self, name: &str) -> Option<HighlightStyle> { self.styles.get(name).copied() }
}
type TokenType = u32;
struct SemanticTokenStylizer { rules: Vec<SemanticTokenRule>, modifiers: Vec<String> }
impl SemanticTokenStylizer {
    fn rules_for_token(&self, _: TokenType) -> Option<&[SemanticTokenRule]> { Some(&self.rules) }
    fn has_modifier(&self, mask: u32, name: &str) -> bool {
        self.modifiers.iter().position(|m| m == name).is_some_and(|i| mask & (1 << i) != 0)
    }
}
fn strings(v: &[&str]) -> Vec<String> { v.iter().map(|s| s.to_string()).collect() }
fn r(token: &str, modifiers: &[&str], style: &[&str]) -> SemanticTokenRule {
    SemanticTokenRule { token_type: Some(token.to_string()), token_modifiers: strings(modifiers),
                        style: strings(style), ..Default::default() }
}
fn h(color: Option<u32>, font: Option<FontStyle>, weight: Option<FontWeight>) -> HighlightStyle {
    HighlightStyle { color, font_style: font, font_weight: weight, ..Default::default() }
}
'''


def rust_style(style):
    assert not set(style) - {"color", "font_style", "font_weight"}, style
    color = f'Some(0x{style["color"][1:]})' if "color" in style else "None"
    font = f'Some(FontStyle::{style["font_style"].title()})' if "font_style" in style else "None"
    weight = f'Some(FontWeight({style["font_weight"]}))' if "font_weight" in style else "None"
    return f"h({color}, {font}, {weight})"


def string_slice(values):
    return "&[" + ",".join(json.dumps(v) for v in values) + "]"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    assert hashlib.sha256(args.source.read_bytes()).hexdigest() == SOURCE_SHA256
    source = args.source.read_text()
    convert = source[source.index("fn convert_token("):source.index("\n#[cfg(test)]\nmod tests")]
    code = [STUBS, convert, "fn main() { let mut count = 0;"]
    for rust in (False, True):
        report = audit.audit(rust)
        flavor = report["profile"]
        original = audit.legacy_rules(rust)
        builtins = audit.builtin_rules(rust)
        modifiers = sorted({m for r in original + builtins for m in r.get("token_modifiers", [])})
        for entry in port.CATALOG:
            syntax = audit.audit_syntax(entry)
            code.append("{ let theme = SyntaxTheme { styles: BTreeMap::from([")
            for name, style in syntax.items():
                code.append(f"({json.dumps(name)}.to_string(), {rust_style(style)}),")
            code.append("]) };")
            for user in (original, report["retained_rules"], []):
                rules = user + builtins
                code.append("{ let rules = vec![")
                for rule in rules:
                    assert not set(rule) - {"token_type", "token_modifiers", "style"}, rule
                    code.append(f'r({json.dumps(rule["token_type"])}, {string_slice(rule.get("token_modifiers", []))}, {string_slice(rule.get("style", []))}),')
                code.append("];")
                for token, combos in audit.domain(original + builtins):
                    # Mirrors the source's rule assembly; convert_token itself
                    # below remains byte-for-byte the pinned Rust implementation.
                    code.append("{ let stylizer = SemanticTokenStylizer { rules: rules.iter().rev()"
                                f'.filter(|r| r.token_type.as_deref().is_none_or(|t| t == {json.dumps(token)}))'
                                f'.cloned().collect(), modifiers: strings({string_slice(modifiers)}) }};')
                    for mods in combos:
                        mask = sum(1 << modifiers.index(m) for m in mods)
                        expected = audit.render(syntax, rules, token, mods)
                        expected = "None" if expected is None else f"Some({rust_style(expected)})"
                        code.append(f'assert_eq!(convert_token(&stylizer, &theme, 0, {mask}), {expected}); count += 1;')
                    code.append("}")
                code.append("}")
            code.append("}")
    code.append('println!("Verified {count} overlays against pinned Zed convert_token."); }')
    args.work_dir.mkdir(parents=True, exist_ok=True)
    path = args.work_dir / "zed_renderer_probe.rs"
    path.write_text("\n".join(code))
    binary = args.work_dir / "zed_renderer_probe"
    subprocess.run(["rustc", "--edition=2024", str(path), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
