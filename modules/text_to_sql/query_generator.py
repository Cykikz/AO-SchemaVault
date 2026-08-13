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
            f"not arithmetic). If the error is 'no such column: X' and X IS in the "
            f"schema, the problem is usually that a CTE/subquery did not SELECT column "
            f"X even though the outer query references it - add X to the CTE's SELECT "
            f"list (every column used in the outer SELECT or WHERE must be carried "
            f"through the CTE). Output ONLY the corrected "
            f"SQL, no explanation, no markdown."
        )
        self.logger.info("Requesting SQL self-correction from model")
        return self._call_llm(prompt)

    def refine(self, question: str, sql: str, feedback: str) -> str:
        """
        Ask the model to adjust a previously generated SQL statement based on
        user feedback. Returns the refined SQL (unverified). Raises if the LLM
        call fails.
        """
        prompt = (
            f"A SQLite query was generated for the question below, and the user "
            f"provided feedback on what should change.\n\n"
            f"QUESTION: {question}\n\n"
            f"CURRENT SQL:\n{sql}\n\n"
            f"USER FEEDBACK: {feedback}\n\n"
            f"SCHEMA (use only these tables/columns):\n{self._describe_schema()}\n\n"
            f"RULES:\n"
            f"1. Output ONLY the corrected SQL query. No explanations, no markdown "
            f"fences, no trailing semicolon.\n"
            f"2. Use the real column names from the schema above. If a needed column "
            f"does not exist, do not invent it.\n"
            f"3. Use SQLite syntax. For dates use STRFTIME('%Y-%m', col) for month "
            f"grouping and STRFTIME('%Y-%m-%d', col) for day comparisons. NEVER use "
            f"EXTRACT(), date_part(), or INTERVAL arithmetic. The date column is a "
            f"TEXT ISO string (YYYY-MM-DD), so step between rows with LAG()/LEAD() "
            f"ordered by the date, never date arithmetic.\n"
            f"4. Only use SELECT statements (read-only). Never generate "
            f"INSERT/UPDATE/DELETE/DROP/ALTER.\n"
            f"5. Window functions (LAG/LEAD/OVER) must be wrapped in a subquery/CTE "
            f"and never appear in a WHERE clause.\n"
            f"6. Always finish with a complete, executable final SELECT.\n\n"
            f"CORRECTED SQL:"
        )
        self.logger.info("Requesting SQL refinement from model")
        return self._call_llm(prompt)

    # ------------------------------------------------------------------ #
    # Classification
    # ------------------------------------------------------------------ #
    def _classify_query_type(self, question: str) -> str:
        """Return a bucket name that tunes the prompt."""
        q = " ".join(question.lower().split())

        # 1. Set-logic ALL/ANY priority (e.g. "higher than every product in X")
        if re.search(r'\b(price|prices)\b.*\b(higher|lower|more|less|greater|cheaper|expensive)\b.*\b(every|all|any|each)\b', q) or \
           re.search(r'\b(higher|lower|more|less|greater|cheaper)\s+than\s+(every|all|any|each)\b', q):
            return "set_logic"

        # 2. Multi-condition priority (multiple ANDed clauses, or explicit intent words)
        if re.search(r'\b(and.*and|combined|confluence|together)\b', q):
             return "multi_condition"

        # 2. Forward window
        if re.search(r'\b(subsequent|following|next \d+ (trading )?days|over the next|after the (signal|cross))\b', q):
            return "forward_window"

        # 3. Crossover
        if re.search(r'\b(cross(es|ed|ing)?\s*(above|below|over|under))\b', q) or \
           re.search(r'\b(golden|death)\s*cross\b', q):
            return "cross_below" if re.search(r'\b(crosses? below|death cross)\b', q) else "cross_above"

        # 4. Streak
        if re.search(r'\b(consecutive|streak|in a row|in succession|run of|days in a row)\b', q):
            return "streak"

        # 5. Running
        if re.search(r'\b(running|rolling|cumulative|drawdown|peak|all-time high)\b', q):
            return "running"

        # 6. Categorize
        if re.search(r'\b(categoriz\w*|regime\w*|bucket\w*|classif\w*|segments?)\b|\bgroup by\s+(category|bucket)\b', q):
            return "categorize"

        # 7. Time Series
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
                "NOT above it the previous trading day.\n"
                "CRITICAL column-carry rule: every column you reference in the OUTER query "
                "or in the WHERE clause must ALSO appear in the CTE's SELECT list. If you "
                "filter on 'fast' and 'slow' (e.g. ma_7 and ma_30), both must be selected "
                "inside the WITH block. Never reference a base-table column in the outer "
                "SELECT/WHERE unless the CTE selected it."
            ),
            "cross_below": (
                "This is a crossover-below query. IMPORTANT: window functions (LAG/LEAD) cannot "
                "appear in a WHERE clause in SQLite. Compute LAG(fast) and LAG(slow) in a "
                "subquery/CTE ordered by date, then in the outer query filter where fast < slow "
                "AND the previous fast >= previous slow.\n"
                "CRITICAL column-carry rule: every column referenced in the outer query or "
                "WHERE clause must ALSO be selected inside the CTE/subquery. Never reference a "
                "base-table column in the outer SELECT/WHERE unless the CTE selected it."
            ),
            "multi_condition": (
                "This query combines multiple conditions or asks for rows that satisfy more "
                "than one requirement.\n"
                "If it asks for rows meeting several conditions at once, join the needed tables "
                "and use WHERE with AND (e.g. WHERE col1 > x AND col2 < y).\n"
                "If it asks for things that appear in BOTH/ALL of several groups (e.g. "
                "customers who bought BOTH 'Electronics' AND 'Furniture'), use GROUP BY on the "
                "entity key and HAVING COUNT(DISTINCT group_col) = <number of groups> - never a "
                "plain IN (...) list, which returns rows matching ANY group.\n"
                "If it asks for things present in one set but NOT another (e.g. never ordered), "
                "use LEFT JOIN ... WHERE other.key IS NULL or NOT EXISTS.\n"
                "Use SQLite syntax and real column names from the schema."
            ),
            "set_logic": (
                "This is a set-comparison query against a whole group, e.g. products whose "
                "price is higher than EVERY product in a category, or cheaper than ALL of them.\n"
                "The correct SQLite pattern compares against the group's extreme with a "
                "NOT EXISTS / ALL pattern, or counts how many group members the candidate "
                "beats:\n"
                "  -- higher than EVERY item in 'Electronics':\n"
                "  SELECT p1.name FROM products p1\n"
                "  WHERE p1.category != 'Electronics'\n"
                "    AND NOT EXISTS (\n"
                "      SELECT 1 FROM products p2\n"
                "      WHERE p2.category = 'Electronics' AND p2.price >= p1.price\n"
                "    )\n"
                "Equivalent alternative: compare p1.price to the MAX price of the group\n"
                "  SELECT name FROM products\n"
                "  WHERE price > (SELECT MAX(price) FROM products WHERE category = 'Electronics')\n"
                "Use real column names from the schema. Never use a self-join with a bare "
                "category filter for this - it cannot express 'beats every member'."
            ),
            "streak": (
                "This asks for consecutive-day sequences (e.g. N days in a row meeting a "
                "condition). The date column is a TEXT ISO string (YYYY-MM-DD), so you cannot "
                "do date arithmetic like date - INTERVAL 1 DAY. Detect the start of each streak "
                "with a separate LAG() step, then use a gap-and-island SUM OVER. Use EXACTLY "
                "this working SQLite shape (adapt table and column names; here 'cond' is the "
                "boolean condition, e.g. daily_return > 0):\n"
                "  WITH base AS (\n"
                "    SELECT date, cond_col,\n"
                "           LAG(cond_col) OVER (ORDER BY date) AS prev\n"
                "    FROM tbl\n"
                "  ),\n"
                "  flagged AS (\n"
                "    SELECT date, cond_col,\n"
                "           CASE WHEN prev IS NULL OR NOT prev THEN 1 ELSE 0 END AS new_group\n"
                "    FROM base\n"
                "  ),\n"
                "  grps AS (\n"
                "    SELECT date, cond_col,\n"
                "           SUM(new_group) OVER (ORDER BY date) AS grp\n"
                "    FROM flagged\n"
                "  ),\n"
                "  agg AS (\n"
                "    SELECT grp, MIN(date) AS start_date, MAX(date) AS end_date,\n"
                "           COUNT(*) AS n, SUM(daily_return) AS cumulative_return\n"
                "    FROM grps WHERE cond_col\n"
                "    GROUP BY grp\n"
                "  )\n"
                "  SELECT start_date, end_date, cumulative_return\n"
                "  FROM agg WHERE n >= 3\n"
                "  ORDER BY start_date\n"
                "CRITICAL: NEVER put LAG()/LEAD() inside another window function (e.g. "
                "SUM(CASE WHEN LAG(x)...) OVER ...). Compute LAG/LEAD in its own CTE first, "
                "then reference the column in a later CTE."
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
                "This asks for an average (or other aggregate) over the NEXT N trading days "
                "AFTER a signal event (e.g. a crossover). First identify the signal rows "
                "(e.g. a crossover using LAG in a CTE). Then, for each signal row, average the "
                "value over the following N rows by computing LEAD(value, k) OVER (ORDER BY "
                "date) for k = 1..N in a CTE, and averaging those LEAD columns. The date column "
                "is a TEXT ISO string so use LAG/LEAD ordered by date (never INTERVAL math).\n"
                "Example shape (crossover detection as the 'signal'):\n"
                "  WITH base AS (\n"
                "    SELECT date, close, macd, macd_signal\n"
                "    FROM tbl\n"
                "  ),\n"
                "  sig AS (\n"
                "    SELECT date, close,\n"
                "           LAG(macd) OVER (ORDER BY date) AS pm,\n"
                "           LAG(macd_signal) OVER (ORDER BY date) AS ps,\n"
                "           macd, macd_signal\n"
                "    FROM base\n"
                "  ),\n"
                "  crossed AS (\n"
                "    SELECT date, close FROM sig\n"
                "    WHERE macd > macd_signal AND COALESCE(pm,0) <= COALESCE(ps,0)\n"
                "  ),\n"
                "  future AS (\n"
                "    SELECT date, LEAD(close,1) OVER (ORDER BY date) AS c1,\n"
                "           LEAD(close,2) OVER (ORDER BY date) AS c2,\n"
                "           LEAD(close,3) OVER (ORDER BY date) AS c3,\n"
                "           LEAD(close,4) OVER (ORDER BY date) AS c4,\n"
                "           LEAD(close,5) OVER (ORDER BY date) AS c5\n"
                "    FROM tbl\n"
                "  )\n"
                "  SELECT x.date AS signal_date,\n"
                "         (x.close + f.c1 + f.c2 + f.c3 + f.c4 + f.c5)/6.0 AS avg_next_5\n"
                "  FROM crossed x JOIN future f ON x.date = f.date\n"
                "CRITICAL: every column you reference in a later CTE's WHERE must be selected "
                "in that CTE's SELECT list (e.g. if you filter s.macd, macd must be in the "
                "sig CTE's SELECT). Use the real column names and never put window functions "
                "in a WHERE clause."
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
    def _validate_columns(self, sql: str):
        """Check if columns in SQL exist in schema."""
        schema_detail = self._describe_schema()
        # Extract columns (very basic regex)
        cols = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', sql))
        
        # Check against schema columns
        all_schema_cols = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', schema_detail))
        
        # Filter out common SQL keywords
        keywords = {'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'JOIN', 'ON', 'AS', 'WITH', 'GROUP', 'BY', 'ORDER', 'LIMIT', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'LAG', 'LEAD', 'OVER', 'PARTITION', 'SUM', 'AVG', 'COUNT', 'MAX', 'MIN', 'STRFTIME', 'COALESCE'}
        
        missing = cols - all_schema_cols - keywords
        if missing:
             self.logger.warning(f"Potentially invalid columns detected: {missing}")

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
            sql = self._clean_sql_response(response.get('response', ''))
            self._validate_columns(sql)
            return sql
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
