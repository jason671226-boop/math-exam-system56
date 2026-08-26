from pathlib import Path

from scripts import stage7_private_jh_public_corpus as corpus


def test_sources_are_closed_allowlist_and_official():
    assert len(corpus.SOURCES) >= 4
    assert all(corpus._official(row["page"]) and corpus._official(row["url"]) for row in corpus.SOURCES)


def test_local_only_output_paths():
    assert corpus.LOCAL == corpus.ROOT / ".local/stage7_private_jh"
    for path in (corpus.PDF_DIR, corpus.RAW_DIR, corpus.REGISTRY, corpus.CORPUS):
        assert corpus.LOCAL in path.parents or path == corpus.LOCAL


def test_filename_is_standardized():
    names = [corpus._filename(row) for row in corpus.SOURCES]
    assert len(names) == len(set(names))
    assert all(name.endswith("_EXAM_MATH.pdf") for name in names)


def test_fingerprint_is_normalized_and_deterministic():
    assert corpus._fingerprint("  1 + 1  ") == corpus._fingerprint("1 + 1")
    assert corpus._fingerprint("1 + 1") != corpus._fingerprint("1 + 2")


def test_script_has_no_model_or_database_dependency():
    text = Path(corpus.__file__).read_text(encoding="utf-8").lower()
    for forbidden in ("supabase", "gemini_api", "deepseek_api", "service_role"):
        assert forbidden not in text
