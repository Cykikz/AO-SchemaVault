import re
from typing import Tuple


# Read-only guard: these SQL verbs can modify data or schema and are never
# allowed, even inside a CTE or as a sub-statement.
_FORBIDDEN_VERBS = [
    r"\bDELETE\b", r"\bINSERT\b", r"\bUPDATE\b", r"\bDROP\b",
    r"\bALTER\b", r"\bTRUNCATE\b", r"\bCREATE\b", r"\bREPLACE\b",
    r"\bATTACH\b", r"\bDETACH\b", r"\bVACUUM\b", r"\bREINDEX\b",
]

_ALLOWED_LEADING = re.compile(
    r"^\s*(?:(?:WITH\b)|(?:SELECT\b))", re.IGNORECASE
)


def validate_sql_query(query: str) -> Tuple[bool, str]:
    """
    Validate that a query is read-only and safe to run.

    Returns (is_valid, error_message). A query is valid only if it begins
    with WITH or SELECT and contains no data/schema-modifying verbs.
    """
    if not query or not query.strip():
        return False, "Query is empty"

    if not _ALLOWED_LEADING.match(query):
        return False, "Only SELECT (and WITH ... SELECT) queries are allowed for security reasons"

    for pattern in _FORBIDDEN_VERBS:
        if re.search(pattern, query, re.IGNORECASE):
            return False, f"Forbidden SQL verb detected: {pattern.replace(r'\\b', '')}"

    if re.match(r"^\s*WITH\b", query, re.IGNORECASE) and \
       not re.search(r"\bSELECT\b", query, re.IGNORECASE):
        return False, "WITH clause must resolve to a SELECT statement"

    return True, ""


def sanitize_input(text: str) -> str:
    """Strip surrounding whitespace from a natural language question."""
    return text.strip()
