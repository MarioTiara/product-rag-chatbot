CREATE TABLE product_enrichments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    product_code TEXT NOT NULL UNIQUE,

    description TEXT NOT NULL,

    use_cases TEXT NOT NULL,
    target_users TEXT NOT NULL,
    key_features TEXT NOT NULL,
    limitations TEXT NOT NULL,

    normalized_attributes TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'pending',

    model_name TEXT,
    prompt_version TEXT,
    source_hash TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (product_code)
        REFERENCES products(product_code)
        ON DELETE CASCADE
);