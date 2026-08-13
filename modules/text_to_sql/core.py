import sqlite3
import ollama
import pandas as pd
import re
from pathlib import Path
from config.settings import TextToSQLConfig
from utils.logger import setup_logger
from modules.text_to_sql.query_generator import SQLGenerator
from utils.validators import validate_sql_query


class TextToSQLModule:
    """
    Text-to-SQL engine for local SQLite databases.

    Uses a schema-aware SQLGenerator that produces valid, executable SQLite
    (window functions wrapped in CTEs, STRFTIME for dates) and a self-correction
    loop that retries with the actual execution error when a query fails.
    """

    def __init__(self):
        self.logger = setup_logger("TextToSQLCore")
        self.db_path = TextToSQLConfig.SAMPLE_DB_PATH
        self.generator = SQLGenerator(self.db_path)
        self.last_error = None
        self.last_bad_sql = None
        self._initialize_database()

    # ------------------------------------------------------------------ #
    # Database initialization
    # ------------------------------------------------------------------ #
    def _initialize_database(self):
        """Initialize sample database if it doesn't exist"""
        try:
            if not self.db_path.exists():
                self.logger.info("Sample database not found. Creating new database...")
                self._create_sample_db()
                self.logger.info("✓ Sample database created successfully")
            else:
                self.logger.info("Using existing sample database")

            # Ensure history table exists
            self._initialize_history_table()

        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            raise

    def _initialize_history_table(self):
        """Create query history table if it doesn't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT,
                sql_query TEXT,
                is_favorite INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def save_query(self, question: str, sql_query: str, is_favorite: bool = False):
        """Save a query to history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO query_history (question, sql_query, is_favorite) VALUES (?, ?, ?)",
            (question, sql_query, 1 if is_favorite else 0)
        )
        conn.commit()
        conn.close()

    def get_history(self, favorites_only: bool = False) -> list:
        """Retrieve history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        query = "SELECT * FROM query_history"
        if favorites_only:
            query += " WHERE is_favorite = 1"
        query += " ORDER BY timestamp DESC"

        cursor.execute(query)
        rows = cursor.fetchall()

        history = [
            {'id': r[0], 'question': r[1], 'sql_query': r[2], 'is_favorite': r[3], 'timestamp': r[4]}
            for r in rows
        ]
        conn.close()
        return history

    def _create_sample_db(self):
        """Create sample database with tables and data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                city TEXT,
                country TEXT,
                signup_date TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                price REAL,
                stock INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                total_amount REAL,
                order_date TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            )
        """)

        sample_customers = [
            (1, 'John Doe', 'john@example.com', 'New York', 'USA', '2024-01-15'),
            (2, 'Jane Smith', 'jane@example.com', 'London', 'UK', '2024-02-20'),
            (3, 'Bob Johnson', 'bob@example.com', 'Toronto', 'Canada', '2024-03-10'),
            (4, 'Alice Williams', 'alice@example.com', 'Sydney', 'Australia', '2024-04-05'),
            (5, 'Charlie Brown', 'charlie@example.com', 'Paris', 'France', '2024-05-12')
        ]

        sample_products = [
            (1, 'Laptop', 'Electronics', 999.99, 50),
            (2, 'Wireless Mouse', 'Electronics', 29.99, 200),
            (3, 'Desk Chair', 'Furniture', 199.99, 75),
            (4, 'Monitor', 'Electronics', 299.99, 100),
            (5, 'Keyboard', 'Electronics', 79.99, 150),
            (6, 'Desk Lamp', 'Furniture', 49.99, 80)
        ]

        sample_orders = [
            (1, 1, 1, 2, 1999.98, '2024-04-01'),
            (2, 2, 2, 5, 149.95, '2024-04-05'),
            (3, 1, 3, 1, 199.99, '2024-04-10'),
            (4, 3, 4, 1, 299.99, '2024-04-12'),
            (5, 4, 5, 2, 159.98, '2024-04-15'),
            (6, 2, 1, 1, 999.99, '2024-04-18'),
            (7, 5, 6, 3, 149.97, '2024-04-20'),
            (8, 3, 2, 10, 299.90, '2024-04-22')
        ]

        cursor.executemany('INSERT OR IGNORE INTO customers VALUES (?,?,?,?,?,?)', sample_customers)
        cursor.executemany('INSERT OR IGNORE INTO products VALUES (?,?,?,?,?)', sample_products)
        cursor.executemany('INSERT OR IGNORE INTO orders VALUES (?,?,?,?,?,?)', sample_orders)

        conn.commit()
        conn.close()

        self.logger.info("Sample data inserted into database")

    # ------------------------------------------------------------------ #
    # SQL generation + self-correction
    # ------------------------------------------------------------------ #
    def generate_sql(self, question: str) -> str:
        """Generate SQL with auto-correction using the real execution error."""
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                self.logger.info(f"Generating SQL (Attempt {attempt + 1}) for: {question}")

                if attempt == 0:
                    sql = self.generator.generate(question)
                else:
                    sql = self.generator.correct(question, self.last_bad_sql, self.last_error)

                self.last_bad_sql = sql

                # Validate read-only, then test execution.
                valid, verr = validate_sql_query(sql)
                if not valid:
                    raise Exception(f"SQL Error: {verr}")
                self.execute_query(sql)
                return sql

            except Exception as e:
                self.last_error = str(e)
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_retries:
                    raise Exception(
                        f"Failed to generate valid SQL after {max_retries + 1} attempts. "
                        f"Last error: {e}"
                    )

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #
    def execute_query(self, query: str) -> list:
        """Execute SQL query (read-only SELECT enforced)."""
        valid, verr = validate_sql_query(query)
        if not valid:
            raise Exception(f"SQL Error: {verr}")
        try:
            self.logger.info(f"Executing: {query}")

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(query)
            rows = cursor.fetchall()
            results = [dict(row) for row in rows]

            conn.close()

            self.logger.info(f"Returned {len(results)} rows")
            return results

        except sqlite3.Error as e:
            self.logger.error(f"Query failed: {e}")
            raise Exception(f"SQL Error: {str(e)}")

    def explain_sql(self, sql: str) -> str:
        """Provide a plain-English explanation of a SQL query"""
        prompt = f"Explain this SQL query in plain English for a non-technical user:\n\n{sql}\n\nExplanation:"
        response = ollama.generate(
            model=TextToSQLConfig.OLLAMA_MODEL,
            prompt=prompt,
            options={'temperature': 0.3}
        )
        return response['response'].strip()

    def refine_sql(self, original_question: str, original_sql: str, feedback: str) -> str:
        """Refine SQL based on user feedback (schema-aware)."""
        try:
            return self.generator.refine(original_question, original_sql, feedback)
        except Exception as e:
            self.logger.error(f"SQL refinement failed: {e}")
            raise

    def _classify_query_type(self, question: str) -> str:
        """Shim for test suite compatibility."""
        return self.generator._classify_query_type(question)

    def _clean_sql_response(self, response: str) -> str:
        """Shim for test suite compatibility."""
        return self.generator._clean_sql_response(response)

    # ------------------------------------------------------------------ #
    # Schema / data access
    # ------------------------------------------------------------------ #
    def get_schema(self) -> str:
        """Get database schema as formatted text."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = cursor.fetchall()

            schema_lines = ["TABLES:"]

            for table in tables:
                table_name = table[0]
                if table_name.startswith("sqlite_"):
                    continue
                schema_lines.append(f"\n{table_name}:")

                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()

                for col in columns:
                    schema_lines.append(f"  {col[1]} ({col[2]})")

            conn.close()
            return "\n".join(schema_lines)

        except Exception as e:
            raise Exception(f"Schema error: {str(e)}")

    def import_file(self, file_path: str, table_name: str = None) -> dict:
        """Import CSV/Excel file"""
        try:
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.csv':
                df = pd.read_csv(file_path)
            elif file_ext in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            else:
                raise ValueError(f"Unsupported: {file_ext}")
            
            if df.empty:
                raise ValueError("The file appears to be empty or has no data columns.")

            if not table_name:
                table_name = self._sanitize_table_name(Path(file_path).stem)
            
            df = self._clean_dataframe(df)
            self._create_table_from_dataframe(df, table_name)
            
            return {
                'success': True,
                'table_name': table_name,
                'rows': len(df),
                'columns': len(df.columns),
                'column_names': list(df.columns)
            }
            
        except Exception as e:
            raise Exception(f"Import failed: {str(e)}")

    def _sanitize_table_name(self, name: str) -> str:
        name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        name = re.sub(r'^[0-9]+', '', name)
        return f"imported_{name.lower() or 'table'}"

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.dropna(how='all')
        df.columns = [self._sanitize_column_name(col) for col in df.columns]

        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].fillna('')
            else:
                df[col] = df[col].fillna(0)

        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()

        return df

    def _sanitize_column_name(self, name: str) -> str:
        name = re.sub(r'[^a-zA-Z0-9_]', '_', str(name).strip())
        return name.strip('_').lower() or 'column'

    def _create_table_from_dataframe(self, df: pd.DataFrame, table_name: str):
        conn = sqlite3.connect(self.db_path)
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        conn.close()

    def list_imported_tables(self) -> list:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'imported_%'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return tables
        except:
            return []

    def delete_table(self, table_name: str) -> bool:
        try:
            if not table_name.startswith('imported_'):
                return False
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.commit()
            conn.close()
            return True
        except:
            return False

    def get_table_info(self, table_name: str) -> dict:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()

            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]

            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            sample_rows = cursor.fetchall()

            conn.close()

            return {
                'table_name': table_name,
                'columns': [col[1] for col in columns],
                'row_count': row_count,
                'sample_data': sample_rows
            }
        except:
            return None
