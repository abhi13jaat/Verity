from backend.evaluation.schemas import EvalResult, EvalSample


def test_eval_sample_defaults():
    sample = EvalSample(
        question="What is RAG?",
        ground_truth="RAG combines retrieval with LLM generation.",
    )
    assert sample.answer == ""
    assert sample.contexts == []


def test_eval_result_summary():
    result = EvalResult(
        faithfulness=0.85,
        answer_relevancy=0.90,
        context_recall=0.75,
        context_precision=0.80,
    )
    summary = result.summary()
    assert summary["faithfulness"] == 0.85
    assert summary["answer_relevancy"] == 0.9
    assert summary["context_recall"] == 0.75
    assert summary["context_precision"] == 0.8


def test_eval_result_summary_with_none():
    result = EvalResult(
        faithfulness=None,
        answer_relevancy=0.90,
        context_recall=None,
        context_precision=0.80,
    )
    summary = result.summary()
    assert summary["faithfulness"] is None
    assert summary["context_recall"] is None
