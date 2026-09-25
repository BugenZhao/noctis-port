#!/usr/bin/env python3
"""Rebuild the entire Noctis catalog from the checked-in VS Code sources.

Scope and semantic-selector scoring follow the pinned VS Code implementation
documented in docs/theme-port.md. No network or third-party modules needed.
"""

import argparse
import copy
import itertools
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "reference/theme-catalog.json").read_text())
SOURCES = json.loads((ROOT / "reference/sources.json").read_text())
SOURCE_DIR = ROOT / "reference" / ("noctis-" + SOURCES["noctis_version"])
VARIANTS = tuple(entry["id"] for entry in CATALOG)
SEMANTICS = json.loads((ROOT / "reference/semantic-scopes.json").read_text())

# Zed UI roles with an explicit counterpart in the original VS Code theme.
UI_MAP = {
    "border": "editorGroup.border",
    "border.variant": "input.border",
    "border.focused": "focusBorder",
    "border.selected": "inputOption.activeBorder",
    "elevated_surface.background": "editorWidget.background",
    "surface.background": "sideBar.background",
    "background": "editor.background",
    "element.background": "dropdown.background",
    "element.hover": "list.hoverBackground",
    "element.active": "list.activeSelectionBackground",
    "element.selected": "list.inactiveSelectionBackground",
    "drop_target.background": "list.dropBackground",
    "ghost_element.hover": "list.hoverBackground",
    "ghost_element.active": "list.activeSelectionBackground",
    "ghost_element.selected": "list.inactiveSelectionBackground",
    "text": "foreground",
    "text.muted": "descriptionForeground",
    "text.placeholder": "input.placeholderForeground",
    "text.accent": "list.highlightForeground",
    "icon": "foreground",
    "icon.muted": "descriptionForeground",
    "icon.accent": "activityBar.foreground",
    "status_bar.background": "statusBar.background",
    "title_bar.background": "titleBar.activeBackground",
    "title_bar.inactive_background": "titleBar.inactiveBackground",
    "toolbar.background": "breadcrumb.background",
    "tab_bar.background": "editorGroupHeader.tabsBackground",
    "tab.inactive_background": "tab.inactiveBackground",
    "tab.active_background": "tab.activeBackground",
    "search.match_background": "editor.findMatchBackground",
    "panel.background": "sideBar.background",
    "panel.focused_border": "panel.border",
    "scrollbar.thumb.background": "scrollbarSlider.background",
    "scrollbar.thumb.hover_background": "scrollbarSlider.hoverBackground",
    "scrollbar.thumb.border": "input.border",
    "editor.foreground": "editor.foreground",
    "editor.background": "editor.background",
    "editor.gutter.background": "editorGutter.background",
    "editor.subheader.background": "editorGroupHeader.noTabsBackground",
    "editor.active_line.background": "editor.lineHighlightBackground",
    "editor.highlighted_line.background": "editor.rangeHighlightBackground",
    "editor.line_number": "editorLineNumber.foreground",
    "editor.active_line_number": "editorLineNumber.activeForeground",
    "editor.invisible": "editorWhitespace.foreground",
    "editor.wrap_guide": "editorRuler.foreground",
    "editor.active_wrap_guide": "editorRuler.foreground",
    "editor.indent_guide": "editorIndentGuide.background",
    "editor.indent_guide_active": "editorIndentGuide.activeBackground",
    "editor.document_highlight.read_background": "editor.wordHighlightBackground",
    "editor.document_highlight.write_background": "editor.wordHighlightStrongBackground",
    "terminal.background": "terminal.background",
    "terminal.foreground": "terminal.foreground",
    "link_text.hover": "textLink.activeForeground",
    "conflict": "gitDecoration.conflictingResourceForeground",
    "created": "gitDecoration.addedResourceForeground",
    "deleted": "gitDecoration.deletedResourceForeground",
    "modified": "gitDecoration.modifiedResourceForeground",
    "ignored": "gitDecoration.ignoredResourceForeground",
    "error": "editorError.foreground",
    "warning": "editorWarning.foreground",
    "info": "editorInfo.foreground",
    "hint": "editorHint.foreground",
    "error.background": "inputValidation.errorBackground",
    "error.border": "inputValidation.errorBorder",
    "warning.background": "inputValidation.warningBackground",
    "warning.border": "inputValidation.warningBorder",
    "info.background": "inputValidation.infoBackground",
    "info.border": "inputValidation.infoBorder",
}
for color in ("black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"):
    UI_MAP[f"terminal.ansi.{color}"] = f"terminal.ansi{color.title()}"
    UI_MAP[f"terminal.ansi.bright_{color}"] = f"terminal.ansiBright{color.title()}"

