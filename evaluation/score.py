"""Score the current DeFaketive model on a labelled CSV (high-confidence rows only).

    backend/.venv/Scripts/python.exe evaluation/score.py evaluation/gold_labels_200.csv [--misses]

Columns: id, stars, review_text, sentiment, flags (';'-separated or none), confidence (high|low).
"""
import collections
import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" / "sentiment-analysis"))
from defaketive_sentiment import registry  # noqa: E402

FLAGS = ("defect", "counterfeit", "safety", "not_as_described")


def predicted_flags(analysis):
    tags = set(analysis.get("review_tags") or []) | set(analysis.get("review_extra_tags") or [])
    return {flag for flag in FLAGS if flag in tags}


def main():
    path = pathlib.Path(sys.argv[1])
    show = "--misses" in sys.argv
    rows = [r for r in csv.DictReader(open(path, encoding="utf-8-sig")) if r["confidence"] == "high"]
    model = registry.load_model()
    right = 0
    counts = {flag: collections.Counter() for flag in FLAGS}
    misses = []
    for row in rows:
        analysis = model.analyze(row["review_text"], rating=int(row["stars"]))
        label = analysis.get("label")
        right += label == row["sentiment"]
        if label != row["sentiment"]:
            misses.append(f"sentiment gold={row['sentiment']} model={label} | {row['review_text'][:120]}")
        gold, predicted = set(row["flags"].split(";")), predicted_flags(analysis)
        for flag in FLAGS:
            outcome = ("tp" if flag in predicted else "fn") if flag in gold else ("fp" if flag in predicted else "tn")
            counts[flag][outcome] += 1
            if outcome in ("fn", "fp"):
                misses.append(f"{flag} {outcome} | {row['review_text'][:120]}")
    print(f"{path.name}: {len(rows)} high-confidence rows")
    print(f"sentiment accuracy {right}/{len(rows)} = {right / len(rows):.3f}")
    for flag in FLAGS:
        c = counts[flag]
        precision = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else float("nan")
        recall = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else float("nan")
        print(f"{flag:17} tp={c['tp']:3} fp={c['fp']:3} fn={c['fn']:3}  precision={precision:.2f} recall={recall:.2f}")
    if show:
        print()
        print("\n".join(misses))


main()
