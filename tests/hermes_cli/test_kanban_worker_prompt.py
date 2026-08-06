"""Tests for kanban worker initial-prompt construction.

The worker prompt used to be only ``work kanban task <id>`` and relied on
kanban tools to fetch the body — those tools are not reliably exposed, so
workers stalled on empty tasks. The prompt now embeds the task ID, title,
and full body between clear delimiters, with an explicit marker when no
body was provided.
"""
from __future__ import annotations

from hermes_cli import kanban_db as kb


def _make_task(*, body):
    return kb.Task(
        id="t_prompt1",
        title="Fix the thing",
        body=body,
        assignee="coder",
        status="ready",
        priority=0,
        created_by="test",
        created_at=1,
        started_at=None,
        completed_at=None,
        workspace_kind="scratch",
        workspace_path=None,
        claim_lock=None,
        claim_expires=None,
        tenant=None,
        current_run_id=None,
    )


def test_prompt_contains_id_title_body_and_delimiters():
    task = _make_task(body="Step one.\nStep two with === sneaky markers ===.")
    prompt = kb._build_worker_prompt(task)

    assert prompt.startswith("work kanban task t_prompt1")
    assert kb._WORKER_PROMPT_BEGIN in prompt
    assert kb._WORKER_PROMPT_END in prompt
    assert "Task ID: t_prompt1" in prompt
    assert "Title: Fix the thing" in prompt
    assert "Step one.\nStep two with === sneaky markers ===." in prompt
    # Body sits between the delimiters.
    assert prompt.index(kb._WORKER_PROMPT_BEGIN) < prompt.index("Step one.")
    assert prompt.index("Step one.") < prompt.index(kb._WORKER_PROMPT_END)
    assert kb._WORKER_PROMPT_NO_BODY not in prompt


def test_prompt_without_body_gets_explicit_marker():
    task = _make_task(body=None)
    prompt = kb._build_worker_prompt(task)

    assert "Task ID: t_prompt1" in prompt
    assert "Title: Fix the thing" in prompt
    assert kb._WORKER_PROMPT_NO_BODY in prompt
    assert prompt.index(kb._WORKER_PROMPT_BEGIN) < prompt.index(
        kb._WORKER_PROMPT_NO_BODY
    ) < prompt.index(kb._WORKER_PROMPT_END)


def test_prompt_with_empty_string_body_gets_marker():
    task = _make_task(body="")
    prompt = kb._build_worker_prompt(task)
    assert kb._WORKER_PROMPT_NO_BODY in prompt
