"""
LLM-as-judge evaluation — compares retrieval WITHOUT vs WITH the cross-encoder
reranker on a small golden question set.

Usage:
    python -m scripts.run_eval

Requires a populated knowledge base (ingest a few RAG papers first, e.g.
`python -m scripts.arxiv_ingest --query "retrieval augmented generation" --max 5 --domain ml`).
"""

import asyncio
import json
import os
from datetime import datetime, timezone

from backend.db.postgres import AsyncSessionLocal
from backend.evaluation.evaluator import RAGEvaluator
from backend.evaluation.schemas import EvalSample
from backend.retrieval.hybrid_retriever import HybridRetriever

METRICS = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]

# Golden dataset — manually written ground-truth answers.
# 20 curated Q/ground-truth pairs over core RAG / retrieval / LLM concepts,
# answerable from a "retrieval augmented generation" arXiv corpus.
EVAL_SAMPLES = [
    EvalSample(
        question="What is RAG and how does it work?",
        ground_truth=(
            "RAG (Retrieval-Augmented Generation) combines information retrieval with "
            "large language model generation. It embeds a query into a vector, searches "
            "a vector database for the most similar document chunks, and uses those chunks "
            "as context for the LLM to generate an accurate, grounded answer."
        ),
    ),
    EvalSample(
        question="What is dense retrieval?",
        ground_truth=(
            "Dense retrieval uses vector embeddings to find semantically similar documents. "
            "Each chunk is converted into a high-dimensional vector and approximate "
            "nearest-neighbour algorithms like HNSW are used to find the closest vectors at query time."
        ),
    ),
    EvalSample(
        question="What is hybrid retrieval and what is RRF?",
        ground_truth=(
            "Hybrid retrieval combines dense vector search with sparse keyword search such as "
            "BM25 or PostgreSQL full-text search. Results from both are fused using "
            "Reciprocal Rank Fusion (RRF), which balances exact keyword matches with semantic similarity."
        ),
    ),
    EvalSample(
        question="What are chunking strategies in RAG?",
        ground_truth=(
            "Chunking strategies determine how documents are split before embedding. "
            "Recursive character splitting is a good default for plain text and PDFs. "
            "Markdown-aware splitting respects heading boundaries. "
            "Semantic chunking uses embeddings to detect topic shifts and create more coherent chunks."
        ),
    ),
    EvalSample(
        question="What is sparse retrieval and how does BM25 work?",
        ground_truth=(
            "Sparse retrieval ranks documents by exact lexical term overlap with the query rather "
            "than semantic meaning. BM25 is the standard algorithm: it scores documents using term "
            "frequency and inverse document frequency, rewarding rare query terms and applying "
            "length normalization so long documents are not unfairly favored. It excels at exact "
            "keyword and rare-entity matches where dense embeddings can miss."
        ),
    ),
    EvalSample(
        question="Why are embeddings central to semantic search?",
        ground_truth=(
            "Embeddings map text into dense numeric vectors so that semantically similar passages "
            "lie close together in vector space. A retriever embeds the query and the document chunks "
            "with the same model, then ranks chunks by vector similarity such as cosine. This lets the "
            "system match meaning rather than exact words, retrieving relevant passages even when they "
            "share no keywords with the query."
        ),
    ),
    EvalSample(
        question="What is HyDE (Hypothetical Document Embeddings)?",
        ground_truth=(
            "HyDE first asks the LLM to generate a hypothetical answer to the query, then embeds that "
            "generated document instead of the raw query for retrieval. Because the hypothetical answer "
            "is closer in form and vocabulary to real relevant passages than a short question is, its "
            "embedding retrieves better matches. It improves zero-shot dense retrieval without any "
            "labeled training data."
        ),
    ),
    EvalSample(
        question="How does RAG reduce hallucinations in large language models?",
        ground_truth=(
            "LLMs hallucinate because they generate from parametric memory that may be outdated, "
            "incomplete, or fabricated. RAG grounds generation by retrieving relevant source passages "
            "and instructing the model to answer only from that context, so claims are tied to "
            "verifiable evidence. This reduces hallucination, supports citations, and lets the system "
            "answer about knowledge not seen during training."
        ),
    ),
    EvalSample(
        question="How does RAG differ from fine-tuning for adding knowledge to a model?",
        ground_truth=(
            "Fine-tuning bakes new knowledge into the model weights through additional training, which "
            "is costly, hard to update, and prone to forgetting. RAG instead keeps knowledge in an "
            "external store and retrieves it at query time, so the knowledge base can be updated "
            "instantly without retraining. RAG is preferred for frequently changing or large factual "
            "knowledge, while fine-tuning is better for teaching style, format, or task behavior."
        ),
    ),
    EvalSample(
        question="What is reranking and why does it improve retrieval?",
        ground_truth=(
            "Reranking is a second retrieval stage that reorders an initial candidate set to push the "
            "most relevant passages to the top. A first-stage retriever favors recall and returns many "
            "candidates cheaply, then a more expensive, more accurate model rescores them. This "
            "two-stage design improves final precision while keeping latency manageable."
        ),
    ),
    EvalSample(
        question="What is the difference between a bi-encoder and a cross-encoder?",
        ground_truth=(
            "A bi-encoder encodes the query and each document independently into vectors and compares "
            "them with a similarity function, which is fast and lets documents be embedded and indexed "
            "ahead of time. A cross-encoder feeds the query and a document together through the model "
            "and outputs a single relevance score, which is far more accurate but too expensive to run "
            "over a whole corpus. Bi-encoders are used for first-stage retrieval and cross-encoders for "
            "reranking a small candidate set."
        ),
    ),
    EvalSample(
        question="What is approximate nearest neighbor search and why is it needed?",
        ground_truth=(
            "Comparing the query vector to every document vector (exact nearest neighbor) is too slow "
            "at scale. Approximate nearest neighbor algorithms such as HNSW build an index that finds "
            "the closest vectors in sub-linear time by trading a small amount of recall for large speed "
            "gains. This makes real-time dense retrieval over millions of chunks feasible."
        ),
    ),
    EvalSample(
        question="What are the roles of the retriever and the generator in a RAG system?",
        ground_truth=(
            "A RAG system has two components: a retriever that finds relevant passages from a knowledge "
            "base for a given query, and a generator (an LLM) that conditions on those passages to "
            "produce the final answer. The retriever determines what evidence is available, so "
            "retrieval quality bounds answer quality, while the generator synthesizes, reasons over, "
            "and cites that evidence."
        ),
    ),
    EvalSample(
        question="What is RAPTOR and how does hierarchical summarization help retrieval?",
        ground_truth=(
            "RAPTOR builds a hierarchical tree over a corpus by recursively clustering chunks and "
            "summarizing each cluster with an LLM, producing higher-level summary nodes on top of the "
            "leaf chunks. At query time it can retrieve from any level of the tree, so broad questions "
            "match high-level summaries while specific questions match detailed leaves. This improves "
            "retrieval for questions that require integrating information across many sections."
        ),
    ),
    EvalSample(
        question="What is GraphRAG and when is graph-based retrieval useful?",
        ground_truth=(
            "GraphRAG augments retrieval with a knowledge graph of entities and the relationships "
            "between them, extracted from the documents. Instead of relying only on text-chunk "
            "similarity, it can traverse entity links to gather connected evidence, which helps "
            "multi-hop questions that span several documents. It is especially useful for queries "
            "about relationships, aggregations, or global structure that flat chunk retrieval handles poorly."
        ),
    ),
    EvalSample(
        question="What is query expansion or query rewriting in retrieval?",
        ground_truth=(
            "Query expansion or rewriting reformulates the user's original query before retrieval to "
            "improve recall. Techniques include adding synonyms or related terms, decomposing a complex "
            "question into simpler sub-queries, or using an LLM to rephrase a vague or conversational "
            "query into a precise search query. This bridges the vocabulary mismatch between how users "
            "ask and how answers are written."
        ),
    ),
    EvalSample(
        question="How are RAG systems evaluated?",
        ground_truth=(
            "RAG systems are evaluated on both retrieval and generation quality. Common metrics are "
            "faithfulness (are the answer's claims supported by the retrieved context), answer relevancy "
            "(does the answer address the question), context recall (do the retrieved passages contain "
            "the information needed for the reference answer), and context precision (what fraction of "
            "retrieved passages are actually relevant). Together they separate retrieval errors from "
            "generation errors."
        ),
    ),
    EvalSample(
        question="Why is RAG well-suited to knowledge-intensive tasks?",
        ground_truth=(
            "Knowledge-intensive tasks such as open-domain question answering and fact verification "
            "require specific facts that a model cannot reliably store in its parameters. RAG suits them "
            "because it retrieves the exact supporting passages on demand, grounding answers in current, "
            "verifiable sources. This yields more accurate, up-to-date, and attributable answers than a "
            "closed-book model of comparable size."
        ),
    ),
    EvalSample(
        question="What is the difference between semantic search and keyword search?",
        ground_truth=(
            "Keyword (lexical) search matches the literal terms in the query against documents and is "
            "precise for exact phrases, names, and rare identifiers but fails when different words "
            "express the same meaning. Semantic (vector) search compares embeddings and matches by "
            "meaning, so it finds relevant passages that share no keywords, but it can miss exact terms. "
            "Hybrid retrieval combines both to get the strengths of each."
        ),
    ),
    EvalSample(
        question="What is multi-hop retrieval and why is it needed?",
        ground_truth=(
            "Some questions cannot be answered from a single passage and require chaining evidence from "
            "multiple sources, known as multi-hop retrieval. The system retrieves an initial passage, "
            "uses what it finds to form a follow-up query, and retrieves again, accumulating the facts "
            "needed to answer. Iterative, multi-step retrieval improves coverage for complex, "
            "compositional questions over single-shot retrieval."
        ),
    ),
]


