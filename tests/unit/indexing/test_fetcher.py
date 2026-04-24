"""Unit tests for the document fetcher."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kyma_knowledge_mcp.indexing.fetcher import (
    DocumentsFetcher,
    DocumentsSource,
    Scroller,
    SourceType,
    get_documents_sources,
)


def test_get_documents_sources_valid_json(tmp_path: Path) -> None:
    sources_file = tmp_path / "sources.json"
    sources_file.write_text(json.dumps([
        {"name": "kyma", "source_type": "Github", "url": "https://github.com/kyma-project/kyma"},
    ]))
    result = get_documents_sources(str(sources_file))
    assert len(result) == 1
    assert result[0].name == "kyma"
    assert result[0].source_type == SourceType.GITHUB


def test_get_documents_sources_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        get_documents_sources("/nonexistent/path.json")


def test_scroller_copies_md_files(tmp_path: Path) -> None:
    src = tmp_path / "repo"
    src.mkdir()
    (src / "doc.md").write_text("# Hello")
    (src / "ignore.txt").write_text("ignored")

    out = tmp_path / "output"
    source = DocumentsSource(
        name="kyma", source_type=SourceType.GITHUB, url="https://github.com/x/y"
    )
    Scroller(str(src), str(out), source).scroll()

    assert (out / "doc.md").exists()
    assert not (out / "ignore.txt").exists()


def test_scroller_respects_exclude_files(tmp_path: Path) -> None:
    src = tmp_path / "repo"
    src.mkdir()
    (src / "keep.md").write_text("keep")
    (src / "skip.md").write_text("skip")

    out = tmp_path / "output"
    source = DocumentsSource(
        name="kyma",
        source_type=SourceType.GITHUB,
        url="https://github.com/x/y",
        exclude_files=["skip.md"],
    )
    Scroller(str(src), str(out), source).scroll()

    assert (out / "keep.md").exists()
    assert not (out / "skip.md").exists()


def test_scroller_respects_include_files(tmp_path: Path) -> None:
    src = tmp_path / "repo"
    src.mkdir()
    (src / "included.md").write_text("yes")
    (src / "excluded.md").write_text("no")

    out = tmp_path / "output"
    source = DocumentsSource(
        name="kyma",
        source_type=SourceType.GITHUB,
        url="https://github.com/x/y",
        include_files=["included.md"],
    )
    Scroller(str(src), str(out), source).scroll()

    assert (out / "included.md").exists()
    assert not (out / "excluded.md").exists()


def test_fetcher_run_calls_fetch_for_each_source(tmp_path: Path) -> None:
    sources_file = tmp_path / "sources.json"
    sources_file.write_text(json.dumps([
        {"name": "a", "source_type": "Github", "url": "https://github.com/org/a"},
        {"name": "b", "source_type": "Github", "url": "https://github.com/org/b"},
    ]))

    with patch("kyma_knowledge_mcp.indexing.fetcher._clone_repo") as mock_clone, \
         patch("kyma_knowledge_mcp.indexing.fetcher.Scroller") as mock_scroller_cls:
        fake_repo = tmp_path / "fake_repo"
        fake_repo.mkdir()
        mock_clone.return_value = str(fake_repo)
        mock_scroller_cls.return_value.scroll = MagicMock()

        DocumentsFetcher(
            source_file=str(sources_file),
            output_dir=str(tmp_path / "data"),
            tmp_dir=str(tmp_path / "tmp"),
        ).run()

    assert mock_clone.call_count == 2
    assert mock_scroller_cls.return_value.scroll.call_count == 2
