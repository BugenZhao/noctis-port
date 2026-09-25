# Noctis for Zed

All **11 original Noctis 10.40.0 themes**, generated from the locally installed
VS Code extension with auditable UI colors, syntax colors and semantic styles.
The original [Noctis](https://github.com/liviuschera/noctis) is by Liviu Schera;
this fork builds on [Siddha Wachche’s Zed port](https://github.com/sidwachche/noctis-port).

| Original theme | Appearance | Compatibility alias |
| --- | --- | --- |
| Noctis Lux | Light | Lux Light |
| Noctis Hibernus | Light | Hibernus Light |
| Noctis Lilac | Light | Lilac Light |
| Noctis | Dark | — |
| Noctis Azureus | Dark | — |
| Noctis Bordo | Dark | — |
| Noctis Obscuro | Dark | — |
| Noctis Sereno | Dark | — |
| Noctis Uva | Dark | — |
| Noctis Viola | Dark | — |
| Noctis Minimus | Dark | — |

The original Hibernus, Lilac and Lux are light themes. Both their canonical
`Noctis …` names and the previous `… Light` names now select the same source palette.

## Use

1. Run **zed: install dev extension** and select this checkout.
2. Select a Noctis theme in the theme picker.
3. Enable `"semantic_tokens": "combined"` and merge the appropriate fragment from
   `settings/` to use the precise VS Code semantic mappings.

[Setup, mapping contract and validation](docs/theme-port.md) explains the standard
and Rust mapping profiles, precedence and fidelity boundaries.

## Rebuild

```sh
python3 scripts/import_sources.py --extension /path/to/liviuschera.noctis-10.40.0
python3 scripts/generate_themes.py
python3 scripts/generate_themes.py --check
python3 scripts/test_themes.py
```

The generator is driven by `reference/theme-catalog.json`; every advertised VS Code
variant is covered. Generated files rebuild entirely from the checked-in sources
and mapping tables. Python’s standard library is sufficient.

## Preview

Open [the self-contained semantic preview](docs/preview.html) in a browser to
compare all 11 palettes and inspect real Rust tokens.

```sh
python3 scripts/preview.py --theme 'Noctis Minimus'
python3 scripts/inspect_rust_tokens.py \
  --rust-analyzer /path/to/rust-analyzer \
  --output docs/preview.html
```

The second command renders all 11 themes from real language-server tokens, with a
clickable token inspector. It also writes a JSON verification report.
