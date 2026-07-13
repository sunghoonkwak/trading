# Portfolio Weight-Difference Adapter (`src/infrastructure/portfolio/weight_diffs.py`)

`get_weight_diffs()` produces group-aware weight and quantity differences for
Telegram composition using dependencies grouped in `WeightDiffDependencies`.

It combines configured core/satellite groups, treats the `Bonds` group as cash,
uses an injected price fallback, and returns sorted differences, total USD
value, and current/target cash weights. Configuration read failure produces an
empty group configuration rather than failing the presentation calculation.
