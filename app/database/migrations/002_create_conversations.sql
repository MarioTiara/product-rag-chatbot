CREATE TABLE conversations (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(255),
    created_at VARCHAR(30) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at VARCHAR(30) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE conversation_messages (
    id VARCHAR(36) PRIMARY KEY,
    conversation_id VARCHAR(36) NOT NULL,
    role VARCHAR(30) NOT NULL,
    content TEXT,
    tool_calls_json TEXT,
    tool_call_id VARCHAR(100),
    tool_name VARCHAR(100),
    created_at VARCHAR(30) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_conversations_updated_at
    ON conversations(updated_at);

CREATE INDEX idx_conversation_messages_conversation_id
    ON conversation_messages(conversation_id, created_at);

CREATE INDEX idx_conversation_messages_tool_call_id
    ON conversation_messages(tool_call_id);