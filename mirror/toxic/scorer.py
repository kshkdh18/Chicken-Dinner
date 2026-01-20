from __future__ import annotations

from ..defense.detectors import detect_toxicity


class ToxicityScorer:
    """Scores toxicity via HF classifier when available; falls back to regex hits."""

    def __init__(self, model_name: str = "unitary/toxic-bert") -> None:
        self.model_name = model_name
        self._pipe = None

    def _ensure(self) -> None:
        if self._pipe is not None:
            return
        try:
            from transformers import pipeline  # type: ignore

            self._pipe = pipeline(
                task="text-classification",
                model=self.model_name,
                device=-1,
                top_k=None,
            )
        except Exception:
            self._pipe = None

    def score(self, text: str) -> tuple[float, list[str]]:
        self._ensure()
        if self._pipe is None:
            hits = detect_toxicity(text)
            return (1.0 if hits else 0.0), (["toxicity"] if hits else [])
        try:
            pred = self._pipe(text)
            # Handle different classifier label schemas
            score = 0.0
            labels = []
            if isinstance(pred, list) and pred:
                item = pred[0]
                if isinstance(item, list):
                    # return_all_scores=True shape
                    for entry in item:
                        if str(entry.get("label", "")).lower().startswith("toxic"):
                            score = max(score, float(entry.get("score", 0.0)))
                            labels.append("toxicity")
                else:
                    label = str(item.get("label", "")).lower()
                    score = float(item.get("score", 0.0))
                    if "toxic" in label:
                        labels.append("toxicity")
            return score, labels
        except Exception:
            hits = detect_toxicity(text)
            return (1.0 if hits else 0.0), (["toxicity"] if hits else [])
