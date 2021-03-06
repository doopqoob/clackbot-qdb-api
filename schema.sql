CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS discord_user(
    id numeric not null primary key,
    handle text not null,
    discriminator smallint not null
);

CREATE TABLE IF NOT EXISTS quote_metadata(
    id uuid not null primary key default gen_random_uuid(),
    said_by numeric not null REFERENCES discord_user(id),
    added_by numeric not null REFERENCES discord_user(id),
    added_at timestamp with time zone not null default now(),
    visible boolean not null default true
);

CREATE TABLE IF NOT EXISTS quote_content(
    id uuid not null REFERENCES quote_metadata(id) ON DELETE CASCADE,
    line_number smallint not null,
    line text not null
);

CREATE TABLE IF NOT EXISTS quote_vote(
    id uuid not null primary key default gen_random_uuid(),
    quote_id uuid not null REFERENCES quote_metadata(id) ON DELETE CASCADE,
    vote smallint NOT NULL,
    voter numeric not null REFERENCES discord_user(id),
    CONSTRAINT vote_record UNIQUE (quote_id,voter)
);

CREATE TABLE IF NOT EXISTS quote_message(
    id numeric not null primary key,
    quote_id uuid not null references quote_metadata(id) ON DELETE CASCADE
);