# Zed-specific roles use documented source roles from the same palette, so a
# fresh build cannot accidentally retain an unrelated light/dark port color.
ADAPTED_UI_MAP = {
    "border.disabled": "input.border",
    "element.disabled": "sideBar.background",
    "ghost_element.disabled": "sideBar.background",
    "text.disabled": "descriptionForeground",
    "icon.disabled": "descriptionForeground",
    "icon.placeholder": "input.placeholderForeground",
    "editor.hover_line_number": "editorLineNumber.activeForeground",
    "scrollbar.track.border": "sideBar.border",
    "conflict.background": "merge.commonHeaderBackground",
    "conflict.border": "gitDecoration.conflictingResourceForeground",
    "created.background": "diffEditor.insertedTextBackground",
    "created.border": "gitDecoration.addedResourceForeground",
    "deleted.background": "diffEditor.removedTextBackground",
    "deleted.border": "gitDecoration.deletedResourceForeground",
    "hidden": "descriptionForeground",
    "hidden.background": "editor.background",
    "hidden.border": "input.border",
    "hint.background": "editorWidget.background",
    "hint.border": "editorWidget.border",
    "ignored.background": "editor.background",
    "ignored.border": "editorGroup.border",
    "modified.background": "editor.wordHighlightBackground",
    "modified.border": "gitDecoration.modifiedResourceForeground",
    "predictive": "descriptionForeground",
    "predictive.background": "editorWidget.background",
    "predictive.border": "input.border",
    "renamed": "gitDecoration.modifiedResourceForeground",
    "renamed.background": "editor.wordHighlightBackground",
    "renamed.border": "gitDecoration.modifiedResourceForeground",
    "success": "gitDecoration.addedResourceForeground",
    "success.background": "diffEditor.insertedTextBackground",
    "success.border": "gitDecoration.addedResourceForeground",
    "unreachable": "descriptionForeground",
    "unreachable.background": "editor.background",
    "unreachable.border": "input.border",
}

# Canonical TextMate probes for Tree-sitter captures and Zed's built-in semantic
# style names. Language-neutral probes use VS Code's standard semantic scope map.
# Rust-specific lifetime/self/primitive captures use rust-analyzer's scope map.
CAPTURES = {
    "attribute": "meta.attribute.rust",
    "boolean": "constant.language.boolean",
    "comment": "comment",
    "comment.doc": "comment.block.documentation",
    "comment.documentation": "comment.block.documentation",
    "constant": "variable.other.constant",
    "constant.builtin": "support.constant",
    "constructor": "entity.name.function.definition.special.constructor",
    "embedded": "source",
    "emphasis": "markup.italic",
    "emphasis.strong": "markup.bold",
    "enum": "entity.name.type.enum",
    "function": "entity.name.function",
    "function.builtin": "support.function",
    "function.method": "entity.name.function.member",
    "function.macro": "entity.name.function.preprocessor",
    "function.decorator": "entity.name.decorator",
    "function.annotation": "meta.attribute.rust",
    "hint": "comment",
    "keyword": "keyword.control",
    "keyword.control": "keyword.control",
    "keyword.modifier": "storage.modifier",
    "label": "entity.name.label",
    "lifetime": "storage.modifier.lifetime.rust",
    "link_text": "markup.underline.link",
    "link_uri": "string.other.link",
    "namespace": "entity.name.namespace",
    "number": "constant.numeric",
    "operator": "keyword.operator",
    "predictive": "comment",
    "preproc": "punctuation.definition.preprocessor",
    "primary": "source",
    "property": "variable.other.property",
    "punctuation": "source punctuation",
    "punctuation.bracket": "source punctuation.section.brackets",
    "punctuation.delimiter": "source punctuation.separator",
    "punctuation.list_marker": "punctuation.definition.list_item",
    "punctuation.special": "punctuation.section.embedded",
    "selector": "entity.other.attribute-name.class",
    "selector.pseudo": "entity.other.attribute-name.pseudo-class",
    "string": "string.quoted",
    "string.doc": "string.quoted",
    "string.escape": "constant.character.escape",
    "string.regex": "string.regexp",
    "string.regexp": "string.regexp",
    "string.special": "string.interpolated",
    "string.special.symbol": "constant.other.symbol",
    "tag": "entity.name.tag",
    "text.literal": "constant.character",
    "title": "markup.heading",
    "type": "entity.name.type",
    "type.builtin": "support.type.primitive.rust",
    "type.class": "entity.name.type.class",
    "type.struct": "entity.name.type.struct",
    "type.enum": "entity.name.type.enum",
    "type.interface": "entity.name.type.interface",
    "type.parameter": "entity.name.type.parameter",
    "type.enum.member": "variable.other.enummember",
    "variable": "variable.other.readwrite",
    "variable.parameter": "variable.parameter",
    "variable.special": "variable.language",
    "variable.builtin": "support.variable",
    "variant": "variable.other.enummember",
}
for name in ("type", "type.class", "type.struct", "type.enum", "type.interface", "type.parameter"):
    CAPTURES[name + ".definition"] = CAPTURES[name]


