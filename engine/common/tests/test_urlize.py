import pytest

from common.utils import urlize_with_respect_to_a


def test_urlize_will_not_mutate_text_without_links():
    original = "Text without link"
    expected = original
    assert urlize_with_respect_to_a(original) == expected


def test_urlize_will_not_mutate_text_with_link_in_a():
    original = '<a href="https://amixr.io/">amixr website</a>'
    expected = original
    assert urlize_with_respect_to_a(original) == expected


@pytest.mark.filterwarnings(
    "ignore:The input looks more like a URL than markup. You may want to use an HTTP client like requests to get the "
    "document behind the URL, and feed that document to Beautiful Soup."
)
def test_urlize_will_wrap_link():
    original = "https://amixr.io/"
    expected = '<a href="https://amixr.io/">https://amixr.io/</a>'
    assert urlize_with_respect_to_a(original) == expected


def test_urlize_will_not_wrap_link_inside_a():
    original = '<a href="https://amixr.io/">https://amixr.io/</a>'
    expected = original
    assert urlize_with_respect_to_a(original) == expected


def test_url_matcher_handles_adversarial_punctuation():
    import subprocess
    import sys

    from common.utils import url_re

    subprocess.run(
        [
            sys.executable,
            "-c",
            "import re, sys; p = re.compile(sys.argv[1], re.I); "
            "p.findall('http://' + '!' * 50000); p.findall('a.' * 25000 + '!')",
            url_re.pattern,
        ],
        timeout=2,
        check=True,
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/a_b?x=one&y=two",
        "http://localhost:8080/path",
        "example.com/path",
        "https://example.com/a_(b)",
    ],
)
def test_url_matcher_preserves_links(url):
    from common.utils import url_re

    assert url_re.findall(url) == [url]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("[link](https://example.com/a_b)", ["https://example.com/a_b"]),
        ("(https://example.com/a_(b)).", ["https://example.com/a_(b)"]),
        ("Visit example.com/path!", ["example.com/path"]),
    ],
)
def test_find_urls_leaves_markup_and_punctuation(text, expected):
    from common.utils import find_urls

    assert find_urls(text) == expected
