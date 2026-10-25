from pathlib import Path
import re

from app.core.config import SENSITIVE_FIELD_NAMES, Settings

SECRET_LEAK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
)


def audit_environment_isolation(
    project_root: Path,
    settings: Settings,
) -> list[str]:
    """Verify environment variable isolation and check against institutional key leakage."""
    violations: list[str] = []

    gitignore_path = project_root / ".gitignore"
    if not gitignore_path.exists():
        violations.append("Missing .gitignore file at project root.")
    else:
        gitignore_content = gitignore_path.read_text(encoding="utf-8")
        if ".env" not in gitignore_content:
            violations.append(".gitignore does not exclude .env files.")

    env_example_path = project_root / "backend" / ".env.example"
    if env_example_path.exists():
        example_text = env_example_path.read_text(encoding="utf-8")
        for pattern in SECRET_LEAK_PATTERNS:
            if pattern.search(example_text):
                violations.append(
                    "Real API key pattern found inside backend/.env.example."
                )

    settings_repr = repr(settings)
    for field_name in SENSITIVE_FIELD_NAMES:
        secret_val = getattr(settings, field_name, None)
        if secret_val and str(secret_val) in settings_repr:
            violations.append(
                f"Sensitive field '{field_name}' is exposed in repr(Settings)."
            )

    safe_summary = settings.get_safe_config_summary()
    for field_name in SENSITIVE_FIELD_NAMES:
        if (
            getattr(settings, field_name, None) is not None
            and safe_summary.get(field_name) != "***REDACTED***"
        ):
            violations.append(
                f"Sensitive field '{field_name}' was not redacted in get_safe_config_summary()."
            )

    return violations

