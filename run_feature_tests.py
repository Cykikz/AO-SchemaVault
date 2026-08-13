"""
Full-feature test harness for SchemaVaultLocal.
Covers: DB init, schema, query classification, SQL generation (all templates),
execution, response cleaning, file import lifecycle, GUI shell, SQL tab, Settings tab.
Writes report to logs/feature_test_report.md
"""
import sys
import os
import json
import time
import traceback
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))

from modules.text_to_sql.core import TextToSQLModule
from utils.logger import setup_logger

RESULTS = []  # (feature, status, detail)
SECTION = [""]

def section(title):
    SECTION[0] = title
    print(f"\n{'='*60}\n{title}\n{'='*60}")

def check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    RESULTS.append((SECTION[0], name, status, detail))
    print(f"  [{status}] {name}" + (f"  -> {detail}" if detail and not ok else ""))
    return ok

def expect_raises(fn, exc_type, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return False
    except exc_type:
        return True
    except Exception:
        return False

logger = setup_logger("FeatureTests")
module = TextToSQLModule()

# ============================================================
section("1. Database Initialization")
# ============================================================
db = module.db_path
check("demo.db exists", db.exists(), str(db))
try:
    import sqlite3
    con = sqlite3.connect(str(db))
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    con.close()
    expected = {"customers", "products", "orders", "imported_gold_price_forecasting_dataset"}
    check("All 4 seed tables present", set(tables) == expected, str(tables))
except Exception as e:
    check("All 4 seed tables present", False, str(e))

# ============================================================
section("2. Schema Viewer (get_schema)")
# ============================================================
try:
    schema = module.get_schema()
    ok = all(t in schema for t in ["customers", "products", "orders", "imported_gold_price_forecasting_dataset"]) \
         and "order_date" in schema and "ma_7" in schema and "customer_id" in schema
    check("Schema contains all tables & key columns", ok)
    check("Schema non-empty", len(schema) > 50, f"{len(schema)} chars")
except Exception as e:
    check("Schema contains all tables & key columns", False, str(e))

# ============================================================
section("3. Query Classification (_classify_query_type)")
# ============================================================
classify_cases = [
    ("Show dates where ma_7 crossed above ma_30 with rsi below 70", "CROSSOVER_ABOVE"),
    ("Show dates where ma_7 crossed below ma_30", "CROSSOVER_BELOW"),
    ("Find bullish divergence between price and macd", "DIVERGENCE_BULLISH"),
    ("Find bearish divergence between price and rsi", "DIVERGENCE_BEARISH"),
    ("Show days when price was rising and rsi was falling and volume increasing", "MULTI_CONDITION"),
    ("Show combined signals of ma crossover and rsi", "MULTI_CONDITION"),
    ("Calculate monthly total sales for 2024", "TIME_SERIES_MONTHLY"),
    ("Show months where sales are increasing", "TREND_UP"),
    ("Show months where sales are decreasing", "TREND_DOWN"),
    ("Show all customers", "GENERAL"),
    ("golden cross on the gold price table", "CROSSOVER_ABOVE"),
    ("death cross on the gold price table", "CROSSOVER_BELOW"),
    ("Show me total sales by customer", "GENERAL"),
]
for q, expected in classify_cases:
    got = module._classify_query_type(q)
    check(f"classify: {q[:45]}...", got == expected, f"expected {expected}, got {got}")

# ============================================================
section("4. SQL Generation (all template types, via Ollama)")
# ============================================================
gen_cases = [
    ("CROSSOVER_ABOVE", "Show the date and ma_7 for dates where ma_7 crossed above ma_30 in the gold price table, but only if rsi was below 70"),
    ("CROSSOVER_BELOW", "Show dates where ma_7 crossed below ma_30 in the gold price table"),
    ("DIVERGENCE_BULLISH", "Find bullish divergence in the gold price table where price makes lower lows but rsi makes higher lows"),
    ("DIVERGENCE_BEARISH", "Find bearish divergence in the gold price table where price makes higher highs but rsi makes lower highs"),
    ("MULTI_CONDITION", "Show dates in the gold price table where ma_7 is above ma_30 and rsi is below 30 and volume is above 1000"),
    ("TIME_SERIES_MONTHLY", "Calculate the monthly total sales from the orders table for 2024"),
    ("TREND_UP", "Show months where total sales are increasing month over month"),
    ("TREND_DOWN", "Show months where the gold price daily return is decreasing"),
    ("GENERAL", "Show all customers and their cities"),
]
for label, q in gen_cases:
    try:
        t0 = time.time()
        sql = module.generate_sql(q)
        dt = round(time.time() - t0, 1)
        clean = sql.strip().startswith("SELECT") and "```" not in sql
        check(f"generate_sql [{label}]", clean and len(sql) > 10, f"{dt}s; {sql[:90]!r}")
    except Exception as e:
        check(f"generate_sql [{label}]", False, str(e)[:200])

# ============================================================
section("5. Query Execution (execute_query)")
# ============================================================
try:
    rows = module.execute_query("SELECT COUNT(*) AS n FROM customers")
    check("Valid SELECT executes", rows and rows[0]["n"] == 5, str(rows))
except Exception as e:
    check("Valid SELECT executes", False, str(e))

try:
    rows = module.execute_query("SELECT name, price FROM products WHERE price < 100 ORDER BY price")
    # Products under $100: Wireless Mouse (29.99), Keyboard (79.99), Desk Lamp (49.99) -> 3
    check("Filtered query returns rows", len(rows) == 3, str(len(rows)))
except Exception as e:
    check("Filtered query returns rows", False, str(e))

try:
    rows = module.execute_query("SELECT * FROM missing_table")
    check("Invalid table raises error", False, "no error raised")
except Exception as e:
    check("Invalid table raises error", True, str(e)[:80])

try:
    rows = module.execute_query("SELECT bad_column FROM customers")
    check("Invalid column raises error", False, "no error raised")
except Exception as e:
    check("Invalid column raises error", True, str(e)[:80])

# ============================================================
section("6. Response Cleaning (_clean_sql_response)")
# ============================================================
clean_cases = [
    ("```sql\nSELECT 1\n```", "SELECT 1"),
    ("```\nSELECT 2\n```", "SELECT 2"),
    ("SQL: SELECT 3", "SELECT 3"),
    ("Answer: SELECT 4", "SELECT 4"),
    ("SELECT 5;", "SELECT 5"),
    ("SELECT 6\n\nThis query does something useful.", "SELECT 6"),
]
for raw, expected in clean_cases:
    got = module._clean_sql_response(raw)
    check(f"clean: {raw[:30]!r}", got.strip() == expected, f"got {got!r}")

# ============================================================
section("7. File Import (CSV / Excel / errors)")
# ============================================================
fixtures = Path(tempfile.gettempdir()) / "opencode" / "fixtures"

try:
    r = module.import_file(str(fixtures / "My Sales Data.csv"))
    ok = r["success"] and r["table_name"] == "imported_my_sales_data" and r["rows"] == 3 \
         and r["column_names"] == ["customer_name", "total_amount", "order_date", "qty"]
    check("CSV import + header sanitization", ok, json.dumps(r))
except Exception as e:
    check("CSV import + header sanitization", False, str(e)[:200])

try:
    rows = module.execute_query("SELECT customer_name, total_amount FROM imported_my_sales_data ORDER BY total_amount DESC")
    check("Query imported CSV table", rows and rows[0]["customer_name"] == "Bob", str(rows)[:120])
except Exception as e:
    check("Query imported CSV table", False, str(e)[:200])

try:
    r = module.import_file(str(fixtures / "Products Export.xlsx"))
    ok = r["success"] and r["table_name"] == "imported_products_export" and r["rows"] == 3 \
         and r["column_names"] == ["product_id", "product_name", "price_usd"]
    check("Excel (.xlsx) import + sanitization", ok, json.dumps(r))
except Exception as e:
    check("Excel (.xlsx) import + sanitization", False, str(e)[:200])

try:
    r = module.import_file(str(fixtures / "notes.txt"))
    check("Unsupported extension rejected", False, f"no error, got {r}")
except Exception as e:
    check("Unsupported extension rejected", True, str(e)[:80])

try:
    r = module.import_file(str(fixtures / "does_not_exist.csv"))
    check("Missing file raises error", False, f"no error, got {r}")
except Exception as e:
    check("Missing file raises error", True, str(e)[:80])

try:
    r = module.import_file(str(fixtures / "empty_data.csv"))
    check("Empty CSV import handled", r.get("success", False) is True, json.dumps(r)[:150])
except Exception as e:
    check("Empty CSV import handled", False, str(e)[:150])

# ============================================================
section("8. Imported Table Lifecycle (list / info / delete)")
# ============================================================
try:
    tables = module.list_imported_tables()
    check("list_imported_tables shows imported tables", "imported_my_sales_data" in tables and "imported_products_export" in tables, str(tables))
except Exception as e:
    check("list_imported_tables shows imported tables", False, str(e))

try:
    info = module.get_table_info("imported_my_sales_data")
    ok = info and info["row_count"] == 3 and "total_amount" in info["columns"] and len(info["sample_data"]) == 3
    check("get_table_info returns details + sample data", bool(ok), json.dumps({k: v for k, v in (info or {}).items() if k != 'sample_data'}) if info else "None")
except Exception as e:
    check("get_table_info returns details + sample data", False, str(e))

try:
    ok1 = module.delete_table("imported_my_sales_data")
    ok2 = module.delete_table("imported_products_export")
    ok3 = module.delete_table("customers") is False  # cannot delete core tables
    check("delete_table removes imported tables only", ok1 and ok2 and ok3, f"csv={ok1} xlsx={ok2} core={ok3}")
except Exception as e:
    check("delete_table removes imported tables only", False, str(e))

try:
    tables = module.list_imported_tables()
    check("Imported tables removed after delete", "imported_my_sales_data" not in tables and "imported_products_export" not in tables, str(tables))
except Exception as e:
    check("Imported tables removed after delete", False, str(e))

# ============================================================
section("9. Utilities (logger)")
# ============================================================
try:
    log_dir = ROOT / "logs"
    files = list(log_dir.glob("app_*.log"))
    check("Logger writes daily log file", len(files) >= 1, str([f.name for f in files]))
except Exception as e:
    check("Logger writes daily log file", False, str(e))

# ============================================================
section("10. GUI (app shell + tabs)")
# ============================================================
gui_ok = True
try:
    import customtkinter as ctk
    from gui.theme import AppTheme
    ctk.set_appearance_mode("dark")

    class FakeApp:
        """Minimal stand-in for MainApplication for tab-level tests."""
        def __init__(self):
            self.status_messages = []
            self.page_status_label = None
        def update_status(self, msg, color=None):
            self.status_messages.append((msg, color))
        def after(self, ms, cb):
            cb()
            return None
        def logger(self):
            return None

    root = ctk.CTk()
    root.withdraw()

    # --- SQL tab ---
    from gui.tabs.sql_tab import TextToSQLTab
    app = FakeApp()
    container = ctk.CTkFrame(root)
    tab = TextToSQLTab(container, app)
    check("SQL tab module initializes", tab.module is not None)
    check("SQL tab generate button enabled", str(tab.generate_btn.cget("state")) == "normal")
    check("SQL tab execute button starts disabled", str(tab.execute_btn.cget("state")) == "disabled")

    # sql area default hint (check BEFORE clear_all, which wipes it)
    check("SQL area seeded with hint", "Generated SQL will appear here" in tab.sql_text.get("1.0", "end"))

    # show_schema (async via parent.after -> flush event loop)
    tab.show_schema()
    root.update()
    content = tab.results_text.get("1.0", "end")
    check("View Schema populates results area", "customers" in content and "order_date" in content)

    # clear_all
    tab.input_text.insert(0, "some question")
    tab.clear_all()
    check("Clear resets inputs + disables buttons",
          tab.input_text.get() == "" and str(tab.execute_btn.cget("state")) == "disabled")

    # format_results
    formatted = tab._format_results([{"name": "Alice", "total": 100}, {"name": "Bob", "total": 200}])
    check("Results formatted as table", "Alice" in formatted and "Total rows: 2" in formatted, formatted.replace("\n", " | "))

    # --- Settings tab ---
    from gui.tabs.settings_tab import SettingsTab
    old_cwd = os.getcwd()
    tmp = tempfile.mkdtemp(prefix="svl_settings_")
    os.chdir(tmp)
    try:
        settings_tab = SettingsTab(container, app)
        settings_tab.local_llm_var.set(True)
        settings_tab.model_var.set("sqlcoder:7b")
        settings_tab.provider_var.set("anthropic")
        settings_tab.api_key_field.delete(0, "end")
        settings_tab.api_key_field.insert(0, "sk-test-123")
        settings_tab.save_settings()
        saved = json.loads(Path(tmp, "user_settings.json").read_text(encoding="utf-8"))
        check("Settings save/load roundtrip",
              saved["use_local_llm"] is True and saved["local_model"] == "sqlcoder:7b"
              and saved["api_provider"] == "anthropic" and saved["api_key"] == "sk-test-123",
              json.dumps(saved))
        os.remove(Path(tmp, "user_settings.json"))
    finally:
        os.chdir(old_cwd)

    # --- Main app shell ---
    from gui.app import MainApplication
    real_app = MainApplication()
    real_app.update()
    check("Main app window created", real_app.title() == "SchemaVaultLocal", real_app.title())
    check("Status bar label present", hasattr(real_app, "status_label"))
    real_app.change_theme("Light")
    real_app.update()
    check("Theme switch works (Light)", ctk.get_appearance_mode() == "Light", ctk.get_appearance_mode())
    real_app.update_status("Testing status", "success")
    real_app.update()
    check("update_status updates labels", real_app.status_label.cget("text") == "Testing status")
    real_app.change_theme("Dark")
    real_app.update()
    real_app.destroy()

    root.destroy()
except Exception as e:
    gui_ok = False
    check("GUI tests", False, f"{type(e).__name__}: {str(e)[:300]}")
    traceback.print_exc()

if gui_ok:
    check("GUI tests all ran", True)

# ============================================================
section("SUMMARY")
# ============================================================
total = len(RESULTS)
passed = sum(1 for r in RESULTS if r[2] == "PASS")
failed = sum(1 for r in RESULTS if r[2] == "FAIL")
print(f"\nTotal: {total} | Passed: {passed} | Failed: {failed}")

# Write report
report = [f"# SchemaVaultLocal Feature Test Report", ""]
report.append(f"- **Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
report.append(f"- **Total checks:** {total} | **Passed:** {passed} | **Failed:** {failed}")
report.append("")
report.append("## Results by Section")
report.append("")
cur = None
for sec, name, status, detail in RESULTS:
    if sec != cur:
        cur = sec
        report.append(f"### {sec}")
        report.append("")
    report.append(f"- [{'x' if status == 'PASS' else ' '}] **{name}** — {status}")
    if detail and status == "FAIL":
        report.append(f"  - _Detail:_ {detail}")
report.append("")

report_path = ROOT / "logs" / "feature_test_report.md"
report_path.write_text("\n".join(report), encoding="utf-8")
print(f"\nReport saved to {report_path}")
