from datetime import datetime
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models import (
    Company,
    Contact,
    Document,
    Employee,
    Product,
    SearchIndex,
    SearchQuery,
    SearchSuggestion,
)


class SearchService:
    """Advanced search service with PostgreSQL full-text search."""

    def __init__(self, db: Session):
        """Use the supplied session for searches and committed index or analytics writes."""
        self.db = db

    # ==================== INDEXING ====================

    def index_entity(
        self,
        entity_type: str,
        entity_id: int,
        title: str,
        content: str,
        metadata: dict[str, Any] = None,
        tags: list[str] = None,
    ):
        """Index or update an entity in the search index and commit the session.

        Replace title, content, and metadata for the entity type and ID. Missing
        metadata becomes an empty mapping; ``tags`` is ignored. Database errors
        propagate.
        """
        searchable = f"{title} {content}"
        if metadata:
            for _key, value in metadata.items():
                if isinstance(value, (str, int, float)):
                    searchable += f" {value}"

        existing = (
            self.db.query(SearchIndex)
            .filter(
                SearchIndex.entity_type == entity_type,
                SearchIndex.entity_id == entity_id,
            )
            .first()
        )

        if existing:
            existing.title = title
            existing.content = content
            existing.meta_data = metadata or {}
            existing.updated_at = datetime.utcnow()
        else:
            index = SearchIndex(
                entity_type=entity_type,
                entity_id=entity_id,
                title=title,
                content=content,
                meta_data=metadata or {},
            )
            self.db.add(index)

        self.db.commit()

    def remove_from_index(self, entity_type: str, entity_id: int):
        """Remove an entity from the search index."""
        self.db.query(SearchIndex).filter(
            SearchIndex.entity_type == entity_type, SearchIndex.entity_id == entity_id
        ).delete()
        self.db.commit()

    def index_all_contacts(self):
        """Index all contacts."""
        contacts = self.db.query(Contact).all()
        for c in contacts:
            self.index_entity(
                "contact",
                c.id,
                f"{c.first_name} {c.last_name}",
                f"{c.email or ''} {c.phone or ''} {c.title or ''} {c.notes or ''}",
                metadata={
                    "email": c.email,
                    "phone": c.phone,
                    "status": c.status,
                    "company_id": c.company_id,
                    "assigned_to": c.assigned_to,
                },
            )

    def index_all_companies(self):
        """Index all companies."""
        companies = self.db.query(Company).all()
        for c in companies:
            self.index_entity(
                "company",
                c.id,
                c.name,
                f"{c.industry or ''} {c.website or ''} {c.address or ''} {c.phone or ''}",
                metadata={"industry": c.industry, "size": c.size, "website": c.website},
            )

    def index_all_products(self):
        """Index all products."""
        products = self.db.query(Product).all()
        for p in products:
            self.index_entity(
                "product",
                p.id,
                p.name,
                f"{p.sku} {p.description or ''} {p.category or ''} {p.supplier or ''}",
                metadata={
                    "sku": p.sku,
                    "category": p.category,
                    "price": float(p.unit_price) if p.unit_price else 0,
                    "stock": p.quantity_in_stock,
                    "status": p.status,
                },
            )

    def index_all_employees(self):
        """Index all employees."""
        employees = self.db.query(Employee).all()
        for e in employees:
            self.index_entity(
                "employee",
                e.id,
                e.employee_code,
                f"{e.job_title or ''} {e.address or ''} {e.emergency_contact or ''}",
                metadata={
                    "code": e.employee_code,
                    "department_id": e.department_id,
                    "status": e.status,
                    "employment_type": e.employment_type,
                },
            )

    def index_all_documents(self):
        """Index all documents."""
        documents = self.db.query(Document).all()
        for d in documents:
            self.index_entity(
                "document",
                d.id,
                d.title,
                f"{d.filename} {d.extracted_text or ''} {d.mime_type or ''}",
                metadata={
                    "filename": d.filename,
                    "mime_type": d.mime_type,
                    "entity_type": d.entity_type,
                    "file_size": d.file_size,
                },
            )

    def reindex_all(self):
        """Reindex all entities."""
        self.db.query(SearchIndex).delete()
        self.db.commit()

        self.index_all_contacts()
        self.index_all_companies()
        self.index_all_products()
        self.index_all_employees()
        self.index_all_documents()

        return {
            "contacts": self.db.query(SearchIndex)
            .filter(SearchIndex.entity_type == "contact")
            .count(),
            "companies": self.db.query(SearchIndex)
            .filter(SearchIndex.entity_type == "company")
            .count(),
            "products": self.db.query(SearchIndex)
            .filter(SearchIndex.entity_type == "product")
            .count(),
            "employees": self.db.query(SearchIndex)
            .filter(SearchIndex.entity_type == "employee")
            .count(),
            "documents": self.db.query(SearchIndex)
            .filter(SearchIndex.entity_type == "document")
            .count(),
        }

    # ==================== SEARCH ====================

    def search(
        self,
        query: str,
        entity_types: list[str] = None,
        filters: dict[str, Any] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int, float]:
        """Return a page of matching index records, total before pagination, and execution time in ms.

        Search title and content using English full-text prefix terms joined
        with AND; blank queries omit text filtering. ``metadata.*`` filters
        compare text values, while tags and other filter keys are ignored.
        Results are ordered newest-update first with 200-character previews.
        Database errors, including invalid tsquery syntax, propagate.
        """
        start_time = datetime.utcnow()

        base_query = self.db.query(SearchIndex)

        if query and query.strip():
            search_terms = query.strip().split()
            tsquery = " & ".join([f"{term}:*" for term in search_terms])

            base_query = base_query.filter(
                text(
                    "to_tsvector('english', title || ' ' || coalesce(content, '')) @@ to_tsquery('english', :query)"
                ).bindparams(query=tsquery)
            )

        if entity_types:
            base_query = base_query.filter(SearchIndex.entity_type.in_(entity_types))

        if filters:
            for key, value in filters.items():
                if key == "tags":
                    pass
                elif key.startswith("metadata."):
                    meta_key = key.replace("metadata.", "")
                    base_query = base_query.filter(
                        SearchIndex.meta_data[meta_key].astext == str(value)
                    )

        total = base_query.count()

        results = (
            base_query.order_by(SearchIndex.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        formatted = []
        for r in results:
            formatted.append(
                {
                    "id": r.id,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "title": r.title,
                    "content_preview": r.content[:200] if r.content else "",
                    "metadata": r.meta_data or {},
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
            )

        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        return formatted, total, execution_time

    def get_facets(
        self, query: str = None, entity_types: list[str] = None
    ) -> dict[str, Any]:
        """Return entity-type counts for the matching title/content search.

        Blank queries omit text filtering. Nonblank queries use English prefix
        terms joined with AND. ``tags`` is always empty. Database errors,
        including invalid tsquery syntax, propagate.
        """
        base_query = self.db.query(SearchIndex)

        if query and query.strip():
            search_terms = query.strip().split()
            tsquery = " & ".join([f"{term}:*" for term in search_terms])
            base_query = base_query.filter(
                text(
                    "to_tsvector('english', title || ' ' || coalesce(content, '')) @@ to_tsquery('english', :query)"
                ).bindparams(query=tsquery)
            )

        if entity_types:
            base_query = base_query.filter(SearchIndex.entity_type.in_(entity_types))

        type_counts = (
            self.db.query(
                SearchIndex.entity_type, func.count(SearchIndex.id).label("count")
            )
            .filter(SearchIndex.id.in_(base_query.with_entities(SearchIndex.id)))
            .group_by(SearchIndex.entity_type)
            .all()
        )

        return {
            "entity_types": [
                {"value": t.entity_type, "count": t.count} for t in type_counts
            ],
            "tags": [],
        }

    # ==================== SUGGESTIONS ====================

    def get_suggestions(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return unique matching query suggestions followed by matching titles.

        Queries shorter than two characters return an empty list. Matching uses
        case-insensitive SQL LIKE patterns; stored queries are ordered by usage
        count, followed by up to five title matches, then sliced to ``limit``.
        """
        if not query or len(query) < 2:
            return []

        suggestions = (
            self.db.query(SearchSuggestion)
            .filter(SearchSuggestion.query.ilike(f"%{query}%"))
            .order_by(SearchSuggestion.count.desc())
            .limit(limit)
            .all()
        )

        title_matches = (
            self.db.query(SearchIndex)
            .filter(SearchIndex.title.ilike(f"%{query}%"))
            .distinct(SearchIndex.title)
            .limit(5)
            .all()
        )

        result = []
        seen = set()

        for s in suggestions:
            if s.query not in seen:
                seen.add(s.query)
                result.append(
                    {
                        "text": s.query,
                        "type": "query",
                        "entity_type": s.entity_type,
                        "frequency": s.count,
                    }
                )

        for t in title_matches:
            if t.title and t.title not in seen:
                seen.add(t.title)
                result.append(
                    {
                        "text": t.title,
                        "type": "title",
                        "entity_type": t.entity_type,
                        "frequency": 0,
                    }
                )

        return result[:limit]

    def record_suggestion(
        self, query: str, entity_type: str = None, entity_id: int = None
    ):
        """Record a search query for suggestion building and commit the session.

        Lowercase and trim the query, incrementing its count for the given
        entity type or creating it with count one. ``entity_id`` is ignored.
        """
        existing = (
            self.db.query(SearchSuggestion)
            .filter(
                SearchSuggestion.query == query.lower().strip(),
                SearchSuggestion.entity_type == entity_type,
            )
            .first()
        )

        if existing:
            existing.count += 1
            existing.last_used = datetime.utcnow()
        else:
            suggestion = SearchSuggestion(
                query=query.lower().strip(), entity_type=entity_type, count=1
            )
            self.db.add(suggestion)

        self.db.commit()

    # ==================== ANALYTICS ====================

    def log_query(
        self,
        user_id: int,
        query: str,
        filters: dict[str, Any] = None,
        results_count: int = 0,
        execution_time_ms: int = 0,
    ):
        """Commit a search analytics record with execution time in milliseconds.

        Only the keys of ``filters`` are stored in ``entity_types``; filter
        values are discarded.
        """
        sq = SearchQuery(
            user_id=user_id,
            query=query,
            entity_types=list(filters.keys()) if filters else None,
            results_count=results_count,
            execution_time_ms=execution_time_ms,
        )
        self.db.add(sq)
        self.db.commit()

    def get_search_analytics(self, days: int = 30) -> dict[str, Any]:
        """Return query counts, popular queries/filters, and daily volume since ``days`` ago.

        The cutoff is inclusive and based on UTC. Return the no-results rate as
        a percentage and average execution time in milliseconds, both zero when
        no queries exist. Popular queries are limited to 20.
        """
        from datetime import datetime, timedelta

        start_date = datetime.utcnow() - timedelta(days=days)

        total_queries = (
            self.db.query(SearchQuery)
            .filter(SearchQuery.created_at >= start_date)
            .count()
        )

        top_queries = (
            self.db.query(SearchQuery.query, func.count(SearchQuery.id).label("count"))
            .filter(SearchQuery.created_at >= start_date)
            .group_by(SearchQuery.query)
            .order_by(func.count(SearchQuery.id).desc())
            .limit(20)
            .all()
        )

        no_results = (
            self.db.query(SearchQuery)
            .filter(
                SearchQuery.created_at >= start_date, SearchQuery.results_count == 0
            )
            .count()
        )

        avg_time = (
            self.db.query(func.avg(SearchQuery.execution_time_ms))
            .filter(SearchQuery.created_at >= start_date)
            .scalar()
            or 0
        )

        daily = (
            self.db.query(
                func.date(SearchQuery.created_at).label("date"),
                func.count(SearchQuery.id).label("count"),
            )
            .filter(SearchQuery.created_at >= start_date)
            .group_by(func.date(SearchQuery.created_at))
            .order_by("date")
            .all()
        )

        filter_usage = {}
        queries_with_filters = (
            self.db.query(SearchQuery)
            .filter(
                SearchQuery.created_at >= start_date,
                SearchQuery.entity_types.isnot(None),
            )
            .all()
        )
        for q in queries_with_filters:
            if q.entity_types:
                for key in q.entity_types:
                    filter_usage[key] = filter_usage.get(key, 0) + 1

        return {
            "period_days": days,
            "total_queries": total_queries,
            "no_results_queries": no_results,
            "no_results_rate": (
                (no_results / total_queries * 100) if total_queries > 0 else 0
            ),
            "avg_execution_time_ms": round(float(avg_time), 2),
            "top_queries": [{"query": q.query, "count": q.count} for q in top_queries],
            "daily_volume": [{"date": str(d.date), "queries": d.count} for d in daily],
            "popular_filters": [
                {"filter": k, "count": v}
                for k, v in sorted(
                    filter_usage.items(), key=lambda x: x[1], reverse=True
                )
            ],
        }
