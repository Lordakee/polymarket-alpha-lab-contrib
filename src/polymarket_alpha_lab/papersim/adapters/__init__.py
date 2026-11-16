"""M2 data-adapter package: the A0 contract layer only.

Re-exports the shared contract surface (m2-plan-formal.md section 2.1)
for the A1-A4 adapters. Nothing here is exported from
``polymarket_alpha_lab.papersim`` itself; adapters remain opt-in
imports. No transport, database or cache code lives in this package
init - adapters stay pure-contract consumers until their own nodes.
"""

from polymarket_alpha_lab.papersim.adapters.contracts import (
    AdapterResult,
    AdapterStatus,
    BudgetExhaustedError,
    DEFAULT_ALLOW_PUBLIC_FETCH,
    DEFAULT_MAX_RESPONSE_BYTES,
    DEFAULT_MAX_TOTAL_RESPONSE_BYTES,
    FetchBudget,
    FetchEvidence,
    FetchPermissionError,
    FIRST_VERSION_MAX_MARKETS_PER_ROUND,
    FIRST_VERSION_MAX_REQUESTS_PER_ROUND,
    FIRST_VERSION_ROUND_DEADLINE_SECONDS,
    HARD_MAX_RESPONSE_BYTES,
    PAPER_ONLY,
    READONLY,
    REASON_DEADLINE_EXCEEDED,
    REASON_PUBLIC_FETCH_NOT_ALLOWED,
    REASON_REQUESTS_EXHAUSTED,
    REASON_RESPONSE_BYTES_EXHAUSTED,
    REPORT_ONLY,
    require_public_fetch,
    sha256_hexdigest,
)

__all__ = (
    "AdapterResult",
    "AdapterStatus",
    "BudgetExhaustedError",
    "DEFAULT_ALLOW_PUBLIC_FETCH",
    "DEFAULT_MAX_RESPONSE_BYTES",
    "DEFAULT_MAX_TOTAL_RESPONSE_BYTES",
    "FetchBudget",
    "FetchEvidence",
    "FetchPermissionError",
    "FIRST_VERSION_MAX_MARKETS_PER_ROUND",
    "FIRST_VERSION_MAX_REQUESTS_PER_ROUND",
    "FIRST_VERSION_ROUND_DEADLINE_SECONDS",
    "HARD_MAX_RESPONSE_BYTES",
    "PAPER_ONLY",
    "READONLY",
    "REASON_DEADLINE_EXCEEDED",
    "REASON_PUBLIC_FETCH_NOT_ALLOWED",
    "REASON_REQUESTS_EXHAUSTED",
    "REASON_RESPONSE_BYTES_EXHAUSTED",
    "REPORT_ONLY",
    "require_public_fetch",
    "sha256_hexdigest",
)
