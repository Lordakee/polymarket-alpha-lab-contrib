"""Environment boundary for the paper-sim ledger DB persistence."""

from __future__ import annotations

from dataclasses import dataclass
from os import environ
from typing import Mapping

from polymarket_alpha_lab.supabase_local_dsn import validate_local_postgres_dsn


PAPERSIM_PG_DSN_ENV_VAR = "PAPERSIM_PG_DSN"
PAPERSIM_PG_PASSWORD_FILE_ENV_VAR = "PAPERSIM_PG_PASSWORD_FILE"
DEFAULT_PAPERSIM_PG_DSN = "postgresql://paper_sim@127.0.0.1:55432/paper_sim"


@dataclass(frozen=True)
class SupabasePapersimConfig:
    """Validated paper-sim ledger DSN environment boundary.

    ``dsn`` is ``None`` when ``PAPERSIM_PG_DSN`` is unset, empty or
    whitespace-only; the documented example default is applied by
    ``resolved_dsn``. Any other override is whitespace-stripped once and
    must then pass the single audited ``validate_local_postgres_dsn``:
    a malformed or non-local override raises a configuration error and
    never silently falls back to the default (codex-review F4). The SCRAM
    password is deliberately not part of this config: it is supplied
    out-of-band via ``PAPERSIM_PG_PASSWORD_FILE`` (an environment
    variable holding the path of a one-line password file) and is never
    read, printed or committed here. This is paper evidence storage
    configuration only, never an execution authorization.
    """

    dsn: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "dsn", _normalize_optional_dsn(self.dsn))
        if self.dsn is not None:
            validate_local_postgres_dsn(
                self.dsn,
                env_var_name=PAPERSIM_PG_DSN_ENV_VAR,
            )

    def resolved_dsn(self) -> str:
        """Return the configured DSN or the documented example default.

        The returned value always passed through the single audited
        ``validate_local_postgres_dsn`` before it reaches a caller.
        """
        value = DEFAULT_PAPERSIM_PG_DSN if self.dsn is None else self.dsn
        validate_local_postgres_dsn(value, env_var_name=PAPERSIM_PG_DSN_ENV_VAR)
        return value

    def __repr__(self) -> str:
        dsn = "<redacted>" if self.dsn is not None else "None"
        return f"{type(self).__name__}(dsn={dsn})"


def from_papersim_db_env(
    env: Mapping[str, str] | None = None,
) -> SupabasePapersimConfig:
    """Read ``PAPERSIM_PG_DSN`` from ``env`` (default: process environment)."""
    source = environ if env is None else env
    return SupabasePapersimConfig(dsn=source.get(PAPERSIM_PG_DSN_ENV_VAR))


def _normalize_optional_dsn(value: object) -> str | None:
    """Normalize an explicit override; never silently drop a nonempty one.

    ``None`` (unset) and values that are empty after stripping mean "use
    the documented default". Every other value is stripped once and
    returned for validation: ``__post_init__`` / ``resolved_dsn`` run the
    single audited ``validate_local_postgres_dsn`` on it, so a padded or
    unpadded malformed/hosted override raises a clear configuration
    error instead of selecting the loopback default (codex-review F4).
    """
    if value is None:
        return None
    if type(value) is not str:
        raise ValueError(f"{PAPERSIM_PG_DSN_ENV_VAR} must be a string")
    stripped = value.strip()
    if not stripped:
        return None
    return stripped


__all__ = (
    "DEFAULT_PAPERSIM_PG_DSN",
    "PAPERSIM_PG_DSN_ENV_VAR",
    "PAPERSIM_PG_PASSWORD_FILE_ENV_VAR",
    "SupabasePapersimConfig",
    "from_papersim_db_env",
)
