
from __future__ import annotations

import json

from psycopg.types.json import Jsonb

from app.database.connection import DatabaseConnection
from app.models.product_enrichment import ProductEnrichment


class ProductEnrichmentRepository:
    JSON_FIELDS = [
        "use_cases",
        "target_users",
        "key_features",
        "limitations",
        "normalized_attributes",
    ]

    def __init__(self, db: DatabaseConnection):
        self.db = db

    @staticmethod
    def _to_model(row) -> ProductEnrichment | None:
        if row is None:
            return None

        # Psycopg with dict_row returns JSONB columns
        # as native Python objects.
        return ProductEnrichment.model_validate(row)

    @classmethod
    def _serialize(cls, enrichment: ProductEnrichment) -> dict:
        data = enrichment.model_dump(
            exclude={"id", "created_at", "updated_at"}
        )

        for field in cls.JSON_FIELDS:
            data[field] = Jsonb(data[field])

        return data

    def get_by_product_code(
        self,
        product_code: str,
    ) -> ProductEnrichment | None:
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM product_enrichments
                WHERE product_code = %s
                """,
                (product_code,),
            ).fetchone()

            return self._to_model(row)

    def create(
        self,
        enrichment: ProductEnrichment,
    ) -> ProductEnrichment:
        data = self._serialize(enrichment)

        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))

        with self.db.connect() as conn:
            row = conn.execute(
                f"""
                INSERT INTO product_enrichments ({columns})
                VALUES ({placeholders})
                RETURNING *
                """,
                tuple(data.values()),
            ).fetchone()

            return self._to_model(row)

    def update(
        self,
        product_code: str,
        enrichment: ProductEnrichment,
    ) -> ProductEnrichment | None:
        data = self._serialize(enrichment)

        # Product code is the lookup key and should not be updated.
        data.pop("product_code", None)

        assignments = ", ".join(
            f"{column} = %s" for column in data
        )

        with self.db.connect() as conn:
            row = conn.execute(
                f"""
                UPDATE product_enrichments
                SET {assignments},
                    updated_at = CURRENT_TIMESTAMP
                WHERE product_code = %s
                RETURNING *
                """,
                (*data.values(), product_code),
            ).fetchone()

            return self._to_model(row)

    def upsert(
        self,
        enrichment: ProductEnrichment,
    ) -> ProductEnrichment:
        existing = self.get_by_product_code(enrichment.product_code)

        if existing:
            result = self.update(
                enrichment.product_code,
                enrichment,
            )

            if result is None:
                raise RuntimeError(
                    "Product enrichment disappeared during update."
                )

            return result

        return self.create(enrichment)

    def delete(self, product_code: str) -> bool:
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM product_enrichments
                WHERE product_code = %s
                """,
                (product_code,),
            )

            return cursor.rowcount > 0