def color(value):
    """Normalize CSS hex without changing opacity."""
    # Noctis 10.40.0 Lilac contains this malformed info-panel background.
    # VS Code Color.fromHex falls back to Color.red for this invalid length.
    if value == "#00c6ea599ff":
        return "#ff0000ff"
    assert re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]|[0-9a-fA-F]{3}|[0-9a-fA-F]{5})?", value), value
    value = value.lower()
    if len(value) in (4, 5):
        value = "#" + "".join(c * 2 for c in value[1:])
    return value + "ff" if len(value) == 7 else value


def scope_score(selector, scopes):
    """VS Code nameMatcher: last matching identifier's depth and specificity."""
    assert re.fullmatch(r"[\w.\s-]+", selector), selector
    identifiers = selector.split()
    if len(identifiers) > len(scopes):
        return -1
    score = -1
    for identifier in identifiers:
        for i in range(len(scopes) - 1, -1, -1):
            if scopes[i] == identifier or scopes[i].startswith(identifier + "."):
                score = (i + 1) * 0x10000 + len(identifier)
                break
        else:
            return -1
    return score


def resolve_scopes(theme, probes):
    """Resolve color/font separately; later equal-specificity rules win."""
    for scopes in probes:
        values, scores, sources = {}, {}, {}
        for rule in theme["tokenColors"]:
            selectors = rule.get("scope", [])
            if isinstance(selectors, str):
                selectors = [selectors]
            score = max((scope_score(s, scopes) for s in selectors), default=-1)
            if score < 0:
                continue
            for key in ("foreground", "fontStyle"):
                if key in rule["settings"] and score >= scores.get(key, -1):
                    values[key] = rule["settings"][key]
                    scores[key] = score
                    sources[key] = rule.get("name", "unnamed")
        if values:
            style = {}
            if "foreground" in values:
                style["color"] = color(values["foreground"])
            if "fontStyle" in values:
                flags = values["fontStyle"].split()
                style["font_style"] = "italic" if "italic" in flags else "normal"
                style["font_weight"] = 700 if "bold" in flags else 400
                # The source themes have no standalone underline/strike
                # rule for our probes. Fail explicitly if a source update adds one.
                assert not {"underline", "strikethrough"} & set(flags), values
            return style, {"scopes": scopes, "rules": sources}
    return {}, {"scopes": probes, "rules": {}}


def hierarchy(token_type, types):
    result = [token_type]
    while types.get(result[-1]):
        parent = types[result[-1]]
        assert parent not in result, result
        result.append(parent)
    return result


def selector_score(rule, token_type, modifiers, types):
    base, *required = rule["selector"].split(".")
    if not set(required) <= set(modifiers):
        return -1
    chain = hierarchy(token_type, types)
    if base != "*" and base not in chain:
        return -1
    return (0 if base == "*" else 100 - chain.index(base)) + len(required) * 100 + (10 if rule.get("language") else 0)


def semantic_style(theme, token_type, modifiers, rust=False):
    types = SEMANTICS["types"] | (SEMANTICS["rust"]["types"] if rust else {})
    rules = SEMANTICS["rules"] + (SEMANTICS["rust"]["rules"] if rust else [])
    result, scores, sources = {}, {}, {}
    for rule in rules:
        score = selector_score(rule, token_type, modifiers, types)
        if score < 0:
            continue
        style, provenance = resolve_scopes(theme, rule["scopes"])
        for key, value in style.items():
            if score >= scores.get(key, -1):
                result[key], scores[key] = value, score
                sources[key] = {"selector": rule["selector"], **provenance}
    return result, sources


def semantic_entries(theme, rust=False):
    """Materialize modifier combinations before Zed's ordered rule lookup."""
    types = SEMANTICS["types"] | (SEMANTICS["rust"]["types"] if rust else {})
    rules = SEMANTICS["rules"] + (SEMANTICS["rust"]["rules"] if rust else [])
    entries = []
    for token_type in sorted(types):
        relevant = sorted({m for r in rules
                           if r["selector"].split(".")[0] in ["*", *hierarchy(token_type, types)]
                           for m in r["selector"].split(".")[1:]})
        emitted = []
        for length in range(len(relevant) + 1):
            for combo in itertools.combinations(relevant, length):
                style, provenance = semantic_style(theme, token_type, combo, rust)
                if not style:
                    continue
                # Keep a combination only when its effective style differs from
                # the most specific already-emitted subset rule.
                subsets = [e for e in emitted if set(e["modifiers"]) <= set(combo)]
                previous = max(subsets, key=lambda e: len(e["modifiers"]), default=None)
                if previous and previous["style"] == style:
                    continue
                selector = ".".join([token_type, *combo])
                entry = {"token_type": token_type, "modifiers": list(combo),
                         "name": f"noctis.{'rust' if rust else 'semantic'}.{selector}",
                         "style": style, "provenance": provenance}
                emitted.append(entry)
                entries.append(entry)
    return sorted(entries, key=lambda e: (-len(e["modifiers"]), e["name"]))