def _averages(results) -> dict:
    acc = {m: [] for m in METRICS}
    for r in results:
        summary = r.summary()
        for m in METRICS:
            if summary[m] is not None:
                acc[m].append(summary[m])
    return {m: (round(sum(v) / len(v), 4) if v else None) for m, v in acc.items()}


async def _run_config(name: str, retriever: HybridRetriever, db) -> dict:
    print(f"\n--- {name} ---")
    results = await RAGEvaluator(retriever).run(EVAL_SAMPLES, db=db)
    avg = _averages(results)
    for m in METRICS:
        print(f"  {m:<20} {avg[m]}")
    return avg


async def main() -> None:
    os.makedirs("reports", exist_ok=True)
    print(f"\nEvaluating {len(EVAL_SAMPLES)} samples — baseline vs reranker...")

    configs = [
        ("baseline", HybridRetriever(use_hyde=False, use_graph=False, use_rerank=False)),
        ("reranker", HybridRetriever(use_hyde=False, use_graph=False, use_rerank=True)),
    ]
    scores = {}
    async with AsyncSessionLocal() as db:
        for name, retriever in configs:
            scores[name] = await _run_config(name, retriever, db)

    # Comparison table
    print("\n" + "=" * 60)
    print(f"{'metric':<22}{'baseline':<12}{'reranker':<12}{'delta':<10}")
    print("-" * 60)
    base, rer = scores["baseline"], scores["reranker"]
    for m in METRICS:
        b, r = base[m], rer[m]
        delta = f"{r - b:+.4f}" if (b is not None and r is not None) else "—"
        print(f"{m:<22}{str(b):<12}{str(r):<12}{delta:<10}")

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "samples": len(EVAL_SAMPLES),
        "baseline": base,
        "reranker": rer,
    }
    with open("reports/eval_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved → reports/eval_report.json")


if __name__ == "__main__":
    asyncio.run(main())
