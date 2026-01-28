-- Database schema bootstrap for Video Converter
-- This script mirrors the SQLAlchemy models in shared/models.py

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS videos (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(512) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'uploaded',
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes aligned with SQLAlchemy definitions
CREATE INDEX IF NOT EXISTS ix_users_id ON users(id);
CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);
CREATE INDEX IF NOT EXISTS ix_videos_id ON videos(id);

-- Helpful status constraint (optional):
-- ALTER TABLE videos ADD CONSTRAINT videos_status_chk CHECK (status IN ('uploaded','processing','completed','error'));
