from __future__ import annotations

import argparse
import logging
import sys

from app.database.connection import DatabaseConnection
from app.database.repositories.product_repository import ProductRepository
from app.database.repositories.product_enrichment_repository import (
    ProductEnrichmentRepository,
)
from app.agents.ai.ai_client_factory import AIClientFactory
from app.services.product_enrichment_service import ProductEnrichmentService
from app.core.configs import config

logger = logging.getLogger(__name__)
settings= config.get_settings()

def build_service() -> ProductEnrichmentService:
    """
    Initialize dependencies and build ProductEnrichmentService.
    """

    # Database initialization
    db = DatabaseConnection()

    product_repository = ProductRepository(db)
    enrichment_repository = ProductEnrichmentRepository(db)
    
    ai_client = AIClientFactory.create()

    return ProductEnrichmentService(
        product_repository=product_repository,
        enrichment_repository=enrichment_repository,
        ai_client=ai_client,
        max_retries=3,
        retry_delay=2.0,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate product enrichment using AI."
    )

    target = parser.add_mutually_exclusive_group(required=True)

    target.add_argument(
        "--all",
        action="store_true",
        help="Enrich all products.",
    )

    target.add_argument(
        "--product-code",
        nargs="+",
        help="Enrich specific product codes.",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate existing enrichments.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate enrichment without saving to database.",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Number of products per batch (default: 20).",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between batches in seconds (default: 1.0).",
    )

    return parser.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    args = parse_args()

    service = build_service()

    results = service.enrich_products(
        product_codes=args.product_code,
        batch_size=args.batch_size,
        force=args.force,
        dry_run=args.dry_run,
        delay_seconds=args.delay,
    )

    print("\n========== ENRICHMENT SUMMARY ==========")
    print(f"Total   : {results['total']}")
    print(f"Success : {results['success']}")
    print(f"Skipped : {results['skipped']}")
    print(f"Failed  : {results['failed']}")
    print("========================================")

    return 1 if results["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())