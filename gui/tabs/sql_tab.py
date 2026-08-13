"""
Text-to-SQL Tab - COMPLETELY INDEPENDENT
Changes here won't affect other tabs
"""

import customtkinter as ctk
from tkinter import filedialog
import threading
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
from config.settings import TextToSQLConfig
from gui.theme import AppTheme
from modules.text_to_sql.core import TextToSQLModule
from utils.logger import setup_logger


class TextToSQLTab:
    """
    Text-to-SQL interface tab
    
    Features:
    - Natural language input
    - SQL query generation using LLM
    - Query execution on sample database
    - Results display
    - Schema viewer
    - Import CSV/Excel files
    """
    
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app  # Reference to main app for status updates
        self.logger = setup_logger("TextToSQL")
        self.mono_font = ctk.CTkFont(family="Consolas", size=12)
        
        # Initialize the backend module
        try:
            self.module = TextToSQLModule()
            self.logger.info("Text-to-SQL module initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize module: {e}")
            self.module = None
        
        self.current_query = None
        self.results = None
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup UI components"""
        self.parent.configure(fg_color="transparent")
        self.parent.grid_columnconfigure(0, weight=3)
        self.parent.grid_columnconfigure(1, weight=2)
        self.parent.grid_rowconfigure(0, weight=0)
        self.parent.grid_rowconfigure(1, weight=1)

        intro = ctk.CTkLabel(
            self.parent,
            text="Ask in plain English, review generated SQL, and execute safely on your local data.",
            font=ctk.CTkFont(size=12),
            text_color=AppTheme.TEXT_MUTED,
            anchor="w",
        )
        intro.grid(row=0, column=0, columnspan=2, padx=12, pady=(8, 6), sticky="ew")

        left_column = ctk.CTkFrame(self.parent, fg_color="transparent")
        left_column.grid(row=1, column=0, padx=(12, 8), pady=(0, 12), sticky="nsew")
        left_column.grid_columnconfigure(0, weight=1)
        left_column.grid_rowconfigure(1, weight=1)

        right_column = ctk.CTkFrame(self.parent, fg_color="transparent")
        right_column.grid(row=1, column=1, padx=(8, 12), pady=(0, 12), sticky="nsew")
        right_column.grid_columnconfigure(0, weight=1)
        right_column.grid_rowconfigure(1, weight=1)

        self.create_input_area(left_column)
        self.create_sql_area(left_column)
        self.create_action_buttons(left_column)
        self.create_schema_viewer(right_column)
        self.create_results_area(right_column)
    
        # Use transparent frames to blend into background
        self.parent.configure(fg_color="transparent")
        
        # Left and Right main columns
        left_column = ctk.CTkFrame(self.parent, fg_color="transparent")
        left_column.grid(row=1, column=0, padx=(12, 8), pady=(0, 12), sticky="nsew")
        left_column.grid_columnconfigure(0, weight=1)
        left_column.grid_rowconfigure(1, weight=1)

        right_column = ctk.CTkFrame(self.parent, fg_color="transparent")
        right_column.grid(row=1, column=1, padx=(8, 12), pady=(0, 12), sticky="nsew")
        right_column.grid_columnconfigure(0, weight=1)
        right_column.grid_rowconfigure(1, weight=1)

        self.create_input_area(left_column)
        self.create_sql_area(left_column)
        self.create_action_buttons(left_column)
        self.create_schema_viewer(right_column)
        self.create_results_area(right_column)
    
    def create_input_area(self, parent):
        """Natural language input area"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=0, pady=(0, 8), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            frame,
            text="Question",
            anchor="w",
            text_color=AppTheme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, padx=0, pady=(0, 4), sticky="w")
        
        self.input_text = ctk.CTkEntry(
            frame,
            placeholder_text="e.g., Show all customers with purchases above 1000",
            height=36,
            corner_radius=6,
            fg_color=AppTheme.INPUT_BG,
            border_width=0,
            text_color=AppTheme.TEXT_PRIMARY,
        )
        self.input_text.grid(row=1, column=0, padx=(0, 8), pady=(0, 10), sticky="ew")
        
        self.generate_btn = ctk.CTkButton(
            frame,
            text="Generate SQL",
            command=self.generate_sql,
            width=130,
            height=36,
            corner_radius=6,
            fg_color=AppTheme.BRAND,
            hover_color=AppTheme.BRAND_HOVER,
            text_color=AppTheme.TEXT_ON_ACCENT,
        )
        self.generate_btn.grid(row=1, column=1, padx=0, pady=(0, 10))
    
    def create_sql_area(self, parent):
        """SQL query display area"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=1, column=0, pady=(0, 8), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            frame,
            text="Generated SQL",
            anchor="w",
            text_color=AppTheme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, padx=0, pady=(0, 4), sticky="w")
        
        self.sql_text = ctk.CTkTextbox(
            frame,
            height=176,
            wrap="word",
            corner_radius=6,
            fg_color=AppTheme.INPUT_BG,
            border_width=0,
            text_color=AppTheme.TEXT_PRIMARY,
            font=self.mono_font,
        )
        self.sql_text.grid(row=1, column=0, padx=0, pady=(0, 10), sticky="ew")
        self.sql_text.insert(
            "1.0",
            "-- Generated SQL will appear here.\n-- Review it before execution.",
        )
        
        self.save_favorite_btn = ctk.CTkButton(
            frame,
            text="Save to Favorites",
            command=self.save_favorite,
            state="disabled",
            fg_color=AppTheme.NEUTRAL_BTN,
            hover_color=AppTheme.NEUTRAL_BTN_HOVER,
            text_color=AppTheme.NEUTRAL_BTN_TEXT,
            corner_radius=6,
            height=28,
        )
        self.save_favorite_btn.grid(row=2, column=0, padx=0, pady=(0, 10), sticky="ew")
    
    def create_results_area(self, parent):
        """Query results display area"""
        self.results_container = ctk.CTkFrame(parent, fg_color="transparent")
        self.results_container.grid(row=1, column=0, sticky="nsew")
        self.results_container.grid_rowconfigure(0, weight=1)
        self.results_container.grid_columnconfigure(0, weight=1)
        
        # Text view (default)
        self.results_text = ctk.CTkTextbox(
            self.results_container,
            wrap="none",
            corner_radius=6,
            fg_color=AppTheme.INPUT_BG,
            border_width=0,
            text_color=AppTheme.TEXT_PRIMARY,
            font=self.mono_font,
        )
        self.results_text.grid(row=0, column=0, sticky="nsew")
        self.results_text.insert("1.0", "Run a query to see results.")
        
        # Chart view (hidden initially)
        self.chart_frame = ctk.CTkFrame(self.results_container, fg_color="transparent")
        # chart_frame is NOT gridded until toggled
        
        self.is_visualizing = False
    
    def create_action_buttons(self, parent):
        """Action buttons"""
        frame = ctk.CTkFrame(
            parent,
            corner_radius=0,
            fg_color="transparent",
            border_width=0,
        )
        frame.grid(row=2, column=0, sticky="nsew")
        frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        self.execute_btn = ctk.CTkButton(
            frame,
            text="Execute Query",
            command=self.execute_query,
            state="disabled",
            fg_color=AppTheme.BRAND,
            hover_color=AppTheme.BRAND_HOVER,
            text_color=AppTheme.TEXT_ON_ACCENT,
            corner_radius=6,
            height=36,
        )
        self.execute_btn.grid(row=0, column=0, padx=(0, 4), pady=10, sticky="ew")
        
        self.clear_btn = ctk.CTkButton(
            frame,
            text="Clear",
            command=self.clear_all,
            fg_color=AppTheme.NEUTRAL_BTN,
            hover_color=AppTheme.NEUTRAL_BTN_HOVER,
            text_color=AppTheme.NEUTRAL_BTN_TEXT,
            corner_radius=6,
            height=36,
        )
        self.clear_btn.grid(row=0, column=1, padx=4, pady=10, sticky="ew")
        
        self.export_btn = ctk.CTkButton(
            frame,
            text="Export",
            command=self.export_results,
            state="disabled",
            fg_color=AppTheme.NEUTRAL_BTN,
            hover_color=AppTheme.NEUTRAL_BTN_HOVER,
            text_color=AppTheme.NEUTRAL_BTN_TEXT,
            corner_radius=6,
            height=36,
        )
        self.export_btn.grid(row=0, column=2, padx=4, pady=10, sticky="ew")

        self.visualize_btn = ctk.CTkButton(
            frame,
            text="Visualize",
            command=self.toggle_visualization,
            state="disabled",
            fg_color=AppTheme.NEUTRAL_BTN,
            hover_color=AppTheme.NEUTRAL_BTN_HOVER,
            text_color=AppTheme.NEUTRAL_BTN_TEXT,
            corner_radius=6,
            height=36,
        )
        self.visualize_btn.grid(row=0, column=3, padx=(4, 0), pady=10, sticky="ew")

        self.explain_btn = ctk.CTkButton(
            frame,
            text="Explain Query",
            command=self.explain_query,
            state="disabled",
            fg_color=AppTheme.NEUTRAL_BTN,
            hover_color=AppTheme.NEUTRAL_BTN_HOVER,
            text_color=AppTheme.NEUTRAL_BTN_TEXT,
            text_color_disabled=AppTheme.TEXT_MUTED,
            corner_radius=6,
            height=36,
        )
        self.explain_btn.grid(row=1, column=0, columnspan=3, padx=12, pady=(0, 10), sticky="ew")
    
    def create_schema_viewer(self, parent):
        """Database schema viewer with import functionality"""
        frame = ctk.CTkFrame(
            parent,
            corner_radius=0,
            fg_color="transparent",
            border_width=0,
        )
        frame.grid(row=0, column=0, pady=(0, 8), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(
            frame,
            text="Schema & Data",
            text_color=AppTheme.TEXT_PRIMARY,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")
        
        schema_btn = ctk.CTkButton(
            frame,
            text="View Schema",
            command=self.show_schema,
            width=120,
            fg_color=AppTheme.NEUTRAL_BTN,
            hover_color=AppTheme.NEUTRAL_BTN_HOVER,
            text_color=AppTheme.NEUTRAL_BTN_TEXT,
            corner_radius=6,
        )
        schema_btn.grid(row=1, column=0, padx=12, pady=(0, 6), sticky="ew")
        
        import_btn = ctk.CTkButton(
            frame,
            text="Import Data",
            command=self.import_data,
            width=130,
            fg_color=AppTheme.NEUTRAL_BTN,
            hover_color=AppTheme.NEUTRAL_BTN_HOVER,
            text_color=AppTheme.NEUTRAL_BTN_TEXT,
            corner_radius=6,
        )
        import_btn.grid(row=2, column=0, padx=12, pady=(0, 6), sticky="ew")
        
        self.tables_btn = ctk.CTkButton(
            frame,
            text="Imported Tables",
            command=self.show_imported_tables,
            width=150,
            fg_color=AppTheme.NEUTRAL_BTN,
            hover_color=AppTheme.NEUTRAL_BTN_HOVER,
            text_color=AppTheme.NEUTRAL_BTN_TEXT,
            corner_radius=6,
        )
        self.tables_btn.grid(row=3, column=0, padx=12, pady=(0, 6), sticky="ew")

        self.history_btn = ctk.CTkButton(
            frame,
            text="View History",
            command=self.show_history,
            width=150,
            fg_color=AppTheme.BRAND,
            hover_color=AppTheme.BRAND_HOVER,
            text_color=AppTheme.TEXT_ON_ACCENT,
            corner_radius=6,
        )
        self.history_btn.grid(row=4, column=0, padx=12, pady=(0, 6), sticky="ew")
        
        examples_label = ctk.CTkLabel(
            frame,
            text="Try: Show all customers\nTry: Products under 100\nTry: Total sales by customer",
            justify="left",
            font=ctk.CTkFont(size=10),
            text_color=AppTheme.TEXT_MUTED,
        )
        examples_label.grid(row=5, column=0, padx=12, pady=(2, 10), sticky="w")
    
    def save_favorite(self):
        """Save current query to favorites"""
        if not self.current_query:
            return
            
        question = self.input_text.get().strip()
        try:
            self.module.save_query(question, self.current_query, is_favorite=True)
            self.app.update_status("Query saved to favorites!", "success")
        except Exception as e:
            self.app.update_status(f"Failed to save: {str(e)}", "error")

    def show_history(self):
        """Display query history"""
        if not self.module:
            return
            
        try:
            history = self.module.get_history()
            if not history:
                self.update_results("No history yet.")
                return
                
            output = ["QUERY HISTORY", "=" * 40, ""]
            for item in history:
                output.append(f"[{item['timestamp']}]")
                output.append(f"Q: {item['question']}")
                output.append(f"SQL: {item['sql_query'][:50]}...")
                output.append("-" * 20)
            
            self.update_results("\n".join(output))
        except Exception as e:
            self.update_results(f"Error loading history: {str(e)}")
            
    def generate_sql(self):
        """Generate SQL from natural language"""
        if not self.module:
            self.update_sql("Error: Module not initialized. Check logs.")
            self.app.update_status("Text-to-SQL module not available", "error")
            return
        
        def task():
            try:
                question = self.input_text.get().strip()
                
                if not question:
                    self.update_sql("Please enter a question")
                    self.app.update_status("Please enter a question", "warning")
                    return
                
                self.update_sql("🔄 Generating SQL query...")
                self.app.update_status("Generating SQL query...", "info")
                self._set_button_state(self.generate_btn, "disabled")
                
                # Generate SQL using Ollama
                sql_query = self.module.generate_sql(question)
                
                self.current_query = sql_query
                self.update_sql(sql_query)
                self._set_button_state(self.execute_btn, "normal")
                self._set_button_state(self.explain_btn, "normal")
                self._set_button_state(self.save_favorite_btn, "normal")
                
                self.app.update_status("SQL query generated successfully", "success")
                self.logger.info(f"SQL generated for: {question}")
                
            except Exception as e:
                self.update_sql(f"❌ Error: {str(e)}")
                self.app.update_status(f"Error generating SQL: {str(e)}", "error")
                self.logger.error(f"SQL generation error: {e}")
            finally:
                self._set_button_state(self.generate_btn, "normal")
        
        thread = threading.Thread(target=task, daemon=True)
        thread.start()

    def explain_query(self):
        """Explain the current SQL query"""
        if not self.module or not self.current_query:
            return
            
        def task():
            try:
                self.update_results("🔍 Generating explanation...")
                self.app.update_status("Generating explanation...", "info")
                self._set_button_state(self.explain_btn, "disabled")
                
                explanation = self.module.explain_sql(self.current_query)
                self.update_results(f"EXPLANATION:\n\n{explanation}")
                self.app.update_status("Explanation generated", "success")
                
            except Exception as e:
                self.update_results(f"❌ Error generating explanation:\n\n{str(e)}")
                self.app.update_status("Explanation failed", "error")
            finally:
                self._set_button_state(self.explain_btn, "normal")
        
        threading.Thread(target=task, daemon=True).start()
    
    def toggle_visualization(self):
        """Toggle between text and chart view"""
        if not hasattr(self, 'current_df') or self.current_df is None:
            return
            
        if self.is_visualizing:
            self.chart_frame.grid_forget()
            self.results_text.grid(row=0, column=0, sticky="nsew")
            self.visualize_btn.configure(text="Visualize")
            self.is_visualizing = False
        else:
            self.results_text.grid_forget()
            self._render_chart()
            self.chart_frame.grid(row=0, column=0, sticky="nsew")
            self.visualize_btn.configure(text="Show Text")
            self.is_visualizing = True

    def _render_chart(self):
        """Render matplotlib chart"""
        # Clear existing
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
            
        fig, ax = plt.subplots(figsize=(5, 3), dpi=100)
        fig.patch.set_facecolor('#111111')
        ax.set_facecolor('#111111')
        
        # Simple auto-plot (first numeric column vs index/date)
        df = self.current_df
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            df[numeric_cols[0]].plot(ax=ax, color='#5B9DFF')
            
        ax.tick_params(colors='#B4B4B4')
        ax.spines['bottom'].set_color('#3A3A3A')
        ax.spines['left'].set_color('#3A3A3A')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        plt.close(fig)

    def execute_query(self):
        """Execute the SQL query"""
        if not self.module:
            self.app.update_status("Module not initialized", "error")
            return
        
        def task():
            try:
                self.update_results("⏳ Executing query...")
                self.app.update_status("Executing query...", "info")
                self._set_button_state(self.execute_btn, "disabled")
                
                # Execute query
                results = self.module.execute_query(self.current_query)
                
                # Format and display results
                if results:
                    self.current_df = pd.DataFrame(results)
                    formatted = self._format_results(results)
                    self.update_results(formatted)
                    self._set_button_state(self.export_btn, "normal")
                    self._set_button_state(self.visualize_btn, "normal")
                    self.app.update_status(f"Query returned {len(results)} rows", "success")
                else:
                    self.current_df = None
                    self.update_results("No results found.")
                    self.app.update_status("Query returned no results", "warning")
                    self._set_button_state(self.visualize_btn, "disabled")
                
                self.logger.info(f"Query executed: {len(results) if results else 0} rows")
                
            except Exception as e:
                error_msg = str(e)
                self.update_results(f"❌ Error executing query:\n\n{error_msg}")
                self.app.update_status(f"Query error: {error_msg[:50]}...", "error")
                self.logger.error(f"Query execution error: {e}")
            finally:
                self._set_button_state(self.execute_btn, "normal")
        
        thread = threading.Thread(target=task, daemon=True)
        thread.start()
    
    def show_schema(self):
        """Display database schema"""
        if not self.module:
            self.app.update_status("Module not initialized", "error")
            return
        
        try:
            self.app.update_status("Loading schema...", "info")
            schema = self.module.get_schema()
            self.update_results(schema)
            self.app.update_status("Schema loaded", "success")
            self.logger.info("Schema displayed")
        except Exception as e:
            self.logger.error(f"Schema display error: {e}")
            self.update_results(f"Error loading schema: {str(e)}")
            self.app.update_status("Error loading schema", "error")
    
    def clear_all(self):
        """Clear all fields"""
        self.input_text.delete(0, "end")
        self.sql_text.delete("1.0", "end")
        self.results_text.delete("1.0", "end")
        self.current_query = None
        self.current_df = None
        self.is_visualizing = False
        self._set_button_state(self.execute_btn, "disabled")
        self._set_button_state(self.export_btn, "disabled")
        self._set_button_state(self.visualize_btn, "disabled")
        self.app.update_status("Cleared all fields", "muted")
        self.logger.info("All fields cleared")
    
    def export_results(self):
        """Export query results to file"""
        content = self.results_text.get("1.0", "end-1c")
        
        if not content.strip():
            self.app.update_status("No results to export", "warning")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("CSV files", "*.csv"),
                ("All files", "*.*")
            ]
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(f"Query: {self.current_query}\n\n")
                    f.write("Results:\n")
                    f.write(content)
                
                self.logger.info(f"Results exported to: {filename}")
                self.app.update_status(f"Exported to {Path(filename).name}", "success")
            except Exception as e:
                self.logger.error(f"Export error: {e}")
                self.app.update_status(f"Export failed: {str(e)}", "error")
    
    def import_data(self):
        """Import CSV or Excel file"""
        if not self.module:
            self.app.update_status("Module not initialized", "error")
            return
        
        # File selection dialog
        filetypes = (
            ("CSV files", "*.csv"),
            ("Excel files", "*.xlsx *.xls"),
            ("All files", "*.*")
        )
        
        filename = filedialog.askopenfilename(
            title="Select CSV or Excel file to import",
            filetypes=filetypes
        )
        
        if not filename:
            return
        
        # Import in background thread
        def task():
            try:
                self.app.update_status("Importing file...", "info")
                
                # Import file
                result = self.module.import_file(filename)
                
                # Show success message
                success_msg = f"""✅ Import Successful!

