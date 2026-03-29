"""LLM-as-judge evaluator for the RAG pipeline.

For each sample it runs the real retrieval + generation, then asks the LLM to
score four standard RAG metrics on a 0..1 scale:

  - faithfulness      — is the answer grounded in the retrieved context?
  - answer_relevancy  — does the answer actually address the question?
  - context_recall    — do the retrieved contexts cover the reference answer?
  - context_precision — are the retrieved contexts relevant (not noise)?

No external eval framework — the metrics are computed transparently here so the
methodology is fully inspectable.
"""

import json
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.llm import llm as _llm, provider_kwargs
from backend.evaluation.schemas import EvalSample, EvalResult
from backend.prompts.report import build_report_prompt
from backend.retrieval.context_assembler import ContextAssembler
from backend.retrieval.hybrid_retriever import HybridRetriever

log = logging.getLogger("verity.evaluation")


# NOTE: braces in the JSON example are doubled ({{ }}) because every metric prompt
# below is built by concatenating this preamble and then calling str.format() on it.
# Single braces here would be parsed as format fields and raise KeyError: '"score"'.
_JUDGE_PREAMBLE = (
    "You are a strict, impartial evaluator of a retrieval-augmented QA system. "
    "Score the metric below from 0.0 (worst) to 1.0 (best). "
    'Respond with ONLY a JSON object: {{"score": <number 0..1>, "reason": "<one sentence>"}}.'
)

_FAITHFULNESS = _JUDGE_PREAMBLE + (
    "\n\nMETRIC — FAITHFULNESS: What fraction of the factual claims in the ANSWER are "
    "directly supported by the CONTEXT? 1.0 = every claim supported, 0.0 = unsupported "
    "or the answer is empty.\n\nCONTEXT:\n{context}\n\nANSWER:\n{answer}"
)
_RELEVANCY = _JUDGE_PREAMBLE + (
    "\n\nMETRIC — ANSWER RELEVANCY: How well does the ANSWER address the QUESTION? "
    "1.0 = fully on-point and complete, 0.0 = irrelevant or empty.\n\n"
    "QUESTION:\n{question}\n\nANSWER:\n{answer}"
)
_RECALL = _JUDGE_PREAMBLE + (
    "\n\nMETRIC — CONTEXT RECALL: What fraction of the key facts in the REFERENCE answer "
    "are present in the CONTEXT? 1.0 = all present, 0.0 = none.\n\n"
    "REFERENCE:\n{ground_truth}\n\nCONTEXT:\n{context}"
)
_PRECISION = _JUDGE_PREAMBLE + (
    "\n\nMETRIC — CONTEXT PRECISION: What fraction of the CONTEXT passages are actually "
    "relevant to answering the QUESTION (vs. noise)? 1.0 = all relevant, 0.0 = all noise.\n\n"
    "QUESTION:\n{question}\n\nCONTEXT:\n{context}"
)


def _parse_score(text: str) -> float | None:
    """Pull a 0..1 score out of a judge response (JSON preferred, float fallback)."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            score = float(json.loads(m.group(0))["score"])
            return max(0.0, min(1.0, score))
        except Exception:
            pass
    m = re.search(r"\d+(?:\.\d+)?", text)
    if m:
        try:
            score = float(m.group(0))
            if score > 1.0:  # model returned a percentage
                score /= 100.0
            return max(0.0, min(1.0, score))
        except Exception:
            pass
    return None


class RAGEvaluator:
    def __init__(self, retriever: HybridRetriever | None = None, top_k: int = 5):
        # Default to the same fast config the chat uses (dense + sparse + RRF).
        self.retriever = retriever or HybridRetriever(use_hyde=False, use_graph=False)
        self.assembler = ContextAssembler()
        self.top_k = top_k

    async def run(self, samples: list[EvalSample], db: AsyncSession) -> list[EvalResult]:
        results: list[EvalResult] = []
        for i, sample in enumerate(samples, 1):
            log.info("[eval] %d/%d — %s", i, len(samples), sample.question[:60])
            await self._answer(sample, db)
            results.append(self._score(sample))
        return results

    async def _answer(self, sample: EvalSample, db: AsyncSession) -> None:
        """Run retrieval + generation; fills sample.contexts and sample.answer."""
        chunks, _ = await self.retriever.retrieve(query=sample.question, db=db, top_k=self.top_k)
        sample.contexts = [c.text for c in chunks]
        if not chunks:
            sample.answer = ""
            return
        prompt = build_report_prompt(
            context=self.assembler.assemble(chunks),
            question=sample.question,
        )
        resp = _llm.chat.completions.create(
            **provider_kwargs(),
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1024,
        )
        sample.answer = (resp.choices[0].message.content or "").strip()

    def _score(self, sample: EvalSample) -> EvalResult:
        ctx = "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(sample.contexts)) or "(no context retrieved)"
        return EvalResult(
            faithfulness=self._judge(_FAITHFULNESS.format(context=ctx, answer=sample.answer or "(empty)")),
            answer_relevancy=self._judge(_RELEVANCY.format(question=sample.question, answer=sample.answer or "(empty)")),
            context_recall=self._judge(_RECALL.format(ground_truth=sample.ground_truth, context=ctx)),
            context_precision=self._judge(_PRECISION.format(question=sample.question, context=ctx)),
        )

    def _judge(self, prompt: str) -> float | None:
        try:
            resp = _llm.chat.completions.create(
                **provider_kwargs(),
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
            )
            return _parse_score((resp.choices[0].message.content or "").strip())
        except Exception as exc:
            log.warning("[eval] judge call failed: %s", exc)
            return None
