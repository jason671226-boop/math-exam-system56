from pathlib import Path

# MathAI v0.8.8.3 deployment entrypoint.
# The validated v0.8.8.2 source is kept byte-for-byte as the release core;
# only the displayed release number is advanced for this deployment.
_core = Path(__file__).resolve().with_name("app_release_v0_8_8_3.py")
_source = _core.read_text(encoding="utf-8-sig")
_source = _source.replace(
    'APP_VERSION = "v0.8.8.2"',
    'APP_VERSION = "v0.8.8.3"',
    1,
)
if 'APP_VERSION = "v0.8.8.3"' not in _source:
    raise RuntimeError("MathAI release version marker not found")
exec(compile(_source, str(_core), "exec"), globals(), globals())
