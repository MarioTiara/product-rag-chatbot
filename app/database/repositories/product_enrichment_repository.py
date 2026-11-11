
from __future__ import annotations

import json

from app.database.connection import DatabaseConnection
from app.models.product_enrichment import ProductEnrichment


class ProductEnrichmentRepository:
    def __init__(self, db: DatabaseConnection):
        self.db = db

    @staticmethod
    def _to_model(row) -> ProductEnrichment | None:
        if row is None:
            return None

        data = dict(row)

        json_fields = [
            "use_cases",
            "target_users",
            "key_features",
            "limitations",
            "normalized_attributes",
        ]

        for field in json_fields:
            data[field] = json.loads(data[field])

        return ProductEnrichment.model_validate(data)

    @staticmethod
    def _serialize(enrichment: ProductEnrichment) -> dict:
        data = enrichment.model_dump(
            exclude={"id", "created_at", "updated_at"}
        )

        json_fields = [
            "use_cases",
            "target_users",
            "key_features",
            "limitations",
            "normalized_attributes",
        ]

        for field in json_fields:
            data[field] = json.dumps(data[field])

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
                WHERE product_code = ?
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
        placeholders = ", ".join(["?"] * len(data))

        with self.db.connect() as conn:
            cursor = conn.execute(
                f"""
                INSERT INTO product_enrichments ({columns})
                VALUES ({placeholders})
                """,
                tuple(data.values()),
            )

            row = conn.execute(
                """
                SELECT *
                FROM product_enrichments
                WHERE id = ?
                """,
                (cursor.lastrowid,),
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
            f"{column} = ?" for column in data
        )

        with self.db.connect() as conn:
            conn.execute(
                f"""
                UPDATE product_enrichments
                SET {assignments},
                    updated_at = CURRENT_TIMESTAMP
                WHERE product_code = ?
                """,
                (*data.values(), product_code),
            )

            row = conn.execute(
                """
                SELECT *
                FROM product_enrichments
                WHERE product_code = ?
                """,
                (product_code,),
            ).fetchone()

            return self._to_model(row)

    def upsert(
        self,
        enrichment: ProductEnrichment,
    ) -> ProductEnrichment:
        existing = self.get_by_product_code(enrichment.product_code)

        if existing:
            return self.update(
                enrichment.product_code,
                enrichment,
            )

        return self.create(enrichment)

    def delete(self, product_code: str) -> bool:
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM product_enrichments
                WHERE product_code = ?
                """,
                (product_code,),
            )

            return cursor.rowcount > 0
