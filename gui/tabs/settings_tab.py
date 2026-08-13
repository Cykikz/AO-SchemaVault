import customtkinter as ctk
from config.settings import TextToSQLConfig
import json
import os

class SettingsTab:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.config_file = "user_settings.json"
        self.settings = self.load_settings()
        
        self.setup_ui()
    
    def load_settings(self):
        """Load user settings from file"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return {
            'use_local_llm': True,
            'api_provider': 'openai',
            'api_key': '',
            'local_model': 'llama3.1:8b'
        }

    def get_available_models(self):
        """Fetch list of models from Ollama"""
        try:
            import ollama
            models_info = ollama.list()
            # Handle different versions of python-ollama (list vs dict)
            if hasattr(models_info, 'models'):
                return [m.model for m in models_info.models]
            return [m['name'] for m in models_info.get('models', [])]
        except Exception as e:
            self.app.logger.warning(f"Could not fetch models from Ollama: {e}")
            return ["llama3.1:8b"] # Fallback
    
    def save_settings(self):
        """Save settings to file"""
        self.settings['use_local_llm'] = self.local_llm_var.get()
        self.settings['api_key'] = self.api_key_field.get()
        self.settings['api_provider'] = self.provider_var.get()
        self.settings['local_model'] = self.model_var.get()
        
        with open(self.config_file, 'w') as f:
            json.dump(self.settings, f)
        
        self.app.update_status("Settings saved!", "green")
    
    def setup_ui(self):
        """Setup settings interface"""
        self.parent.grid_columnconfigure(0, weight=1)
        self.parent.grid_rowconfigure(0, weight=1)
        
        # Main frame
        main_frame = ctk.CTkScrollableFrame(self.parent)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # ===== LLM Settings =====
        llm_label = ctk.CTkLabel(
            main_frame,
            text="🤖 LLM Settings",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        llm_label.grid(row=0, column=0, pady=(0, 10), sticky="w")
        
        # Local/API Toggle
        self.local_llm_var = ctk.BooleanVar(value=self.settings['use_local_llm'])
        
        local_frame = ctk.CTkFrame(main_frame)
        local_frame.grid(row=1, column=0, sticky="ew", pady=10)
        
        ctk.CTkLabel(local_frame, text="Use Local LLM (Ollama):").pack(side="left")
        ctk.CTkSwitch(
            local_frame,
            variable=self.local_llm_var,
            command=self.on_llm_mode_change,
            onvalue=True,
            offvalue=False
        ).pack(side="right")
        
        # Local Model Selection
        self.local_model_frame = ctk.CTkFrame(main_frame)
        self.local_model_frame.grid(row=2, column=0, sticky="ew", pady=10)
        
        ctk.CTkLabel(self.local_model_frame, text="Local Model:").pack(side="left", padx=(0, 10))
        self.model_var = ctk.StringVar(value=self.settings['local_model'])
        model_dropdown = ctk.CTkComboBox(
            self.local_model_frame,
            values=self.get_available_models(),
            variable=self.model_var,
            state="readonly"
        )
        model_dropdown.pack(side="left")
        
        local_status = ctk.CTkLabel(
            self.local_model_frame,
            text="✅ Ollama running",
            text_color="green"
        )
        local_status.pack(side="right")
        
        # API Settings
        self.api_frame = ctk.CTkFrame(main_frame)
        self.api_frame.grid(row=3, column=0, sticky="ew", pady=10)
        
        ctk.CTkLabel(self.api_frame, text="API Provider:").pack(side="left", padx=(0, 10))
        self.provider_var = ctk.StringVar(value=self.settings['api_provider'])
        provider_dropdown = ctk.CTkComboBox(
            self.api_frame,
            values=["openai", "anthropic", "cohere"],
            variable=self.provider_var,
            state="readonly"
        )
        provider_dropdown.pack(side="left")
        
        # API Key Input
        api_key_label = ctk.CTkLabel(
            main_frame,
            text="API Key:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        api_key_label.grid(row=4, column=0, sticky="w", pady=(20, 5))
        
        self.api_key_field = ctk.CTkEntry(
            main_frame,
            placeholder_text="sk-...",
            show="•",  # Hide API key
            height=40
        )
        self.api_key_field.grid(row=5, column=0, sticky="ew", pady=5)
        self.api_key_field.insert(0, self.settings['api_key'])
        
        # API Key Info
        info_label = ctk.CTkLabel(
            main_frame,
            text="Get your API key from: openai.com/api",
            text_color="gray",
            font=ctk.CTkFont(size=10)
        )
        info_label.grid(row=6, column=0, sticky="w", pady=(0, 20))
        
        # Separator
        separator = ctk.CTkFrame(main_frame, height=2, fg_color="gray30")
        separator.grid(row=7, column=0, sticky="ew", pady=20)
        
        # ===== Display Settings =====
        display_label = ctk.CTkLabel(
            main_frame,
            text="🎨 Display Settings",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        display_label.grid(row=8, column=0, pady=(0, 10), sticky="w")
        
        theme_frame = ctk.CTkFrame(main_frame)
        theme_frame.grid(row=9, column=0, sticky="ew", pady=10)
        
        ctk.CTkLabel(theme_frame, text="Theme:").pack(side="left")
        ctk.CTkComboBox(
            theme_frame,
            values=["Dark", "Light"],
            state="readonly"
        ).pack(side="left", padx=10)
        
        # Separator
        separator2 = ctk.CTkFrame(main_frame, height=2, fg_color="gray30")
        separator2.grid(row=10, column=0, sticky="ew", pady=20)
        
        # ===== Info =====
        info_frame = ctk.CTkFrame(main_frame, fg_color="gray20", corner_radius=10)
        info_frame.grid(row=11, column=0, sticky="ew", pady=10)
        
        info_title = ctk.CTkLabel(
            info_frame,
            text="ℹ️ About",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        info_title.pack(anchor="w", padx=10, pady=(10, 0))
        
        info_text = ctk.CTkLabel(
            info_frame,
            text="Local Mode: Uses Ollama (free, private, no API key needed)\n"
                 "API Mode: Uses OpenAI/other providers (costs money, but works anywhere)",
            text_color="gray",
            font=ctk.CTkFont(size=10),
            justify="left"
        )
        info_text.pack(anchor="w", padx=10, pady=(5, 10))
        
        # ===== Buttons =====
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.grid(row=12, column=0, sticky="ew", pady=20)
        button_frame.grid_columnconfigure(0, weight=1)
        
        save_btn = ctk.CTkButton(
            button_frame,
            text="💾 Save Settings",
            command=self.save_settings,
            fg_color="#2fa572",
            hover_color="#25874f"
        )
        save_btn.pack(side="right", padx=(10, 0))
        
        test_btn = ctk.CTkButton(
            button_frame,
            text="🧪 Test Connection",
            command=self.test_connection
        )
        test_btn.pack(side="right")
    
    def on_llm_mode_change(self):
        """Handle switching between local and API mode"""
        use_local = self.local_llm_var.get()
        
        if use_local:
            self.local_model_frame.grid()
            self.app.update_status("Switched to Local LLM mode", "blue")
        else:
            self.app.update_status("Switched to API mode", "blue")
    
    def test_connection(self):
        """Test LLM connection"""
        self.app.update_status("Testing connection...", "blue")
        
        if self.local_llm_var.get():
            # Test Ollama
            try:
                import ollama
                response = ollama.generate(
                    model=self.model_var.get(),
                    prompt="Say 'OK'",
                    stream=False
                )
                self.app.update_status("✅ Ollama connection successful!", "green")
            except Exception as e:
                self.app.update_status(f"❌ Ollama error: {str(e)}", "red")
        else:
            # Test API
            api_key = self.api_key_field.get()
            if not api_key:
                self.app.update_status("❌ API key is empty!", "red")
                return
            
            try:
                import openai
                openai.api_key = api_key
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Say OK"}],
                    max_tokens=10
                )
                self.app.update_status("✅ API connection successful!", "green")
            except Exception as e:
                self.app.update_status(f"❌ API error: {str(e)}", "red")