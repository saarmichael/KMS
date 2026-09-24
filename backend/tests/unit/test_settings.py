from kms.config import Settings


def test_defaults_match_design():
    s = Settings(_env_file=None)
    assert s.ai_provider == "fake"
    assert s.worker_threads == 4
    assert s.units_per_path == 100
    assert s.page_size == 20
    assert s.embedding_dims == 1024
