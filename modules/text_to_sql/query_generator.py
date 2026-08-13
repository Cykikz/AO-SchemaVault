import re
import sqlite3
import ollama
from pathlib import Path
from config.settings import TextToSQLConfig
from utils.logger import setup_logger


class SQLGenerator:
    """
    Generates SQL from natural language for SQLite.

    Designed for analytical datasets (e.g. financial time series). It is
    schema-aware: the actual table and column names are injected into every
    prompt so the model references real identifiers instead of inventing them.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.logger = setup_logger("SQLGenerator")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def generate(self, question: str) -> str:
        """Generate a single SQL statement for the question."""
        query_type = self._classify_query_type(question)
        self.logger.info(f"Query classified as: {query_type}")

        schema_detail = self._describe_schema()
        prompt = self._build_prompt(question, schema_detail, query_type)
        sql_query = self._call_llm(prompt)
        self.logger.info(f"Generated SQL:\n{sql_query}")
        return sql_query

    def correct(self, question: str, bad_sql: str, error: str) -> str:
        """
        Ask the model to fix SQL that failed to execute. Returns the corrected
        SQL (unverified). Raises if the LLM call fails.
        """
        prompt = (
            f"The following SQLite query was generated for the question below but "
            f"failed with this error:\nERROR: {error}\n\n"
            f"QUESTION: {question}\n\n"
            f"BAD SQL:\n{bad_sql}\n\n"
            f"SCHEMA (use only these tables/columns):\n{self._describe_schema()}\n\n"
            f"Fix the query so it is valid SQLite. Remember window functions "
            f"(LAG/LEAD/OVER) must live in a subquery/CTE, never in a WHERE clause, "
            f"and use STRFTIME (never EXTRACT, date_part, or INTERVAL date math - the "
            f"date column is a TEXT ISO string, so step between rows with LAG/LEAD, "
            f"not arithmetic). Output ONLY the corrected "
            f"SQL, no explanation, no markdown."
        )
        self.logger.info("Requesting SQL self-correction from model")
        return self._call_llm(prompt)

    # ------------------------------------------------------------------ #
    # Classification
    # ------------------------------------------------------------------ #
    def _classify_query_type(self, question: str) -> str:
        """Return a bucket name that tunes the prompt."""
        q = " ".join(question.lower().split())

        if re.search(r'\b(cross(es|ed|ing)?\s*(above|below|over|under))\b', q) or \
           re.search(r'\b(golden|death)\s*cross\b', q):
            return "cross_below" if re.search(r'\b(crosses? below|death cross)\b', q) else "cross_above"

        if re.search(r'\b(consecutive|streak|in a row|in succession|run of|days in a row)\b', q):
            return "streak"

        if re.search(r'\b(running|rolling|cumulative|drawdown|peak|all-time high)\b', q):
            return "running"

        if re.search(r'\b(categoriz\w*|regime\w*|bucket\w*|classif\w*|segments?)\b|\bgroup by\s+(category|bucket)\b', q):
            return "categorize"

        if re.search(r'\b(subsequent|following|next \d+ (trading )?days|after the (signal|cross))\b', q):
            return "forward_window"

        if re.search(r'\b(monthly|by month|per month|calendar month)\b', q):
            return "time_series"

        return "general"

    # ------------------------------------------------------------------ #
    # Prompt construction
    # ------------------------------------------------------------------ #
    def _describe_schema(self) -> str:
        """Produce a machine-friendly schema listing columns and types."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            tables = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            lines = []
            for (tname,) in tables:
                if tname.startswith("sqlite_"):
                    continue
                cols = cur.execute(f"PRAGMA table_info('{tname}')").fetchall()
                lines.append(f"{tname}({', '.join(f'{c[1]} {c[2]}' for c in cols)})")
            conn.close()
            return "\n".join(lines)
        except Exception:
            return ""

    def _build_prompt(self, question: str, schema_detail: str, query_type: str) -> str:
        guidance = {
            "cross_above": (
                "This is a crossover query (one line/indicator crossing above another).\n"
                "IMPORTANT SQLite constraint: window functions (LAG/LEAD) CANNOT appear in a "
                "WHERE clause. Compute the previous day's values in a subquery or CTE first,\n"
                "then filter in the outer SELECT. Example shape:\n"
                "  WITH p AS (\n"
                "    SELECT date, close, fast, slow,\n"
                "           LAG(fast) OVER (ORDER BY date) AS prev_fast,\n"
                "           LAG(slow) OVER (ORDER BY date) AS prev_slow\n"
                "    FROM tbl\n"
                "  )\n"
                "  SELECT date, close FROM p\n"
                "  WHERE fast > slow AND COALESCE(prev_fast,0) <= COALESCE(prev_slow,0)\n"
                "A 'crossed above' means the fast line is above the slow line TODAY but was "
                "NOT above it the previous trading day."
            ),
            "cross_below": (
                "This is a crossover-below query. IMPORTANT: window functions (LAG/LEAD) cannot "
                "appear in a WHERE clause in SQLite. Compute LAG(fast) and LAG(slow) in a "
                "subquery/CTE ordered by date, then in the outer query filter where fast < slow "
                "AND the previous fast >= previous slow."
            ),
            "streak": (
                "This asks for consecutive-day sequences (e.g. N days in a row meeting a "
                "condition). The date column is a TEXT ISO string (YYYY-MM-DD), so you cannot "
                "do date arithmetic like date - INTERVAL 1 DAY. Use LAG()/LEAD() window "
                "functions over the ordered date to compare consecutive rows. Use window "
                "functions inside a subquery/CTE (they cannot be in WHERE clauses in SQLite). "
                "Use a gap-and-island approach: assign a group id via SUM(flag) OVER (ORDER BY "
                "date), group consecutive days, and return start/end dates and requested "
                "aggregates. Only include streaks meeting the minimum length."
            ),
            "running": (
                "This needs a running/cumulative or drawdown calculation. Use SQLite window "
                "functions inside a subquery/CTE (they cannot be in WHERE clauses): "
                "MAX(col) OVER (ORDER BY date) for running max, MIN() for running min, "
                "SUM() OVER for cumulative sums. For drawdown compute (price - peak)/peak using "
                "a running MAX, then order and LIMIT to the top N rows as requested."
            ),
            "categorize": (
                "This asks to bucket rows into categories. Use a CASE WHEN expression to assign "
                "each row a bucket, then GROUP BY the bucket and compute the requested "
                "aggregates (COUNT, AVG, SUM)."
            ),
            "forward_window": (
                "This asks for the average (or other aggregate) over the subsequent N trading "
                "days AFTER a signal. Detect the signal days first (e.g. a crossover via LAG in "
                "a CTE). Then compute the average of the NEXT N rows for each signal date using "
                "LEAD() over the ordered date, or a self-join on date ranges. Window functions "
                "must live in a subquery/CTE, not a WHERE clause."
            ),
            "time_series": (
                "This asks for a calendar-month grouping. Use strftime('%Y-%m', date_col) as "
                "the grouping key and compute the requested aggregates (SUM, AVG, COUNT)."
            ),
            "general": (
                "Answer with plain SELECT aggregation/grouping as needed. Use real column names "
                "and SQLite syntax. If you use window functions, wrap them in a subquery/CTE "
                "(SQLite forbids them in WHERE clauses)."
            ),
        }[query_type]

        return f"""You are a SQLite expert. Convert the user's question into a single SQL query.

DATABASE SCHEMA (use ONLY these tables and columns):
{schema_detail}

QUESTION:
{question}

QUERY TYPE HINT:
{guidance}

RULES:
1. Output ONLY the SQL query. No explanations, no markdown fences, no trailing semicolon.
2. Use the real column names from the schema above. If a needed column does not exist, do not invent it.
3. Use SQLite syntax. For dates use STRFTIME('%Y-%m', col) for month grouping and
   STRFTIME('%Y-%m-%d', col) for day comparisons. NEVER use EXTRACT(), date_part(),
   or INTERVAL arithmetic (e.g. 'date - INTERVAL 1 DAY'). The date column is stored
   as a TEXT string in ISO format (YYYY-MM-DD), so compare dates as strings with
   STRFTIME('%Y-%m-%d', col). To step between consecutive rows, use LAG()/LEAD()
   window functions ordered by the date, never date arithmetic.
4. Only use SELECT statements (read-only). Never generate INSERT/UPDATE/DELETE/DROP/ALTER.
5. When the question implies 'top N', use ORDER BY ... LIMIT N.
6. Use window functions (LAG/LEAD/ROW_NUMBER/SUM OVER/MAX OVER) when the question needs
   cross-row or chronological comparisons, but always wrap them in a subquery/CTE.
7. Always finish with a complete, executable final SELECT. Do not end with a CTE definition.

SQL:"""

    # ------------------------------------------------------------------ #
    # LLM call + cleanup
    # ------------------------------------------------------------------ #
    def _call_llm(self, prompt: str) -> str:
        try:
            response = ollama.generate(
                model=TextToSQLConfig.OLLAMA_MODEL,
                prompt=prompt,
                options={
                    'temperature': 0.1,
                    'num_predict': 1500,
                },
            )
            return self._clean_sql_response(response.get('response', ''))
        except Exception as e:
            self.logger.error(f"Ollama call failed: {e}")
            raise Exception(
                "Failed to connect to Ollama. Please check that Ollama is "
                "downloaded, running and accessible. https://ollama.com/download"
            )

    def _clean_sql_response(self, response: str) -> str:
        sql = response.strip()

        if '```sql' in sql:
            sql = sql.split('```sql')[1].split('```')[0].strip()
        elif '```' in sql:
            sql = sql.split('```')[1].split('```')[0].strip()

        for prefix in ['SQL:', 'Query:', 'A:', 'Answer:']:
            if sql.upper().startswith(prefix.upper()):
                sql = sql[len(prefix):].strip()

        sql = sql.rstrip(';').strip()

        if '\n\n' in sql:
            sql = sql.split('\n\n')[0].strip()

        if sql.startswith('(') and sql.endswith(')'):
            sql = sql[1:-1].strip()

        return sql
