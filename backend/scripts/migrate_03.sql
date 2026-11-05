-- CogniFlow AI — improvements_plan_03, Etapa 2
--
-- Replaces the legacy vector schema (768-dimension embeddings, no page tracking)
-- with the new one: `documents` table, chunks linked by `document_id`, page and
-- section columns, 1024-dimension embeddings (bge-m3) and an HNSW index.
--
-- Vectors from the previous embedding model are not comparable with bge-m3, so the
-- old data cannot be converted: it is dropped and the PDFs must be ingested again.
--
-- Usage (from the repository root):
--   docker compose exec -T postgres psql -U cogniflow -d cogniflow_db < backend/scripts/migrate_03.sql
-- Then restart the backend: the new tables and index are created on startup.

BEGIN;
DROP TABLE IF EXISTS mind_maps;
DROP TABLE IF EXISTS document_chunks;
DROP TABLE IF EXISTS documents;
ALTER EXTENSION vector UPDATE;
COMMIT;