def generate():
    outputs = {}
    manifest = {"source_version": SOURCES["noctis_version"], "themes": {}, "aliases": {},
                "ui_roles": UI_MAP, "adapted_ui_roles": ADAPTED_UI_MAP}
    shared_rules = {}
    for catalog_entry in CATALOG:
        source = json.loads((SOURCE_DIR / catalog_entry["source"]).read_text())
        path = ROOT / "themes" / catalog_entry["file"]
        style = {}
        theme = {"name": catalog_entry["name"], "appearance": catalog_entry["appearance"], "style": style}
        target = {"$schema": "https://zed.dev/schema/themes/v0.2.0.json", "name": catalog_entry["name"],
                  "author": "Liviu Schera; Siddha Wachche; Noctis port contributors", "themes": [theme]}
        for key, original in (UI_MAP | ADAPTED_UI_MAP).items():
            style[key] = color(source["colors"][original])
        style.update({"border.transparent": "#00000000", "ghost_element.background": "#00000000",
                      "scrollbar.track.background": "#00000000", "pane.focused_border": None})
        # Let Zed derive terminal dim colors; the original has no dim palette.
        style["players"] = [{
            "cursor": color(source["colors"]["editorCursor.foreground"]),
            "background": color(source["colors"]["editorCursor.foreground"]),
            "selection": color(source["colors"]["editor.selectionBackground"]),
        }]
        for ansi in ("Cyan", "Yellow", "Magenta", "Green", "Red", "Blue", "BrightCyan"):
            cursor = color(source["colors"]["terminal.ansi" + ansi])
            style["players"].append({"cursor": cursor, "background": cursor, "selection": cursor[:7] + "3d"})
        syntax = {}
        capture_sources = {}
        for capture, probe in CAPTURES.items():
            resolved, provenance = resolve_scopes(source, [probe.split()])
            # Unstyled syntax falls back to the source editor foreground.
            syntax[capture] = {"color": color(source["colors"]["editor.foreground"]),
                               "font_style": "normal", "font_weight": 400, **resolved}
            capture_sources[capture] = provenance
        variants = {}
        for flavor, rust in [("standard", False), ("rust", True)]:
            entries = semantic_entries(source, rust)
            for entry in entries:
                syntax[entry["name"]] = entry["style"]
            rules = [{"token_type": e["token_type"], "token_modifiers": e["modifiers"],
                      "style": [e["name"]]} for e in entries]
            if flavor in shared_rules:
                assert rules == shared_rules[flavor], "Theme variants require different rule ordering"
            shared_rules[flavor] = rules
            variants[flavor] = entries
        style["syntax"] = syntax
        outputs[path] = target
        manifest["themes"][theme["name"]] = {"source": str((SOURCE_DIR / catalog_entry["source"]).relative_to(ROOT)),
                                              "captures": capture_sources, "semantics": variants}
        for alias in catalog_entry["aliases"]:
            alias_theme = copy.deepcopy(target)
            alias_theme["name"] = alias["name"]
            alias_theme["themes"][0]["name"] = alias["name"]
            outputs[ROOT / "themes" / alias["file"]] = alias_theme
            manifest["aliases"][alias["name"]] = catalog_entry["name"]
    for flavor, rules in shared_rules.items():
        outputs[ROOT / f"settings/{flavor}-semantic.json"] = {
            "semantic_tokens": "combined",
            "global_lsp_settings": {"semantic_token_rules": rules},
        }
    outputs[ROOT / "reference/generated-mapping.json"] = manifest
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report stale generated files without writing")
    args = parser.parse_args()
    stale = []
    for path, value in generate().items():
        rendered = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
        if not path.exists() or path.read_text() != rendered:
            stale.append(str(path.relative_to(ROOT)))
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(rendered)
    if args.check and stale:
        parser.exit(1, "Stale generated files: " + ", ".join(stale) + "\n")
    aliases = sum(len(entry["aliases"]) for entry in CATALOG)
    print(f"{'Checked' if args.check else 'Generated'} {len(CATALOG)} Noctis themes, {aliases} aliases and semantic mapping fragments.")


if __name__ == "__main__":
    main()
