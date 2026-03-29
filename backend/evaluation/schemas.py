from dataclasses import dataclass, field


@dataclass
class EvalSample:
    question: str
    ground_truth: str
    answer: str = ""
    contexts: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    faithfulness: float | None
    answer_relevancy: float | None
    context_recall: float | None
    context_precision: float | None

    def summary(self) -> dict:
        def fmt(v):
            return round(float(v), 4) if v is not None else None

        return {
            "faithfulness": fmt(self.faithfulness),
            "answer_relevancy": fmt(self.answer_relevancy),
            "context_recall": fmt(self.context_recall),
            "context_precision": fmt(self.context_precision),
        }
