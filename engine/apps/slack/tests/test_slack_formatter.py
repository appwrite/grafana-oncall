from unittest.mock import MagicMock

import pytest

from apps.slack.slack_formatter import SlackFormatter


@pytest.mark.django_db
def test_slack_to_accepted_emoji():
    sf = SlackFormatter(MagicMock())
    test_message = """[:book: Runbook:link:](https://example-test.com/explore?panes=%7B:%7Bname-with-dash%22:%22FE%22:%5B%7B%22another-one%22:namespace-with-dash)
Test emoji :male-construction-worker:https://another-example.com/test:=%22-dash
:female-construction-worker:"""
    expected_result = test_message.replace("-construction-worker", "_construction_worker")
    result = sf.slack_to_accepted_emoji(test_message)
    assert result == expected_result


@pytest.mark.parametrize(
    "message,process_markdown,expected",
    [
        ("<@U123|alice> *on call* #incident", True, "<p>@alice <strong>on call</strong> <b>#incident</b></p>"),
        ("plain #incident text", False, "plain <b>#incident</b> text"),
        ("<https://example.com|docs>", False, '<a href="https://example.com">docs</a>'),
    ],
)
def test_render_text(message, process_markdown, expected):
    assert SlackFormatter(MagicMock()).render_text(message, process_markdown) == expected
