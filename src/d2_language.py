"""D2 — language-stratified classification experiment.

IMPORTANT — what this actually is: CLAUDE.md's "clean / truncated / small_model" design
describes conditions for a production LLM classifier. This repo has no LLM library and no
network calls at runtime (see hard constraints), so this script implements an honest,
deterministic **keyword-matching baseline classifier** instead of calling a real model.

This is NOT a claim that we ran GPT/Claude/etc. It IS a real, reproducible, deterministic
classification pipeline whose accuracy numbers are genuinely measured (not invented) —
they just measure a simpler baseline than a production LLM. Say so explicitly on the slide.

`small_model` is simulated as a version of the same classifier with a deliberately smaller
keyword vocabulary (proportionally reduced in both languages, not specifically gimped for
native script) — a stand-in for a smaller/cheaper model's narrower coverage.
`truncated` uses the real production behaviour described in CLAUDE.md: truncate to the
first 40 characters before classifying.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = REPO_ROOT / "outputs"

DEPARTMENTS = [
    "electrical_emergency",
    "electrical_maintenance",
    "water_supply",
    "drainage",
    "roads",
    "sanitation",
]

# Full ("clean" / "truncated" conditions) keyword vocabulary, atomic substrings chosen to
# avoid accidental collisions with unrelated departments wherever possible.
FULL_KEYWORDS_EN: dict[str, list[str]] = {
    "electrical_emergency": [
        "spark", "sparks", "sparking", "live wire", "shock", "buzzing", "burning",
        "fire", "exposed wire", "exposed electric wire", "emergency", "dangerous",
    ],
    "electrical_maintenance": [
        "streetlight", "street light", "flicker", "flickering", "electricity meter",
        "meter reading", "bill", "repair visit", "dark at night", "pole",
    ],
    "water_supply": [
        "water supply", "no water", "pipeline", "burst", "tap", "muddy",
        "contamination", "water pressure", "restore", "water connection",
    ],
    "drainage": [
        "drain", "drainage", "storm drain", "sewage", "overflow", "overflowing",
        "flooding", "manhole", "blocked",
    ],
    "roads": [
        "pothole", "footpath", "pavement", "traffic jam", "dug up", "accident",
        "junction", "uneven",
    ],
    "sanitation": [
        "garbage", "trash", "toilet", "dead animal", "carcass", "stray animals",
        "cleaned", "waste",
    ],
}

FULL_KEYWORDS_KN: dict[str, list[str]] = {
    "electrical_emergency": [
        "ಕಿಡಿ", "ಶಾಕ್", "ವಿದ್ಯುತ್ ತಂತಿ", "ಬೆಂಕಿ", "ಗುಂಯ್", "ಸುಟ್ಟ ವಾಸನೆ",
        "ತುರ್ತು", "ಅಪಾಯಕಾರಿ",
    ],
    "electrical_maintenance": [
        "ಬೀದಿ ದೀಪ", "ಫ್ಲಿಕರ್", "ಮೀಟರ್", "ಬಿಲ್", "ದುರಸ್ತಿ", "ಆರಿ ಹೋಗಿ",
    ],
    "water_supply": [
        "ನೀರು ಪೂರೈಕೆ", "ಪೈಪ್‌ಲೈನ್", "ಪೈಪ್", "ಒಡೆದ", "ಕೆಸರು", "ಒತ್ತಡ", "ಕಲುಷಿತ",
    ],
    "drainage": [
        "ಚರಂಡಿ", "ಕೊಳಚೆ", "ಉಕ್ಕಿ", "ದುರ್ವಾಸನೆ", "ಬ್ಲಾಕ್",
    ],
    "roads": [
        "ಗುಂಡಿ", "ಪಾದಚಾರಿ", "ಟ್ರಾಫಿಕ್", "ಅಗೆದ", "ಅಪಘಾತ", "ಜಂಕ್ಷನ್", "ಅಸಮ",
    ],
    "sanitation": [
        "ಕಸ", "ಶೌಚಾಲಯ", "ಶವ", "ಸ್ವಚ್ಛ", "ನಾಯಿ",
    ],
}

# small_model: same structure, proportionally trimmed to ~2 keywords/department in BOTH
# languages (not more aggressively cut for Kannada) to keep the comparison fair.
SMALL_KEYWORDS_EN: dict[str, list[str]] = {
    "electrical_emergency": ["spark", "fire"],
    "electrical_maintenance": ["streetlight", "meter"],
    "water_supply": ["water supply", "pipeline"],
    "drainage": ["drain", "sewage"],
    "roads": ["pothole", "traffic jam"],
    "sanitation": ["garbage", "toilet"],
}

SMALL_KEYWORDS_KN: dict[str, list[str]] = {
    "electrical_emergency": ["ಕಿಡಿ", "ಶಾಕ್"],
    "electrical_maintenance": ["ಬೀದಿ ದೀಪ", "ಮೀಟರ್"],
    "water_supply": ["ನೀರು ಪೂರೈಕೆ", "ಪೈಪ್"],
    "drainage": ["ಚರಂಡಿ", "ಕೊಳಚೆ"],
    "roads": ["ಗುಂಡಿ", "ಟ್ರಾಫಿಕ್"],
    "sanitation": ["ಕಸ", "ಶೌಚಾಲಯ"],
}

CONDITIONS = ["clean", "truncated", "small_model"]
LANGUAGES = {"en": "text_en", "native": "text_native"}


def load_config() -> dict[str, Any]:
    with open(REPO_ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def classify(text: str, keywords: dict[str, list[str]]) -> str:
    """Deterministic keyword-count classifier. Returns "" (unparseable) if nothing matches.

    Ties are broken by DEPARTMENTS order — a genuine limitation of a keyword baseline,
    not something to hide.
    """
    text_lower = text.lower()
    scores = {}
    for dept in DEPARTMENTS:
        count = sum(text_lower.count(kw.lower()) for kw in keywords[dept])
        scores[dept] = count
    best_dept = max(DEPARTMENTS, key=lambda d: scores[d])
    if scores[best_dept] == 0:
        return ""
    return best_dept


def classify_one(text: str, condition: str, truncate_chars: int) -> str:
    if condition == "clean":
        return classify(text, FULL_KEYWORDS_EN if _looks_english(text) else FULL_KEYWORDS_KN)
    if condition == "truncated":
        truncated_text = text[:truncate_chars]
        return classify(truncated_text, FULL_KEYWORDS_EN if _looks_english(text) else FULL_KEYWORDS_KN)
    if condition == "small_model":
        return classify(text, SMALL_KEYWORDS_EN if _looks_english(text) else SMALL_KEYWORDS_KN)
    raise ValueError(f"unknown condition: {condition}")


def _looks_english(text: str) -> bool:
    """True if text is ASCII-dominant (i.e. the English column, not the native-script one)."""
    ascii_letters = sum(1 for c in text if c.isascii() and c.isalpha())
    total_letters = sum(1 for c in text if c.isalpha())
    return total_letters == 0 or (ascii_letters / total_letters) > 0.5


def run_experiment(complaints: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    truncate_chars = cfg["d2"]["truncate_chars"]
    rows = []
    for _, row in complaints.iterrows():
        for lang_key, col in LANGUAGES.items():
            text = row[col]
            for condition in CONDITIONS:
                predicted = classify_one(text, condition, truncate_chars)
                correct = predicted == row["true_dept"]
                rows.append(
                    {
                        "id": row["id"],
                        "language": lang_key,
                        "condition": condition,
                        "predicted_dept": predicted,
                        "true_dept": row["true_dept"],
                        "correct": correct,
                    }
                )
    return pd.DataFrame(rows)


def accuracy_table(results: pd.DataFrame) -> pd.DataFrame:
    return (
        results.groupby(["language", "condition"])["correct"]
        .mean()
        .mul(100)
        .round(1)
        .reset_index()
        .rename(columns={"correct": "accuracy_pct"})
    )


def plot_accuracy(acc: pd.DataFrame, out_path: Path | None) -> plt.Figure:
    """Grouped bar chart of accuracy by condition × language. Saves to out_path if given; returns the figure."""
    # 1600x1000 px at dpi=150 per CLAUDE.md
    fig, ax = plt.subplots(figsize=(1600 / 150, 1000 / 150), dpi=150)
    x = range(len(CONDITIONS))
    width = 0.35

    en_vals = [
        acc[(acc.condition == c) & (acc.language == "en")]["accuracy_pct"].values[0]
        for c in CONDITIONS
    ]
    native_vals = [
        acc[(acc.condition == c) & (acc.language == "native")]["accuracy_pct"].values[0]
        for c in CONDITIONS
    ]

    ax.bar([i - width / 2 for i in x], en_vals, width, label="English", color="#4285f4")
    ax.bar([i + width / 2 for i in x], native_vals, width, label="Native script (Kannada)", color="#d93025")

    ax.set_xticks(list(x))
    ax.set_xticklabels(CONDITIONS, fontsize=14)
    ax.set_ylabel("Accuracy (%)", fontsize=14)
    ax.set_ylim(0, 105)
    ax.set_title("Classification accuracy by language and model condition", fontsize=16)
    ax.legend(fontsize=13)
    for i, v in enumerate(en_vals):
        ax.text(i - width / 2, v + 1.5, f"{v:.0f}%", ha="center", fontsize=11)
    for i, v in enumerate(native_vals):
        ax.text(i + width / 2, v + 1.5, f"{v:.0f}%", ha="center", fontsize=11)

    fig.tight_layout()
    if out_path is not None:
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"[d2_language] wrote {out_path}")
    return fig


def misroute_examples(results: pd.DataFrame, complaints: pd.DataFrame) -> pd.DataFrame:
    """Complaints correctly routed in English but misrouted in native script, per condition."""
    rows = []
    for condition in CONDITIONS:
        en = results[(results.condition == condition) & (results.language == "en")]
        native = results[(results.condition == condition) & (results.language == "native")]
        merged = en.merge(native, on="id", suffixes=("_en", "_native"))
        bad = merged[(merged.correct_en) & (~merged.correct_native)]
        for _, row in bad.iterrows():
            complaint = complaints[complaints.id == row["id"]].iloc[0]
            rows.append(
                {
                    "condition": condition,
                    "id": row["id"],
                    "true_dept": row["true_dept_en"],
                    "predicted_en": row["predicted_dept_en"],
                    "predicted_native": row["predicted_dept_native"] or "(unparseable)",
                    "text_en": complaint["text_en"],
                    "text_native": complaint["text_native"],
                }
            )
    return pd.DataFrame(rows, columns=["condition", "id", "true_dept", "predicted_en", "predicted_native", "text_en", "text_native"])


def print_misroute_examples(results: pd.DataFrame, complaints: pd.DataFrame) -> None:
    print("\n[d2_language] Complaints correctly routed in English but misrouted in native script:")
    examples = misroute_examples(results, complaints)
    for _, row in examples.iterrows():
        print(
            f"  [{row['condition']}] {row['id']}: true={row['true_dept']} | "
            f"EN -> {row['predicted_en']} (correct) | "
            f"native -> {row['predicted_native']} (WRONG)\n"
            f"      en: {row['text_en']}"
        )
    if examples.empty:
        print("  None found — report this honestly; do not tune the experiment to force examples.")
    print(f"[d2_language] total misroute examples: {len(examples)}")


def main() -> None:
    cfg = load_config()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    complaints = pd.read_csv(REPO_ROOT / "data" / "complaints.csv")
    print(f"[d2_language] loaded {len(complaints)} complaints")

    results = run_experiment(complaints, cfg)
    print(f"[d2_language] ran {len(results)} classifications")
    results_path = OUTPUTS_DIR / "d2_results.csv"
    results.to_csv(results_path, index=False)
    print(f"[d2_language] wrote {results_path}")

    acc = accuracy_table(results)
    acc_path = OUTPUTS_DIR / "d2_accuracy.csv"
    acc.to_csv(acc_path, index=False)
    print(f"[d2_language] wrote {acc_path}")
    print(acc.to_string(index=False))

    plot_accuracy(acc, OUTPUTS_DIR / "d2_chart.png")
    print_misroute_examples(results, complaints)


if __name__ == "__main__":
    main()
