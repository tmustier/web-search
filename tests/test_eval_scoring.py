from __future__ import annotations

from wstk.eval.scoring import normalize_url_for_match, score_search_results
from wstk.search.types import SearchResultItem


def test_normalize_url_for_match_strips_query_fragment_and_trailing_slash() -> None:
    assert (
        normalize_url_for_match("https://Example.COM/a/b/?x=1#frag")
        == "https://example.com/a/b"
    )


def test_score_search_results_domain_hit_rank_and_mrr() -> None:
    results = [
        SearchResultItem(
            title="Other",
            url="https://other.example/x",
            snippet=None,
            published_at=None,
            source_provider="fake",
        ),
        SearchResultItem(
            title="Docs",
            url="https://docs.python.org/3/library/venv.html",
            snippet=None,
            published_at=None,
            source_provider="fake",
        ),
    ]
    score = score_search_results(
        results,
        expected_domains=("docs.python.org",),
        expected_urls=(),
        k=10,
    )
    assert score.domain_hit is True
    assert score.domain_first_hit_rank == 2
    assert score.domain_mrr == 0.5


def test_score_search_results_url_hit() -> None:
    results = [
        SearchResultItem(
            title="Docs",
            url="https://go.dev/ref/mod/?utm=1",
            snippet=None,
            published_at=None,
            source_provider="fake",
        )
    ]
    score = score_search_results(
        results,
        expected_domains=(),
        expected_urls=("https://go.dev/ref/mod",),
        k=5,
    )
    assert score.url_hit is True
    assert score.url_first_hit_rank == 1
