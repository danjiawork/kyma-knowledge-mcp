"""CLI entry point for building the local Kyma docs index."""

import argparse
import logging
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kyma-knowledge-mcp-build-index",
        description=(
            "Fetch Kyma documentation from GitHub and build a local ChromaDB index "
            "for use with kyma-knowledge-mcp."
        ),
    )
    parser.add_argument(
        "--sources",
        default="./docs_sources.json",
        help="Path to docs_sources.json (default: ./docs_sources.json)",
    )
    parser.add_argument(
        "--data-dir",
        default="./data",
        help="Directory to store fetched markdown files (default: ./data)",
    )
    parser.add_argument(
        "--tmp-dir",
        default="./tmp",
        help="Temporary directory for git clones (default: ./tmp)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path.home() / ".kyma-knowledge-mcp" / "index"),
        help="ChromaDB output directory (default: ~/.kyma-knowledge-mcp/index)",
    )
    parser.add_argument(
        "--embed-model",
        default="BAAI/bge-small-en-v1.5",
        help="fastembed model name (default: BAAI/bge-small-en-v1.5)",
    )
    parser.add_argument(
        "--package",
        default="",
        help="If set, package the index into a .tar.gz archive at this path",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip the fetch step and use an existing --data-dir",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    logger = logging.getLogger(__name__)

    # Import here so logging is configured first
    from kyma_knowledge_mcp.indexing.fetcher import DocumentsFetcher
    from kyma_knowledge_mcp.indexing.indexer import FastEmbedEmbeddings, LocalFileIndexer

    if not args.skip_fetch:
        if not Path(args.sources).exists():
            logger.error(f"Sources file not found: {args.sources}")
            sys.exit(1)
        logger.info("Step 1/2: Fetching documents...")
        DocumentsFetcher(
            source_file=args.sources,
            output_dir=args.data_dir,
            tmp_dir=args.tmp_dir,
        ).run()
    else:
        logger.info("Skipping fetch step.")

    logger.info("Step 2/2: Indexing documents...")
    embedding = FastEmbedEmbeddings(args.embed_model)
    indexer = LocalFileIndexer(
        docs_path=args.data_dir,
        embedding=embedding,
        output_dir=args.output_dir,
    )
    indexer.index()

    if args.package:
        logger.info(f"Packaging index → {args.package}")
        LocalFileIndexer.package(args.output_dir, args.package)

    logger.info("Done.")


if __name__ == "__main__":
    main()
