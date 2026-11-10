CREATE TABLE products (
    id VARCHAR(36) PRIMARY KEY,
    product_code VARCHAR(100) NOT NULL UNIQUE,
    brand VARCHAR(100) NOT NULL,
    model VARCHAR(255),
    name VARCHAR(500) NOT NULL,
    os VARCHAR(100),
    usd_price REAL,
    processor_name VARCHAR(255),
    processor_brand VARCHAR(100),
    ram_expandable INTEGER NOT NULL DEFAULT 0,
    ram INTEGER,
    ram_type VARCHAR(100),
    processor_ghz REAL,
    display_type VARCHAR(100),
    display_inch REAL,
    gpu VARCHAR(255),
    gpu_brand VARCHAR(100),
    ssd_gb INTEGER,
    hdd_gb INTEGER,
    battery_life VARCHAR(100),
    tags TEXT,
    stock INTEGER NOT NULL DEFAULT 0,
    created_at VARCHAR(30) DEFAULT CURRENT_TIMESTAMP,
    updated_at VARCHAR(30) DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_products_brand ON products(brand);
CREATE INDEX idx_products_name ON products(name);
CREATE INDEX idx_products_product_code ON products(product_code);