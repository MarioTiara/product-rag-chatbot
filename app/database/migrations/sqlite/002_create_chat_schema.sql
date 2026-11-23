
PRAGMA foreign_keys = ON;

-- =====================================================
-- 1. USERS
-- Application users and authentication
-- =====================================================

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,

    display_name VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- =====================================================
-- 2. CHANNEL IDENTITIES
-- Link external channel accounts to application users
-- =====================================================

CREATE TABLE IF NOT EXISTS channel_identities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id VARCHAR(36) NOT NULL,

    channel VARCHAR(50) NOT NULL
        CHECK (channel IN ('telegram', 'whatsapp', 'web')),

    channel_user_id VARCHAR(255) NOT NULL,

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_channel_identity
        UNIQUE (channel, channel_user_id)
);

CREATE INDEX IF NOT EXISTS idx_channel_identities_user
    ON channel_identities(user_id);


-- =====================================================
-- 3. CONVERSATIONS
-- Internal conversation sessions
-- =====================================================

CREATE TABLE IF NOT EXISTS conversations (
    id VARCHAR(36) PRIMARY KEY,

    user_id VARCHAR(36),

    title VARCHAR(255),

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_user
    ON conversations(user_id);

CREATE INDEX IF NOT EXISTS idx_conversations_updated_at
    ON conversations(updated_at);


-- =====================================================
-- 4. CHANNEL CONVERSATIONS
-- Map external chat/thread to internal conversation
-- =====================================================

CREATE TABLE IF NOT EXISTS channel_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    conversation_id VARCHAR(36) NOT NULL,

    channel VARCHAR(50) NOT NULL
        CHECK (channel IN ('telegram', 'whatsapp', 'web')),

    channel_chat_id VARCHAR(255) NOT NULL,

    channel_thread_id VARCHAR(255) NOT NULL DEFAULT '',

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_channel_conversation
        UNIQUE (
            channel,
            channel_chat_id,
            channel_thread_id
        )
);

CREATE INDEX IF NOT EXISTS idx_channel_conversations_internal
    ON channel_conversations(conversation_id);

CREATE INDEX IF NOT EXISTS idx_channel_conversations_external
    ON channel_conversations(
        channel,
        channel_chat_id
    );


-- =====================================================
-- 5. CONVERSATION MESSAGES
-- Canonical history for the LLM
-- =====================================================

CREATE TABLE IF NOT EXISTS conversation_messages (
    id VARCHAR(36) PRIMARY KEY,

    conversation_id VARCHAR(36) NOT NULL,

    sequence_number INTEGER NOT NULL,

    role VARCHAR(30) NOT NULL
        CHECK (
            role IN ('system', 'user', 'assistant', 'tool')
        ),

    content TEXT,

    tool_calls_json TEXT,
    tool_call_id VARCHAR(100),
    tool_name VARCHAR(100),

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_conversation_sequence
        UNIQUE (conversation_id, sequence_number)
);

CREATE INDEX IF NOT EXISTS idx_messages_history
    ON conversation_messages(
        conversation_id,
        sequence_number
    );

CREATE INDEX IF NOT EXISTS idx_messages_tool_call_id
    ON conversation_messages(tool_call_id);


-- =====================================================
-- 6. CHANNEL MESSAGES
-- Map internal messages to external channel messages
-- =====================================================

CREATE TABLE IF NOT EXISTS channel_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    internal_message_id VARCHAR(36) NOT NULL,

    channel_conversation_id INTEGER NOT NULL,

    channel_message_id VARCHAR(255) NOT NULL,

    message_type VARCHAR(20) NOT NULL
        CHECK (message_type IN ('user', 'assistant')),

    delivery_status VARCHAR(20) NOT NULL DEFAULT 'received'
        CHECK (
            delivery_status IN (
                'received',
                'pending',
                'sent',
                'failed'
            )
        ),

    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (internal_message_id)
        REFERENCES conversation_messages(id)
        ON DELETE CASCADE,

    FOREIGN KEY (channel_conversation_id)
        REFERENCES channel_conversations(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_channel_external_message
        UNIQUE (
            channel_conversation_id,
            channel_message_id
        )
);

CREATE INDEX IF NOT EXISTS idx_channel_messages_internal
    ON channel_messages(internal_message_id);

CREATE INDEX IF NOT EXISTS idx_channel_messages_conversation
    ON channel_messages(channel_conversation_id);
