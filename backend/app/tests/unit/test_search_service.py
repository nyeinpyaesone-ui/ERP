from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql

from app.models import SearchIndex, SearchQuery, SearchSuggestion
from app.services.search_service import SearchService

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("metadata", [None, {"status": "active", "stock": 0}])
def test_new_index_uses_mapped_metadata(db: Mock, metadata: dict | None) -> None:
    SearchService(db).index_entity(
        "product", 7, "Widget", "Description", metadata, tags=["legacy"]
    )
    index = db.add.call_args.args[0]
    assert isinstance(index, SearchIndex)
    assert (index.entity_type, index.entity_id, index.title, index.content) == (
        "product",
        7,
        "Widget",
        "Description",
    )
    assert index.meta_data == (metadata or {})
    db.commit.assert_called_once_with()


def test_reindex_updates_existing_record_and_clears_old_metadata(db: Mock) -> None:
    index = SearchIndex(id=1, title="Old", content="Old", meta_data={"obsolete": True})
    db.query.return_value.first.return_value = index
    SearchService(db).index_entity("product", 7, "New", "Updated")
    assert (index.title, index.content, index.meta_data) == ("New", "Updated", {})
    assert index.updated_at is not None
    db.add.assert_not_called()
    db.commit.assert_called_once_with()


@pytest.mark.parametrize(
    "content,metadata,updated",
    [(None, None, None), ("x" * 201, {"status": "active"}, datetime(2026, 1, 1))],
)
def test_search_returns_pair_and_serializes_mapped_fields(
    db: Mock, content: str | None, metadata: dict | None, updated: datetime | None
) -> None:
    db.query.return_value.all.return_value = [
        SearchIndex(
            id=3,
            entity_type="product",
            entity_id=7,
            title="Widget",
            content=content,
            meta_data=metadata,
            updated_at=updated,
        )
    ]
    db.query.return_value.count.return_value = 9
    rows, total = SearchService(db).search("", limit=2, offset=4)
    assert total == 9
    assert rows == [
        {
            "id": 3,
            "entity_type": "product",
            "entity_id": 7,
            "title": "Widget",
            "content_preview": (content or "")[:200],
            "metadata": metadata or {},
            "updated_at": updated.isoformat() if updated else None,
        }
    ]
    db.query.return_value.offset.assert_called_once_with(4)
    db.query.return_value.limit.assert_called_once_with(2)


def test_search_uses_bound_terms_and_mapped_json_metadata(db: Mock) -> None:
    SearchService(db).search(
        "  red widget  ",
        entity_types=["product"],
        filters={"metadata.status": "active"},
    )
    predicates = [call.args[0] for call in db.query.return_value.filter.call_args_list]
    text_query = predicates[0].compile(dialect=postgresql.dialect())
    assert text_query.params == {"query": "red:* & widget:*"}
    assert "coalesce(content, '')" in str(text_query)
    assert "searchable_text" not in str(text_query)
    json_query = predicates[-1].compile(dialect=postgresql.dialect())
    assert set(json_query.params.values()) == {"status", "active"}
    assert "metadata" in str(json_query)


@pytest.mark.parametrize("query", ["", " ", "\t"])
def test_empty_search_does_not_build_fulltext_predicate(db: Mock, query: str) -> None:
    assert SearchService(db).search(query) == ([], 0)
    db.query.return_value.filter.assert_not_called()


@pytest.mark.parametrize("existing", [False, True])
def test_record_suggestion_normalizes_query_and_counts_reuse(
    db: Mock, existing: bool
) -> None:
    suggestion = (
        SearchSuggestion(query="widget", entity_type="product", count=2)
        if existing
        else None
    )
    db.query.return_value.first.return_value = suggestion
    SearchService(db).record_suggestion("  WiDgEt  ", "product")
    if existing:
        assert suggestion.count == 3
        assert suggestion.last_used is not None
        db.add.assert_not_called()
    else:
        suggestion = db.add.call_args.args[0]
        assert (suggestion.query, suggestion.entity_type, suggestion.count) == (
            "widget",
            "product",
            1,
        )
    predicates = db.query.return_value.filter.call_args.args
    assert predicates[0].right.value == "widget"
    db.commit.assert_called_once_with()


@pytest.mark.parametrize("limit,expected_count", [(1, 1), (10, 2)])
def test_suggestions_use_mapped_columns_and_deduplicate_titles(
    db: Mock, limit: int, expected_count: int
) -> None:
    db.query.return_value.all.side_effect = [
        [SearchSuggestion(query="Widget", entity_type="product", count=8)],
        [
            SearchIndex(title="Widget", entity_type="product"),
            SearchIndex(title="Widget Pro", entity_type="product"),
            SearchIndex(title=None),
        ],
    ]
    expected = [
        {"text": "Widget", "type": "query", "entity_type": "product", "frequency": 8},
        {
            "text": "Widget Pro",
            "type": "title",
            "entity_type": "product",
            "frequency": 0,
        },
    ]
    assert SearchService(db).get_suggestions("Wi", limit) == expected[:expected_count]


@pytest.mark.parametrize(
    "filters,expected",
    [
        (None, None),
        ({}, None),
        ({"status": "active", "type": "product"}, ["status", "type"]),
    ],
)
def test_query_log_uses_existing_schema(
    db: Mock, filters: dict | None, expected: list[str] | None
) -> None:
    SearchService(db).log_query(
        42, "widget", filters, results_count=3, execution_time_ms=12
    )
    record = db.add.call_args.args[0]
    assert isinstance(record, SearchQuery)
    assert (
        record.user_id,
        record.query,
        record.results_count,
        record.execution_time_ms,
    ) == (42, "widget", 3, 12)
    assert record.entity_types == expected
    db.commit.assert_called_once_with()


def test_search_analytics_counts_filter_keys(db: Mock) -> None:
    db.query.return_value.count.side_effect = [4, 1]
    db.query.return_value.scalar.return_value = 12.345
    db.query.return_value.all.side_effect = [
        [],
        [],
        [
            SimpleNamespace(entity_types=["status", "type"]),
            SimpleNamespace(entity_types=["status"]),
            SimpleNamespace(entity_types=None),
        ],
    ]
    result = SearchService(db).get_search_analytics(days=7)
    assert result["period_days"] == 7
    assert result["no_results_rate"] == 25
    assert result["avg_execution_time_ms"] == 12.35
    assert result["popular_filters"] == [
        {"filter": "status", "count": 2},
        {"filter": "type", "count": 1},
    ]
