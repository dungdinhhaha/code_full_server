"""Canonical list of the ten virtual melon greenhouses used by SMIOT."""

FARMS = (
    ("greenhouse_a", "Greenhouse A", "🌿"),
    ("greenhouse_b", "Greenhouse B", "🍈"),
    ("greenhouse_c", "Greenhouse C", "🌱"),
    ("greenhouse_d", "Greenhouse D", "🏡"),
    ("greenhouse_e", "Greenhouse E", "🌿"),
    ("greenhouse_f", "Greenhouse F", "🍈"),
    ("greenhouse_g", "Greenhouse G", "🌱"),
    ("greenhouse_h", "Greenhouse H", "🏡"),
    ("greenhouse_i", "Greenhouse I", "🌿"),
    ("greenhouse_j", "Greenhouse J", "🍈"),
)

FARM_KEYS = tuple(row[0] for row in FARMS)
FARM_LABELS = {key: label for key, label, _emoji in FARMS}
FARM_KEYS_BY_LABEL = {label: key for key, label, _emoji in FARMS}
