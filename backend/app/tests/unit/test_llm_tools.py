from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.models import Task
from app.services.llm_service import LLMService

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "tool,resource",
    [
        ("get_contacts", "contacts"),
        ("get_deals", "deals"),
        ("get_products", "products"),
        ("get_invoices", "invoices"),
        ("get_projects", "projects"),
    ],
)
@pytest.mark.parametrize(
    "arguments,expected",
    [({}, 10), ({"limit": 1}, 1), ({"limit": 50}, 50), ({"limit": 51}, 50)],
)
async def test_tool_result_limits(
    db: Mock, tool: str, resource: str, arguments: dict, expected: int
) -> None:
    assert await LLMService(db).execute_tool(tool, arguments) == {resource: []}
    db.query.return_value.limit.assert_called_once_with(expected)


async def test_create_task_requires_existing_project(db: Mock) -> None:
    result = await LLMService(db).execute_tool(
        "create_task", {"project_id": 99, "title": "Task"}
    )
    assert result == {"error": "Project 99 not found"}
    db.add.assert_not_called()
    db.commit.assert_not_called()


async def test_create_task_persists_valid_project_and_details(db: Mock) -> None:
    db.query.return_value.first.return_value = SimpleNamespace(id=7)
    result = await LLMService(db).execute_tool(
        "create_task",
        {
            "project_id": 7,
            "title": "Task",
            "description": "Details",
            "priority": "high",
        },
    )
    task = db.add.call_args.args[0]
    assert isinstance(task, Task)
    assert (task.project_id, task.title, task.description, task.priority) == (
        7,
        "Task",
        "Details",
        "high",
    )
    assert result["success"] is True
    db.commit.assert_called_once_with()
    db.rollback.assert_not_called()


@pytest.mark.parametrize(
    "tool,arguments",
    [
        ("create_contact", {"first_name": "Alex", "last_name": "User"}),
        ("create_task", {"project_id": 7, "title": "Task"}),
    ],
)
async def test_failed_tool_write_rolls_back(
    db: Mock, tool: str, arguments: dict
) -> None:
    db.query.return_value.first.return_value = SimpleNamespace(id=7)
    db.commit.side_effect = RuntimeError("database unavailable")
    result = await LLMService(db).execute_tool(tool, arguments)
    assert result == {"error": "database unavailable"}
    db.rollback.assert_called_once_with()


async def test_failed_tool_read_rolls_back(db: Mock) -> None:
    db.query.return_value.all.side_effect = RuntimeError("query failed")
    assert await LLMService(db).execute_tool("get_products", {}) == {
        "error": "query failed"
    }
    db.rollback.assert_called_once_with()


def test_named_prompt_template_is_loaded_from_mapped_model(db: Mock) -> None:
    from app.models import AIPromptTemplate

    db.query.return_value.first.return_value = AIPromptTemplate(
        name="summary", is_active=True, system_prompt="Summarize the report"
    )
    assert LLMService(db).build_system_prompt("summary") == "Summarize the report"
    db.query.assert_called_once_with(AIPromptTemplate)
