#!/usr/bin/env python3
"""Audit Noctis rules against Zed 1.21's complete semantic styling pipeline.

Source contract: SemanticTokenStylizer::new reverses user + language + default
rules; convert_token merges each property separately; style_for_name is exact.
The highest-priority type-matching empty rule suppresses a token when its
modifiers match. This intentionally models the code, including that edge case.
"""
import argparse
import itertools
import json
import re
from pathlib import Path

import generate_themes as port

REFERENCE = port.ROOT / "reference/zed-1.21.0"
DEFAULT_RULES = json.loads(re.sub(r",\s*([}\]])", r"\1", re.sub(
    r"//[^\n]*", "", (REFERENCE / "default_semantic_token_rules.jsonc").read_text())))
RUST_RULES = json.loads((REFERENCE / "rust_semantic_token_rules.json").read_text())
FIELDS = {"foreground_color": "color", "background_color": "background_color",
          "font_style": "font_style", "font_weight": "font_weight",
          "underline": "underline", "strikethrough": "strikethrough"}


def legacy_rules(rust):
    """Reconstruct the retired parity profile solely for comparison."""
    source = json.loads((port.SOURCE_DIR / port.CATALOG[0]["source"]).read_text())
    return [{"token_type": e["token_type"], "token_modifiers": e["modifiers"], "style": [e["name"]]}
            for e in port.semantic_entries(source, rust)]


def audit_syntax(entry):
    syntax = json.loads((port.ROOT / "themes" / entry["file"]).read_text())["themes"][0]["style"]["syntax"]
    source = json.loads((port.SOURCE_DIR / entry["source"]).read_text())
    for rust in (False, True):
        syntax.update({e["name"]: e["style"] for e in port.semantic_entries(source, rust)})
    return syntax


def render(syntax, rules, token, modifiers):
    """Return the semantic overlay (None means suppressed/unmapped)."""
    by_type = [r for r in rules if r.get("token_type") in (None, token)]
    if not by_type:
        return None
    def matches(rule):
        return set(rule.get("token_modifiers", [])) <= set(modifiers)
    first = by_type[0]
    if not first.get("style") and not any(first.get(k) is not None for k in FIELDS) and matches(first):
        return None
    result = {}
    for rule in reversed(by_type):
        if not matches(rule):
            continue
        style = next((syntax[n] for n in rule.get("style", []) if n in syntax), {})
        for rule_field, style_field in FIELDS.items():
            value = rule.get(rule_field)
            if value is None:
                value = style.get(style_field)
            if value is not None:
                if rule_field == "font_weight":
                    value = {"normal": 400, "bold": 700}.get(value, value)
                result[style_field] = value
    return result


def builtin_rules(rust):
    return (RUST_RULES if rust else []) + DEFAULT_RULES


def domain(rules):
    """All modifier equivalence classes for every rule's token type.

    Modifiers absent from every selector cannot change the output. Enumerating
    relevant modifiers per token is exhaustive without repeating neutral flags.
    """
    for token in sorted({r["token_type"] for r in rules if r.get("token_type")}):
        modifiers = sorted({m for r in rules if r.get("token_type") in (None, token)
                            for m in r.get("token_modifiers", [])})
        yield token, [frozenset(m for m, enabled in zip(modifiers, flags) if enabled)
                      for flags in itertools.product([False, True], repeat=len(modifiers))]


def audit(rust):
    flavor = "rust" if rust else "standard"
    user = legacy_rules(rust)
    builtins = builtin_rules(rust)
    themes = [(e["name"], audit_syntax(e)) for e in port.CATALOG]
    cases = {}
    differences = []
    for token, combos in domain(user + builtins):
        cases[token] = [(name, syntax, mods, render(syntax, user + builtins, token, mods))
                        for name, syntax in themes for mods in combos]
        for name, syntax, mods, expected in cases[token]:
            default = render(syntax, builtins, token, mods)
            if expected != default:
                differences.append({"theme": name, "token": token, "modifiers": sorted(mods),
                                    "current": expected, "built_in": default})
    kept = user.copy()
    removed = []
    for rule in user:
        candidate = kept.copy()
        candidate.remove(rule)
        token = rule["token_type"]
        if all(render(syntax, candidate + builtins, token, mods) == expected
               for _, syntax, mods, expected in cases[token]):
            kept = candidate
            removed.append(rule)
    # Final full-domain check also covers tokens untouched by user rules.
    checked = 0
    for token, token_cases in cases.items():
        for _, syntax, mods, expected in token_cases:
            assert render(syntax, kept + builtins, token, mods) == expected
            checked += 1
    return {"profile": flavor, "original_rule_count": len(user),
            "retained_rule_count": len(kept), "removed_rule_count": len(removed),
            "exhaustive_cases": checked, "built_in_difference_cases": len(differences),
            "differences": differences, "retained_rules": kept, "removed_rules": removed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tokens", type=Path, help="Real LSP tokens from inspect_rust_tokens.py")
    args = parser.parse_args()
    report = {"zed_version": "1.21.0", "profiles": [audit(False), audit(True)]}
    if args.tokens:
        tokens = json.loads(args.tokens.read_text())["tokens"]
        user = legacy_rules(True)
        reduced = report["profiles"][1]["retained_rules"]
        checks = {}
        for entry in port.CATALOG:
            syntax = audit_syntax(entry)
            differences = []
            for token in tokens:
                kind, mods = token["type"], token["modifiers"]
                current = render(syntax, user + builtin_rules(True), kind, mods)
                minimal = render(syntax, reduced + builtin_rules(True), kind, mods)
                default = render(syntax, builtin_rules(True), kind, mods)
                assert minimal == current, (entry["name"], token)
                if current != default:
                    differences.append({**token, "current": current, "built_in": default})
            checks[entry["name"]] = {"tokens": len(tokens), "reduced_mismatches": 0,
                                     "built_in_differences": len(differences), "differences": differences}
        report["actual_lsp"] = checks
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    for p in report["profiles"]:
        print({k: v for k, v in p.items() if not isinstance(v, list)})


if __name__ == "__main__":
    main()
