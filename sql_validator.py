import re

# Configuration

MAX_SQL_LENGTH = 4000  # characters

# Keywords that signal DML / DDL 
FORBIDDEN_LEADING = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "CREATE", "TRUNCATE", "REPLACE", "MERGE",
}

# Keywords that are dangerous 
FORBIDDEN_ANYWHERE = {
    "EXEC", "EXECUTE", "GRANT", "REVOKE", "SHUTDOWN",
    "ATTACH", "DETACH",
}

# Dangerous prefix patterns (SQLServer stored procs, extended procs)
FORBIDDEN_PREFIXES = ["xp_", "sp_"]

# SQLite internal tables that should never be queried
FORBIDDEN_TABLES = {
    "sqlite_master", "sqlite_schema", "sqlite_sequence",
    "sqlite_stat1", "sqlite_stat2", "sqlite_stat3", "sqlite_stat4",
    "sqlite_temp_master",
}


class ValidationError(ValueError):
    """Raised when a generated SQL query fails security validation."""


def _normalize(sql: str) -> str:
    """Collapse whitespace and upper-case for keyword matching."""
    return re.sub(r"\s+", " ", sql.strip()).upper()


def validate_sql(sql: str) -> str:
    """
    Validate `sql` against all security rules.

    Returns the original (un-modified) sql string on success.
    Raises ValidationError with a human-readable message on failure.
    """
    if not sql or not sql.strip():
        raise ValidationError("No SQL query was generated. Please rephrase your question.")

    if len(sql) > MAX_SQL_LENGTH:
        raise ValidationError(
            f"Generated SQL is too long ({len(sql)} chars). "
            "Please ask a more specific question."
        )

    norm = _normalize(sql)

    # Rule 1: Must start with SELECT 
    first_token = norm.split()[0] if norm.split() else ""
    if first_token not in ("SELECT", "WITH"):
        # WITH … SELECT is a valid CTE — allow it
        # Everything else is rejected
        if first_token in FORBIDDEN_LEADING:
            raise ValidationError(
                f"Security error: '{first_token}' statements are not permitted. "
                "Only SELECT queries are allowed."
            )
        raise ValidationError(
            f"Unexpected statement type '{first_token}'. "
            "Only SELECT queries are allowed."
        )

    # Rule 2: No dangerous keywords anywhere in the query 
    # Tokenise to avoid false positives like "EXECUTOR" matching "EXEC"
    tokens = set(re.findall(r"\b[A-Z_]+\b", norm))
    bad = tokens & FORBIDDEN_ANYWHERE
    if bad:
        raise ValidationError(
            f"Security error: forbidden keyword(s) detected: {', '.join(sorted(bad))}."
        )

    # Rule 3: No dangerous prefix patterns (xp_, sp_) 
    for prefix in FORBIDDEN_PREFIXES:
        if prefix.upper() in norm:
            raise ValidationError(
                f"Security error: queries referencing '{prefix}*' procedures "
                "are not permitted."
            )

    # Rule 4: No system table access
    for table in FORBIDDEN_TABLES:
        # Compare against the uppercased norm so case-insensitive detection works
        if re.search(r"\b" + re.escape(table.upper()) + r"\b", norm):
            raise ValidationError(
                f"Security error: access to system table '{table}' is not allowed."
            )

    # Rule 5: No stacked statements (semicolon injection)
    trimmed = sql.strip().rstrip(";")
    if ";" in trimmed:
        raise ValidationError(
            "Security error: multiple statements detected. "
            "Only a single SELECT query is permitted per request."
        )

    return sql  # passes all checks
