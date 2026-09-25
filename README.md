# Noctis for Zed

All **11 original Noctis 10.40.0 themes** for Zed, with source-derived UI colors,
syntax colors, and LSP semantic styles.

**[Live theme preview](https://bugenzhao.github.io/noctis-port/)** ·
[Semantic setup and mapping details](docs/theme-port.md) ·
[Theme source snapshots](reference/noctis-10.40.0)

The preview lets you switch palettes and click Rust tokens to inspect their
types, modifiers, Zed mapping rules, theme styles, and original Noctis colors.

The original [Noctis](https://github.com/liviuschera/noctis) is by Liviu Schera;
this fork builds on [Siddha Wachche’s Zed port](https://github.com/sidwachche/noctis-port).

| Theme | Appearance |
| --- | --- |
| Noctis Lux | Light |
| Noctis Hibernus | Light |
| Noctis Lilac | Light |
| Noctis | Dark |
| Noctis Azureus | Dark |
| Noctis Bordo | Dark |
| Noctis Obscuro | Dark |
| Noctis Sereno | Dark |
| Noctis Uva | Dark |
| Noctis Viola | Dark |
| Noctis Minimus | Dark |

## Install

```sh
git clone https://github.com/BugenZhao/noctis-port.git
```

1. In Zed, run **zed: install dev extension** and select the cloned `noctis-port` directory.
2. Run **theme selector: toggle** and select a Noctis theme.
3. Enable semantic highlighting in your Zed settings:

```json
{
  "theme": "Noctis Lux",
  "semantic_tokens": "combined"
}
```

Zed's built-in language and semantic mappings connect LSP tokens to the theme.
The theme uses native style names, so installation needs zero Noctis-specific
`semantic_token_rules`. Personal overrides such as unresolved-reference styling
can stay in your settings.

For an earlier installation, remove rules whose `style` names start with
`noctis.rust.` or `noctis.semantic.`. Keep semantic highlighting enabled.
For mutable tokens and Rust `self` / `Self`, append the **three rules** in
[mut-self-semantic.json](settings/mut-self-semantic.json) after your personal
rules. This optional preset adds Noctis's mutable color and self styling while
preserving the native mapping for other tokens. The online and isolated previews
include this preset.

A language-server restart may be needed after enabling semantic tokens.

[Setup and native mapping details](docs/theme-port.md) documents the source
palettes, Zed's mapping behavior, and validation coverage.

## Rebuild

```sh
python3 scripts/import_sources.py --extension /path/to/liviuschera.noctis-10.40.0
python3 scripts/generate_themes.py
python3 scripts/generate_themes.py --check
python3 scripts/test_themes.py
```

The checked-in snapshots make rebuilding possible without an installed VS Code
extension; run `import_sources.py` when updating those snapshots.
The generator is driven by `reference/theme-catalog.json`; every advertised VS Code
variant is covered. Generated files rebuild entirely from the checked-in sources
and mapping tables. Python’s standard library is sufficient.

## Preview

Use the **[online preview](https://bugenzhao.github.io/noctis-port/)** or download
the [self-contained HTML](docs/preview.html) and open it locally.

```sh
python3 scripts/preview.py --theme 'Noctis Minimus'
python3 scripts/inspect_rust_tokens.py \
  --rust-analyzer /path/to/rust-analyzer \
  --output docs/preview.html
```

The second command renders all 11 themes from real language-server tokens, with a
clickable token inspector. It also writes a JSON verification report and LSP log
alongside the HTML. The page renders the semantic layer; native Zed layout and
Tree-sitter fallback rendering have separate coverage.

## Publishing the preview

The [Pages workflow](.github/workflows/pages.yml) deploys the checked-in
`docs/preview.html` as the website root whenever that file changes on `main`.
It also supports manual runs from the Actions tab. Regenerate and commit the HTML
alongside palette changes to keep the hosted preview current.

Validation includes the pinned Zed renderer function, native style coverage,
and 208 actual Rust tokens across all 11 palettes. See the
[mapping audit](docs/semantic-rule-audit.md) for the source analysis and test
boundaries.
