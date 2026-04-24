"""Document fetcher: clones GitHub repos and extracts markdown files."""

import fnmatch
import json
import logging
import os
import shutil
import subprocess
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SourceType(StrEnum):
    GITHUB = "Github"


class DocumentsSource(BaseModel):
    name: str
    source_type: SourceType
    url: str
    include_files: list[str] | None = None
    exclude_files: list[str] | None = None
    filter_file_types: list[str] = ["md"]


def get_documents_sources(path: str) -> list[DocumentsSource]:
    with open(path) as f:
        return [DocumentsSource(**item) for item in json.load(f)]


class Scroller:
    """Walks a cloned repo directory and copies allowed files to output_dir."""

    def __init__(self, dir_path: str, output_dir: str, source: DocumentsSource) -> None:
        self.dir_path = dir_path
        self.output_dir = output_dir
        self.source = source

    def _save_file(self, file_dir: str, file_name: str) -> None:
        source_path = os.path.join(self.dir_path, file_dir, file_name)
        target_dir = os.path.join(self.output_dir, file_dir)
        os.makedirs(target_dir, exist_ok=True)
        shutil.copy(source_path, target_dir)
        logger.debug(f"Saved {source_path} → {target_dir}")

    def _should_exclude(self, file_path: str) -> bool:
        if self.source.exclude_files is None:
            return False
        return any(fnmatch.fnmatch(file_path, p) for p in self.source.exclude_files)

    def _should_include(self, file_path: str) -> bool:
        if self.source.include_files is None:
            return True
        return any(fnmatch.fnmatch(file_path, p) for p in self.source.include_files)

    def scroll(self) -> None:
        for file_dir, _, files in os.walk(self.dir_path):
            relative_dir = file_dir.removeprefix(self.dir_path).lstrip("/")
            for file_name in files:
                file_path = os.path.join(relative_dir, file_name)

                if file_name.rsplit(".", 1)[-1] not in self.source.filter_file_types:
                    continue
                if self._should_exclude(file_path):
                    logger.debug(f"Excluded: {file_path}")
                    continue
                if not self._should_include(file_path):
                    logger.debug(f"Not in include list: {file_path}")
                    continue

                self._save_file(relative_dir, file_name)


def _clone_repo(repo_url: str, clone_dir: str) -> str:
    """Clone a git repository and return the path to the cloned directory."""
    repo_name = repo_url.rstrip("/").split("/")[-1].removesuffix(".git")
    repo_path = os.path.join(clone_dir, repo_name)
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path, ignore_errors=True)
    subprocess.run(["git", "clone", "--depth=1", repo_url, repo_path], check=True)
    return repo_path


class DocumentsFetcher:
    """Fetches markdown documents from sources defined in a JSON file."""

    def __init__(self, source_file: str, output_dir: str, tmp_dir: str) -> None:
        self.output_dir = output_dir
        self.tmp_dir = tmp_dir
        shutil.rmtree(self.output_dir, ignore_errors=True)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        self.sources = get_documents_sources(source_file)
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.tmp_dir).mkdir(parents=True, exist_ok=True)

    def _fetch_source(self, source: DocumentsSource) -> None:
        logger.info(f"Fetching: {source.name}")
        if source.source_type != SourceType.GITHUB:
            raise ValueError(f"Unsupported source_type: {source.source_type}")

        repo_dir = _clone_repo(source.url, self.tmp_dir)
        module_output_dir = os.path.join(self.output_dir, source.name)
        os.makedirs(module_output_dir, exist_ok=True)
        try:
            Scroller(repo_dir, module_output_dir, source).scroll()
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def run(self) -> None:
        for source in self.sources:
            self._fetch_source(source)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        logger.info("All documents fetched successfully.")
