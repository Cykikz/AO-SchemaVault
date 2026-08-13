import sys
import os
import json
import time
from pathlib import Path

# Add the current directory to sys.path to import modules
sys.path.append(str(Path(__file__).parent))

from modules.text_to_sql.core import TextToSQLModule
from utils.logger import setup_logger

def run_evaluation():
    module = TextToSQLModule()
    logger = setup_logger("SQL_Evaluator")
    
    test_cases = [
        {
            "id": 1,
            "category": "Complex Aggregation & Joins",
            "question": "Find the names of customers who have spent more than the average total amount across all orders, and list the total amount they spent.",
            "expected_logic": "Join customers and orders, GROUP BY customer, HAVING SUM(total_amount) > (SELECT AVG(total_amount) FROM orders)"
        },
        {
            "id": 2,
            "category": "Financial Crossover & Conditions",
            "question": "Show the date and ma_7 for dates where ma_7 crossed above ma_30 in the gold price table, but only if rsi was below 70.",
            "expected_logic": "Self-join on date-1 for crossover, WHERE t1.ma_7 > t1.ma_30 AND t2.ma_7 <= t2.ma_30 AND t1.rsi < 70"
        },
        {
            "id": 3,
            "category": "Set Operations / Joins",
            "question": "Identify products that have never been ordered and list their names and current stock.",
            "expected_logic": "LEFT JOIN products and orders WHERE order_id IS NULL"
        },
        {
            "id": 4,
            "category": "Time Series & Growth",
            "question": "Calculate the monthly total sales and show the difference from the previous month for all of 2024.",
            "expected_logic": "GROUP BY month, use Window function LAG or self-join for difference"
        },
        {
            "id": 5,
            "category": "Multi-category Logic",
            "question": "List names of customers who bought products from both 'Electronics' and 'Furniture' categories.",
            "expected_logic": "Join customers, orders, products; filter for categories; check for both (INTERSECT or EXISTS or COUNT DISTINCT category = 2)"
        }
    ]
    
    results = []
    
    print("\n" + "="*50)
    print("STARTING SQL CAPABILITY EVALUATION")
    print("="*50 + "\n")
    
    for case in test_cases:
        print(f"Testing Case {case['id']}: {case['category']}")
        print(f"Question: {case['question']}")
        
        start_time = time.time()
        try:
            sql = module.generate_sql(case['question'])
            gen_time = time.time() - start_time
            
            print(f"Generated SQL:\n{sql}")
            
            exec_start = time.time()
            rows = module.execute_query(sql)
            exec_time = time.time() - exec_start
            
            results.append({
                "case_id": case['id'],
                "question": case['question'],
                "generated_sql": sql,
                "execution_status": "Success",
                "rows_returned": len(rows),
                "generation_time": round(gen_time, 2),
                "execution_time": round(exec_time, 2),
                "error": None
            })
            print(f"Status: SUCCESS ({len(rows)} rows, {round(gen_time + exec_time, 2)}s)")
            
        except Exception as e:
            results.append({
                "case_id": case['id'],
                "question": case['question'],
                "generated_sql": locals().get('sql', 'N/A'),
                "execution_status": "Failed",
                "error": str(e),
                "generation_time": round(time.time() - start_time, 2)
            })
            print(f"Status: FAILED - {str(e)}")
        
        print("-" * 30)
    
    # Save detailed report
    report_path = Path("logs/evaluation_report.json")
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(results, f, indent=4)
    
    print(f"\nEvaluation complete. Detailed report saved to {report_path}")
    return results

if __name__ == "__main__":
    run_evaluation()
