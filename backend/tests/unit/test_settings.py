from kms.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.ai_provider == "fake"
    assert s.worker_threads == 4
    assert s.units_per_path == 100
    assert s.page_size == 20
    assert s.embedding_dims == 1024


def test_plain_postgres_urls_get_the_psycopg_driver():
    s = Settings(_env_file=None, database_url="postgresql://u:p@h:5432/d")
    assert s.database_url == "postgresql+psycopg://u:p@h:5432/d"
    s = Settings(_env_file=None, database_url="postgres://u:p@h:5432/d")
    assert s.database_url == "postgresql+psycopg://u:p@h:5432/d"