Table Name: {result['table_name']}
Rows Imported: {result['rows']}
Columns: {result['columns']}

Column Names:
{', '.join(result['column_names'])}

You can now ask questions about this data!
Try: "Show all data from {result['table_name']}" """
                
                self.update_results(success_msg)
                self.app.update_status(
                    f"Imported {result['rows']} rows into '{result['table_name']}'",
                    "success",
                )
                
                self.logger.info(f"File imported successfully: {filename}")
                
            except Exception as e:
                error_msg = f"❌ Import Failed\n\n{str(e)}"
                self.update_results(error_msg)
                self.app.update_status(f"Import failed: {str(e)}", "error")
                self.logger.error(f"Import error: {e}")
        
        thread = threading.Thread(target=task, daemon=True)
        thread.start()
    
    def show_imported_tables(self):
        """Show list of imported tables with info"""
        if not self.module:
            self.app.update_status("Module not initialized", "error")
            return
        
        try:
            self.app.update_status("Loading imported tables...", "info")
            
            # Get list of imported tables
            tables = self.module.list_imported_tables()
            
            if not tables:
                self.update_results("No imported tables found.\n\nClick 'Import Data' to add your own datasets!")
                self.app.update_status("No imported tables", "warning")
                return
            
            # Build detailed info
            output = ["=" * 60]
            output.append("IMPORTED TABLES")
            output.append("=" * 60)
            output.append("")
            
            for table in tables:
                info = self.module.get_table_info(table)
                if info:
                    output.append(f"📊 Table: {table}")
                    output.append(f"   Rows: {info['row_count']}")
                    output.append(f"   Columns: {', '.join(info['columns'])}")
                    output.append("")
            
            output.append("=" * 60)
            output.append(f"Total Imported Tables: {len(tables)}")
            output.append("")
            output.append("💡 Tip: Ask questions about any of these tables!")
            
            self.update_results("\n".join(output))
            self.app.update_status(f"Found {len(tables)} imported tables", "success")
            
        except Exception as e:
            self.logger.error(f"Error showing tables: {e}")
            self.update_results(f"Error: {str(e)}")
            self.app.update_status("Error loading tables", "error")
    
    def update_sql(self, text):
        """Update SQL text area"""
        self._run_on_ui(lambda: self._replace_text(self.sql_text, text))
    
    def update_results(self, text):
        """Update results text area"""
        self._run_on_ui(lambda: self._replace_text(self.results_text, text))

    def _replace_text(self, widget, text):
        widget.delete("1.0", "end")
        widget.insert("1.0", text)

    def _set_button_state(self, button, state):
        self._run_on_ui(lambda: button.configure(state=state))

    def _run_on_ui(self, callback):
        self.parent.after(0, callback)
    
    def _format_results(self, results):
        """Format query results for display as a simple table"""
        if not results:
            return "No results found"
        
        formatted = []
        
        # Get column names from first row
        headers = list(results[0].keys())
        
        # Calculate column widths
        col_widths = {}
        for header in headers:
            col_widths[header] = len(header)
            for row in results:
                col_widths[header] = max(col_widths[header], len(str(row[header])))
        
        # Create header row
        header_line = " | ".join(h.ljust(col_widths[h]) for h in headers)
        formatted.append(header_line)
        formatted.append("-" * len(header_line))
        
        # Add data rows
        for row in results:
            row_line = " | ".join(str(row[h]).ljust(col_widths[h]) for h in headers)
            formatted.append(row_line)
        
        # Add summary
        formatted.append("")
        formatted.append(f"Total rows: {len(results)}")
        
        return "\n".join(formatted)