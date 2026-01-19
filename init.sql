-- Создание таблиц для хранения данных Telegram аккаунтов

-- Глобальные настройки приложения (ОДИН api_id/api_hash на все аккаунты)
CREATE TABLE IF NOT EXISTS global_app_settings (
    id SERIAL PRIMARY KEY,
    api_id INTEGER UNIQUE NOT NULL,
    api_hash VARCHAR(200) NOT NULL,
    app_name VARCHAR(100) DEFAULT 'Corporate Telegram Manager',
    app_version VARCHAR(20) DEFAULT '1.0',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Прокси-серверы
CREATE TABLE IF NOT EXISTS proxy_servers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    host VARCHAR(200) NOT NULL,
    port INTEGER NOT NULL,
    username VARCHAR(100),
    password VARCHAR(100),
    proxy_type VARCHAR(20) DEFAULT 'socks5',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Основная таблица для хранения аккаунтов
CREATE TABLE IF NOT EXISTS telegram_accounts (
    id SERIAL PRIMARY KEY,
    
    -- Идентификаторы
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    employee_id VARCHAR(50),
    employee_fio VARCHAR(200),
    account_note TEXT,
    
    -- КРИТИЧЕСКИ ВАЖНЫЕ ДАННЫЕ (все зашифрованы)
    encrypted_api_id BYTEA,
    encrypted_api_hash BYTEA,
    encrypted_session BYTEA,
    encrypted_recovery_email BYTEA,
    encrypted_phone_code_hash BYTEA, -- Добавлено для хранения временного кода подтверждения
    
    -- Метаданные сессии
    session_updated_at TIMESTAMP,
    session_hash VARCHAR(64),
    
    -- Состояние аккаунта
    is_2fa_enabled BOOLEAN DEFAULT FALSE,
    last_checked TIMESTAMP,
    account_status VARCHAR(20) DEFAULT 'pending',
    
    -- Новые поля по ТЗ
    last_ping TIMESTAMP,
    activity_status VARCHAR(20) DEFAULT 'active',
    device_params JSONB DEFAULT '{}',
    proxy_id INTEGER REFERENCES proxy_servers(id) ON DELETE SET NULL,
    
    -- Безопасность
    encryption_version INTEGER DEFAULT 1,
    
    -- Аудит
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Очередь задач
CREATE TABLE IF NOT EXISTS task_queue (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    account_id INTEGER REFERENCES telegram_accounts(id) ON DELETE CASCADE,
    account_ids JSONB,
    parameters JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    result JSONB,
    error_message TEXT,
    created_by VARCHAR(100),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для аудита
CREATE TABLE IF NOT EXISTS account_audit_log (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES telegram_accounts(id),
    action_type VARCHAR(50) NOT NULL,
    action_details JSONB,
    performed_by VARCHAR(100),
    ip_address INET,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_telegram_accounts_phone ON telegram_accounts(phone_number);
CREATE INDEX IF NOT EXISTS idx_telegram_accounts_status ON telegram_accounts(account_status);
CREATE INDEX IF NOT EXISTS idx_telegram_accounts_employee ON telegram_accounts(employee_id);
CREATE INDEX IF NOT EXISTS idx_telegram_accounts_last_ping ON telegram_accounts(last_ping);
CREATE INDEX IF NOT EXISTS idx_telegram_accounts_activity_status ON telegram_accounts(activity_status);
CREATE INDEX IF NOT EXISTS idx_telegram_accounts_proxy ON telegram_accounts(proxy_id);
CREATE INDEX IF NOT EXISTS idx_task_queue_status ON task_queue(status);
CREATE INDEX IF NOT EXISTS idx_task_queue_type ON task_queue(task_type);
CREATE INDEX IF NOT EXISTS idx_task_queue_created ON task_queue(created_at);
CREATE INDEX IF NOT EXISTS idx_account_audit_log_account ON account_audit_log(account_id);