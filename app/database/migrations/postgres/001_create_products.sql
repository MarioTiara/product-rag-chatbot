CREATE TABLE products (
    id VARCHAR(36) PRIMARY KEY,
    product_code VARCHAR(100) NOT NULL UNIQUE,
    brand VARCHAR(100) NOT NULL,
    model VARCHAR(255),
    name VARCHAR(500) NOT NULL,
    os VARCHAR(100),
    price NUMERIC(12, 2),
    processor_name VARCHAR(255),
    processor_brand VARCHAR(100),
    ram_expandable INTEGER NOT NULL DEFAULT 0,
    ram INTEGER,
    ram_type VARCHAR(100),
    processor_ghz DOUBLE PRECISION,
    display_type VARCHAR(100),
    display_inch DOUBLE PRECISION,
    gpu VARCHAR(255),
    gpu_brand VARCHAR(100),
    ssd_gb INTEGER,
    hdd_gb INTEGER,
    battery_life VARCHAR(100),
    tags TEXT,
    stock INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_products_brand
    ON products(brand);

CREATE INDEX idx_products_name
    ON products(name);

-- Not necessary: product_code already has a UNIQUE constraint,
-- which automatically creates a unique index.