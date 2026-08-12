import sqlite3
import ollama
import pandas as pd
import re
from pathlib import Path
from config.settings import TextToSQLConfig
from utils.logger import setup_logger


class TextToSQLModule:
    """
    Production-grade SQL Generator with query classification
    Handles expert-level queries by detecting patterns first
    """
    
    def __init__(self):
        self.logger = setup_logger("TextToSQLCore")
        self.db_path = TextToSQLConfig.SAMPLE_DB_PATH
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize sample database if it doesn't exist"""
        try:
            if not self.db_path.exists():
                self.logger.info("Sample database not found. Creating new database...")
                self._create_sample_db()
                self.logger.info("✓ Sample database created successfully")
            else:
                self.logger.info("Using existing sample database")
                
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            raise
    
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
    
    def _classify_query_type(self, question: str) -> str:
        """
        Classify the query type to use correct template
        This prevents AI from generating wrong patterns
        """
        q_lower = question.lower()
        
        # Crossover detection keywords
        crossover_keywords = [
            'cross above', 'crosses above', 'crossed above',
            'cross below', 'crosses below', 'crossed below',
            'golden cross', 'death cross', 'crossover',
            'breaks above', 'breaks below', 'breakthrough'
        ]
        
        # Divergence keywords
        divergence_keywords = [
            'divergence', 'diverge', 'opposite direction',
            'price down.*indicator up', 'price up.*indicator down'
        ]
        
        # Multi-condition keywords
        multi_condition_keywords = [
            'and.*and', 'while.*and', 'when.*and.*and',
            'combined', 'confluence', 'together'
        ]
        
        # Check for crossover
        for keyword in crossover_keywords:
            if keyword in q_lower:
                if 'above' in q_lower or 'golden' in q_lower:
                    return 'CROSSOVER_ABOVE'
                elif 'below' in q_lower or 'death' in q_lower:
                    return 'CROSSOVER_BELOW'
                return 'CROSSOVER_ABOVE'  # Default to above
        
        # Check for divergence
        for keyword in divergence_keywords:
            if keyword in q_lower:
                if 'bullish' in q_lower:
                    return 'DIVERGENCE_BULLISH'
                elif 'bearish' in q_lower:
                    return 'DIVERGENCE_BEARISH'
                return 'DIVERGENCE_BULLISH'  # Default
        
        # Check for multi-condition
        for keyword in multi_condition_keywords:
            if re.search(keyword, q_lower):
                return 'MULTI_CONDITION'
        
        # Time-series patterns
        if any(word in q_lower for word in ['monthly', 'by month', 'per month']):
            return 'TIME_SERIES_MONTHLY'
        
        if any(word in q_lower for word in ['increasing', 'rising', 'growing', 'up from previous']):
            return 'TREND_UP'
        
        if any(word in q_lower for word in ['decreasing', 'falling', 'declining', 'down from previous']):
            return 'TREND_DOWN'
        
        # Default to general query
        return 'GENERAL'
    
    def generate_sql(self, question: str) -> str:
        """
        Generate SQL with query classification for accuracy
        """
        try:
            self.logger.info(f"Generating SQL for: {question}")
            
            # Classify query type
            query_type = self._classify_query_type(question)
            self.logger.info(f"Query classified as: {query_type}")
            
            schema = self.get_schema()
            
            # Use specialized prompt based on query type
            if query_type in ['CROSSOVER_ABOVE', 'CROSSOVER_BELOW']:
                sql_query = self._generate_crossover_query(question, query_type, schema)
            elif query_type in ['DIVERGENCE_BULLISH', 'DIVERGENCE_BEARISH']:
                sql_query = self._generate_divergence_query(question, query_type, schema)
            elif query_type == 'MULTI_CONDITION':
                sql_query = self._generate_multi_condition_query(question, schema)
            else:
                sql_query = self._generate_general_query(question, schema)
            
            return sql_query
            
        except Exception as e:
            self.logger.error(f"SQL generation failed: {e}")
            raise Exception(f"Failed to generate SQL: {str(e)}")
    
    def _generate_crossover_query(self, question: str, query_type: str, schema: str) -> str:
        """Generate crossover-specific query with strict template"""
        
        direction = "above" if "ABOVE" in query_type else "below"
        
        prompt = f"""Generate a SQL query for detecting when one value crosses {direction} another.

SCHEMA:
{schema}

MANDATORY CROSSOVER TEMPLATE - DO NOT DEVIATE:

For ABOVE crossover:
SELECT t1.date, t1.fast_column, t1.slow_column
FROM table_name t1
LEFT JOIN table_name t2 ON DATE(t1.date) = DATE(t2.date, '+1 day')
WHERE t1.fast_column > t1.slow_column
  AND COALESCE(t2.fast_column, 0) <= COALESCE(t2.slow_column, 999999)
ORDER BY t1.date

For BELOW crossover:
SELECT t1.date, t1.fast_column, t1.slow_column
FROM table_name t1
LEFT JOIN table_name t2 ON DATE(t1.date) = DATE(t2.date, '+1 day')
WHERE t1.fast_column < t1.slow_column
  AND COALESCE(t2.fast_column, 999999) >= COALESCE(t2.slow_column, 0)
ORDER BY t1.date

QUESTION: {question}

INSTRUCTIONS:
1. Identify which columns are being compared (e.g., ma_7 and ma_30)
2. Determine which is "fast" (smaller period) and "slow" (larger period)
3. Use the EXACT template above
4. Replace table_name, fast_column, slow_column with actual names
5. Output ONLY the SQL query

SQL:"""
        
        response = ollama.generate(
            model=TextToSQLConfig.OLLAMA_MODEL,
            prompt=prompt,
            options={
                'temperature': 0.05,  # Very low for strict template following
                'num_predict': 300,
                'stop': ['\n\n']
            }
        )
        
        return self._clean_sql_response(response['response'])
    
    def _generate_divergence_query(self, question: str, query_type: str, schema: str) -> str:
        """Generate divergence-specific query"""
        
        divergence_type = "bullish" if "BULLISH" in query_type else "bearish"
        
        prompt = f"""Generate a SQL query for detecting {divergence_type} divergence.

SCHEMA:
{schema}

MANDATORY DIVERGENCE TEMPLATE:

For BULLISH divergence (price down, indicator up):
SELECT t1.date, t1.close, t1.indicator
FROM table_name t1
JOIN table_name t2 ON DATE(t1.date) = DATE(t2.date, '+1 day')
WHERE t1.close < t2.close
  AND t1.indicator > t2.indicator
ORDER BY t1.date

For BEARISH divergence (price up, indicator down):
SELECT t1.date, t1.close, t1.indicator
FROM table_name t1
JOIN table_name t2 ON DATE(t1.date) = DATE(t2.date, '+1 day')
WHERE t1.close > t2.close
  AND t1.indicator < t2.indicator
ORDER BY t1.date

QUESTION: {question}

Replace table_name and indicator with actual column names.
Output ONLY the SQL query.

SQL:"""
        
        response = ollama.generate(
            model=TextToSQLConfig.OLLAMA_MODEL,
            prompt=prompt,
            options={'temperature': 0.05, 'num_predict': 300}
        )
        
        return self._clean_sql_response(response['response'])
    
    def _generate_multi_condition_query(self, question: str, schema: str) -> str:
        """Generate multi-condition query"""
        
        prompt = f"""Generate SQL for query with multiple conditions.

SCHEMA:
{schema}

TEMPLATE:
SELECT t1.date, t1.col1, t1.col2, t1.col3
FROM table_name t1
LEFT JOIN table_name t2 ON DATE(t1.date) = DATE(t2.date, '+1 day')
WHERE condition1
  AND condition2
  AND condition3
ORDER BY t1.date

QUESTION: {question}

Output ONLY the SQL query.

SQL:"""
        
        response = ollama.generate(
            model=TextToSQLConfig.OLLAMA_MODEL,
            prompt=prompt,
            options={'temperature': 0.1, 'num_predict': 400}
        )
        
        return self._clean_sql_response(response['response'])
    
    def _generate_general_query(self, question: str, schema: str) -> str:
        """Generate general SQL query"""
        
        prompt = f"""Convert to SQL query.

SCHEMA:
{schema}

QUESTION: {question}

RULES:
- For time grouping: GROUP BY strftime('%Y-%m', date)
- For aggregations: SUM/AVG/COUNT/MAX/MIN
- For filters: WHERE column > value
- For trends: Use self-join with DATE(t1.date) = DATE(t2.date, '+1 day')
- Output ONLY SQL query

SQL:"""
        
        response = ollama.generate(
            model=TextToSQLConfig.OLLAMA_MODEL,
            prompt=prompt,
            options={'temperature': 0.1, 'num_predict': 400}
        )
        
        return self._clean_sql_response(response['response'])
    
    def _clean_sql_response(self, response: str) -> str:
        """Clean AI response to extract pure SQL"""
        sql = response.strip()
        
        # Remove markdown
        if '```sql' in sql:
            sql = sql.split('```sql')[1].split('```')[0].strip()
        elif '```' in sql:
            sql = sql.split('```')[1].split('```')[0].strip()
        
        # Remove common prefixes
        prefixes = ['SQL:', 'Query:', 'A:', 'Answer:']
        for prefix in prefixes:
            if sql.upper().startswith(prefix.upper()):
                sql = sql[len(prefix):].strip()
        
        # Remove trailing semicolon
        sql = sql.rstrip(';').strip()
        
        # Remove explanations after query
        if '\n\n' in sql:
            sql = sql.split('\n\n')[0].strip()
        
        return sql
    
    def execute_query(self, query: str) -> list:
        """Execute SQL query"""
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
    
    def get_schema(self) -> str:
        """Get database schema"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = cursor.fetchall()
            
            schema_lines = ["TABLES:"]
            
            for table in tables:
                table_name = table[0]
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