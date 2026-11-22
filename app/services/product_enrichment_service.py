from __future__ import annotations

import json
import logging
import time
from typing import Any


from app.agents.ai.ai_client import AIClient
from app.database.repositories.product_enrichment_repository import ProductEnrichmentRepository
from app.database.repositories.product_repository import ProductRepository
from app.models.product_enrichment import ProductEnrichment, ProductEnrichmentOutput


logger = logging.getLogger(__name__)


class ProductEnrichmentService:
    PROMPT_VERSION = "1.0"

    def __init__(
        self,
        product_repository: ProductRepository,
        enrichment_repository: ProductEnrichmentRepository,
        ai_client:AIClient ,
        max_retries: int = 1,
        retry_delay: float = 2.0,
    ) -> None:
        self.product_repository = product_repository
        self.enrichment_repository = enrichment_repository
        self.ai_client = ai_client
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def enrich_product(
        self,
        product_code: str,
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> ProductEnrichment | ProductEnrichmentOutput | None:
        product = self.product_repository.get_by_code(product_code)

        if not product:
            logger.warning("Product not found: %s", product_code)
            return None

        existing = self.enrichment_repository.get_by_product_code(
            product_code
        )

        if existing and not force:
            logger.info(
                "Product already enriched, skipping: %s",
                product_code,
            )
            return existing

        product_data = self._serialize_product(product)

        enrichment_output = self._generate_enrichment(product_data)

        if not enrichment_output:
            return None

        if dry_run:
            logger.info(
                "Dry run: generated enrichment for %s",
                product_code,
            )
            return enrichment_output

        enrichment = ProductEnrichment(
            product_code=product_code,
            description=enrichment_output.description,
            use_cases=enrichment_output.use_cases,
            target_users=enrichment_output.target_users,
            key_features=enrichment_output.key_features,
            limitations=enrichment_output.limitations,
            normalized_attributes={
                item.name: item.value
                for item in enrichment_output.normalized_attributes
            },
            status="completed",
            model_name=self.ai_client.model,
            prompt_version=self.PROMPT_VERSION,
        )

        self.enrichment_repository.upsert(enrichment)

        logger.info("Product enrichment completed: %s", product_code)

        return enrichment

    def enrich_products(
        self,
        product_codes: list[str] | None = None,
        *,
        batch_size: int = 20,
        force: bool = False,
        dry_run: bool = False,
        delay_seconds: float = 1.0,
    ) -> dict[str, Any]:
        if product_codes is None:
            products = self.product_repository.get_all()
            product_codes = [
                product.product_code for product in products
            ]

        results = {
            "total": len(product_codes),
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "details": [],
        }

        for index, product_code in enumerate(product_codes, start=1):
            logger.info(
                "[%s/%s] Processing product: %s",
                index,
                len(product_codes),
                product_code,
            )

            try:
                existing = (
                    self.enrichment_repository.get_by_product_code(
                        product_code
                    )
                )

                if existing and not force:
                    results["skipped"] += 1
                    results["details"].append({
                        "product_code": product_code,
                        "status": "skipped",
                    })
                    continue

                result = self.enrich_product(
                    product_code,
                    force=force,
                    dry_run=dry_run,
                )

                if result is None:
                    results["failed"] += 1
                    status = "failed"
                else:
                    results["success"] += 1
                    status = "success"

                results["details"].append({
                    "product_code": product_code,
                    "status": status,
                })

            except Exception:
                logger.exception(
                    "Failed to enrich product: %s",
                    product_code,
                )

                results["failed"] += 1
                results["details"].append({
                    "product_code": product_code,
                    "status": "failed",
                })

            if (
                index < len(product_codes)
                and index % batch_size == 0
            ):
                logger.info("Batch completed. Waiting before next batch.")
                time.sleep(delay_seconds)

        logger.info("Product enrichment summary: %s", results)

        return results

    def _generate_enrichment(
        self,
        product_data: dict[str, Any],
    ) -> ProductEnrichmentOutput | None:
        prompt = self._build_prompt(product_data)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert product information analyst. "
                    "Generate accurate and useful product information "
                    "based only on the provided product data."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]

        for attempt in range(1, self.max_retries + 1):
            try:
                result = self.ai_client.create_structured_completion(
                    messages=messages,
                    response_format=ProductEnrichmentOutput,
                )

                if result is None:
                    raise ValueError("AI returned an empty response.")

                return result

            except Exception:
                logger.exception(
                    "Enrichment generation failed. Attempt %s/%s",
                    attempt,
                    self.max_retries,
                )

                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)

        return None


    def _build_prompt(
        self,
        product_data: dict[str, Any],
    ) -> str:
        return f"""
            You are an expert laptop product analyst and technical sales advisor.

            Your task is to analyze the laptop specifications and generate
            accurate product enrichment for an e-commerce product catalog.

            PRODUCT DATA:
            {json.dumps(product_data, indent=2, ensure_ascii=False, default=str)}

            ## ANALYSIS GUIDELINES

            ### 1. Product Description
            - Write a clear and informative product description.
            - Explain its main capabilities based on the actual specifications.
            - Avoid generic marketing statements.
            - Do not claim performance that cannot be supported by the specifications.

            ### 2. Use Cases

            Identify suitable laptop workloads from the following categories:

            A. Programming
            - Light programming:
            Basic coding, web development, Python scripting,
            VS Code, and lightweight development tools.
            - Moderate programming:
            Full-stack development, multiple IDEs, local databases,
            and moderate multitasking.
            - Heavy programming:
            Android Studio, Docker containers, virtual machines,
            large projects, and resource-intensive development environments.

            B. Office and Productivity
            - Document processing, spreadsheets, presentations,
            browsing, video conferencing, and multitasking.

            C. Data Analysis
            - Excel, SQL, Python data analysis, Jupyter Notebook,
            and moderate data processing.
            - Distinguish CPU-based workloads from GPU-intensive workloads.

            D. Design and Creative Work
            - Graphic design, photo editing, UI/UX design,
            and digital illustration.

            E. Video Editing
            - Basic 1080p video editing.
            - Advanced 1080p and 4K video editing.
            - Consider CPU, RAM, GPU, VRAM, and storage limitations.

            F. Gaming
            - Casual gaming.
            - Competitive esports gaming.
            - Modern AAA gaming.
            - Consider GPU model, VRAM, CPU, RAM, and display capabilities.

            G. Streaming
            - Basic streaming.
            - Streaming while gaming.
            - Consider CPU/GPU encoding capabilities, RAM, and multitasking.

            For each recommended use case:
            - Specify the workload level: light, moderate, or heavy.
            - Explain briefly why the laptop is suitable.
            - Reference relevant specifications as evidence.
            - Do not recommend workloads beyond the laptop's capabilities.
            - If specifications are insufficient to assess a category,
            do not make unsupported recommendations.

            ### 3. Target Users

            Identify specific user profiles who would benefit from this laptop.

            Examples:
            - Students and university students.
            - Office workers and business users.
            - Beginner programmers.
            - Web developers.
            - Software engineers working with heavy development environments.
            - Data analysts.
            - Graphic designers.
            - Video editors.
            - Casual gamers.
            - Competitive gamers.
            - AAA gamers.
            - Content creators and streamers.

            For each target user:
            - Describe their typical workload.
            - Explain why this laptop fits their needs.
            - Distinguish between beginner, intermediate, and professional workloads
            where relevant.
            - Do not assume that a laptop is suitable for every user in a category.

            ### 4. Key Features
            - Extract important features from the provided specifications.
            - Highlight meaningful advantages such as RAM capacity,
            SSD storage, processor, GPU, display, and connectivity.
            - Do not invent features.

            ### 5. Factuality Rules
            - Use only information supported by PRODUCT DATA.
            - Never invent specifications, benchmarks, certifications,
            or hardware capabilities.
            - Do not assume GPU performance based only on the presence of a GPU.
            - Do not assume RAM or storage is upgradeable unless stated.
            - When information is missing, acknowledge the limitation.
            - Avoid repeating the same information across fields.

            ### 6. Output Quality
            - Use natural, customer-friendly language.
            - Be specific rather than generic.
            - Prioritize practical purchasing guidance.
            - Return concise but informative results.
            """


    @staticmethod
    def _serialize_product(product: Any) -> dict[str, Any]:
        if hasattr(product, "model_dump"):
            return product.model_dump(mode="json")

        if hasattr(product, "__table__"):
            return {
                column.name: getattr(product, column.name)
                for column in product.__table__.columns
            }

        if isinstance(product, dict):
            return product

        raise TypeError(
            f"Unsupported product type: {type(product).__name__}"
        )