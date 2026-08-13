# SchemaVaultLocal 🚀
*The ultimate local-first SQL workbench for data analysts and quant researchers.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

SchemaVaultLocal is a **local-first, private-by-design** SQL workbench. It leverages local LLMs (via Ollama) to convert natural language into expert-level SQL, enabling seamless data analysis without ever sending your sensitive datasets to the cloud.

<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/ec706174-862e-41aa-8b0e-7006ac3817be" />

---

## ✨ Key Features
- **Intelligent Text-to-SQL**: Auto-generates complex, window-function-optimized SQL (including crossovers, divergence, and trends).
- **Self-Correcting Engine**: Automatically catches execution errors and retries with context to ensure perfect query generation.
- **Data Visualization**: Instant chart rendering for time-series and numerical insights.
- **Privacy First**: All processing runs locally on your machine. No API keys, no data leaks.
- **Query Workbench**: Save favorites, view execution history, and refine queries iteratively with LLM feedback.
- **Universal Import**: Drag-and-drop CSV/Excel files into your own local database instantly.

---

## 🚀 Quick Start
1.  **Install Prerequisites**:
    - [Ollama](https://ollama.com/) (Ensure it's running).
    - Python 3.10+
2.  **Setup**:
    ```bash
    pip install -r requirements.txt
    python main.py
    ```

---

## 🛠 Tech Stack
- **Inference**: Ollama (Llama 3.1:8b / SQLCoder)
- **GUI**: CustomTkinter (Modern, Dark/Light themed)
- **Data**: Pandas + SQLite3
- **Visualization**: Matplotlib

---

## 🚧 Roadmap

### Completed ✅
- [x] Text-to-SQL with expert-level queries
- [x] CSV/Excel import
- [x] Query classification system
- [x] SQL Query history & favorites
- [x] SQL explanation mode
- [x] Data visualization (charts)
- [x] Iterative query refinement system

### Future Enhancements 💡
- [ ] SQL guardrails (Safety filters)
- [ ] Performance optimization tips
- [ ] Custom model fine-tuning

---

## 🙏 Acknowledgements
- **Ollama** - Local LLM inference
- **CustomTkinter** - Modern GUI framework
- **Pandas** - Data manipulation
- **Agent Orchestrator** - AI Agent Orchestrator
---

**Built with passion for data analysts, traders, researchers, and anyone who works with data!**
