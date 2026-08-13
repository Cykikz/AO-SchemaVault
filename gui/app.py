"""
Main GUI Application with a cleaner linear-style shell and SQL-first layout.
"""

import customtkinter as ctk
from config.settings import GUIConfig
from gui.theme import AppTheme
from gui.tabs.sql_tab import TextToSQLTab
from gui.tabs.settings_tab import SettingsTab
from utils.logger import setup_logger


class MainApplication(ctk.CTk):
    """Main application window with sidebar navigation and focused content."""

    def __init__(self):
        super().__init__()

        self.logger = setup_logger("MainApp")
        self.page_status_label = None

        self.title(GUIConfig.WINDOW_TITLE)
        self.geometry(f"{GUIConfig.WINDOW_WIDTH}x{GUIConfig.WINDOW_HEIGHT}")
        self.minsize(1100, 760)
        self.configure(fg_color=AppTheme.APP_BG)

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self.create_shell_layout()
        self.create_status_bar()
        self.sync_theme_controls()

        self.logger.info("Main application window initialized")

    def create_shell_layout(self):
        """Create modern sidebar + content shell."""
        shell = ctk.CTkFrame(self, corner_radius=0, fg_color=AppTheme.APP_BG)
        shell.grid(row=0, column=0, sticky="nsew")
        shell.grid_rowconfigure(0, weight=1)
        shell.grid_columnconfigure(0, weight=0)
        shell.grid_columnconfigure(1, weight=1)

        self.create_sidebar(shell)
        self.create_content_area(shell)

    def create_sidebar(self, parent):
        """Create left navigation/sidebar area."""
        sidebar = ctk.CTkFrame(
            parent,
            width=280,
            corner_radius=0,
            fg_color=AppTheme.SIDEBAR_BG,
            border_width=0,
        )
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(6, weight=1)

        brand = ctk.CTkLabel(
            sidebar,
            text="SchemaVaultLocal",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=AppTheme.TEXT_PRIMARY,
            anchor="w",
        )
        brand.grid(row=0, column=0, padx=24, pady=(24, 6), sticky="ew")

        subtitle = ctk.CTkLabel(
            sidebar,
            text="PROJECT",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=AppTheme.TEXT_MUTED,
            anchor="w",
        )
        subtitle.grid(row=1, column=0, padx=24, pady=(2, 10), sticky="ew")

        nav_row = ctk.CTkFrame(
            sidebar,
            fg_color=AppTheme.CARD_BG,
            corner_radius=8,
            border_width=1,
            border_color=AppTheme.BORDER,
        )
        nav_row.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="ew")
        nav_row.grid_columnconfigure(1, weight=1)

        nav_indicator = ctk.CTkFrame(
            nav_row, width=2, corner_radius=2, fg_color=AppTheme.BRAND
        )
        nav_indicator.grid(row=0, column=0, padx=(8, 0), pady=8, sticky="ns")

        nav_button = ctk.CTkButton(
            nav_row,
            text="Text to SQL",
            fg_color=AppTheme.CARD_BG,
            hover_color=AppTheme.CARD_BG,
            text_color=AppTheme.TEXT_PRIMARY,
            corner_radius=6,
            height=36,
            anchor="w",
            command=lambda: self.switch_tab("sql")
        )
        nav_button.grid(row=0, column=1, padx=(8, 8), pady=8, sticky="ew")
        
        self.settings_button = ctk.CTkButton(
            nav_row,
            text="Settings",
            fg_color="transparent",
            hover_color=AppTheme.CARD_BG,
            text_color=AppTheme.TEXT_SECONDARY,
            corner_radius=6,
            height=36,
            anchor="w",
            command=lambda: self.switch_tab("settings")
        )
        self.settings_button.grid(row=1, column=1, padx=(8, 8), pady=8, sticky="ew")

        hint = ctk.CTkLabel(
            sidebar,
            text="Local mode.\nNo data leaves your machine.",
            justify="left",
            text_color=AppTheme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=12),
        )
        hint.grid(row=3, column=0, padx=24, pady=(2, 18), sticky="w")

        theme_label = ctk.CTkLabel(
            sidebar,
            text="Appearance",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=AppTheme.TEXT_MUTED,
            anchor="w",
        )
        theme_label.grid(row=4, column=0, padx=24, pady=(0, 6), sticky="ew")

        self.theme_selector = ctk.CTkSegmentedButton(
            sidebar,
            values=["Dark", "Light"],
            command=self.change_theme,
            height=32,
            corner_radius=6,
            selected_color=AppTheme.BRAND,
            selected_hover_color=AppTheme.BRAND_HOVER,
            unselected_color=AppTheme.NEUTRAL_BTN,
            unselected_hover_color=AppTheme.NEUTRAL_BTN_HOVER,
            text_color=AppTheme.TEXT_PRIMARY,
        )
        self.theme_selector.grid(row=5, column=0, padx=16, pady=(0, 16), sticky="ew")

        version = ctk.CTkLabel(
            sidebar,
            text="v1.0.0",
            text_color=AppTheme.TEXT_MUTED,
            font=ctk.CTkFont(size=10),
        )
        version.grid(row=7, column=0, padx=24, pady=(0, 18), sticky="w")

    def create_content_area(self, parent):
        """Create content area with compact top bar and SQL workspace."""
        content = ctk.CTkFrame(parent, fg_color=AppTheme.CONTENT_BG, corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=0)
        content.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure(0, weight=1)

        topbar = ctk.CTkFrame(
            content,
            corner_radius=0,
            fg_color=AppTheme.CARD_BG,
            border_width=0,
        )
        topbar.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 10))
        topbar.grid_columnconfigure(0, weight=1)

        title_block = ctk.CTkFrame(topbar, fg_color="transparent")
        title_block.grid(row=0, column=0, padx=14, pady=10, sticky="w")

        page_title = ctk.CTkLabel(
            title_block,
            text="Text to SQL",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=AppTheme.TEXT_PRIMARY,
            anchor="w",
        )
        page_title.grid(row=0, column=0, sticky="w")

        page_subtitle = ctk.CTkLabel(
            title_block,
            text="Generate SQL, run it instantly, and keep your data private.",
            font=ctk.CTkFont(size=11),
            text_color=AppTheme.TEXT_MUTED,
            anchor="w",
        )
        page_subtitle.grid(row=1, column=0, pady=(2, 0), sticky="w")

        self.page_status_label = ctk.CTkLabel(
            topbar,
            text="Ready",
            text_color=AppTheme.TEXT_MUTED,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=AppTheme.CARD_SUBTLE_BG,
            corner_radius=6,
            padx=10,
            pady=4,
        )
        self.page_status_label.grid(row=0, column=1, padx=12, pady=10, sticky="e")

        self.workspace = ctk.CTkFrame(content, corner_radius=0, fg_color="transparent")
        self.workspace.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))
        self.workspace.grid_rowconfigure(0, weight=1)
        self.workspace.grid_columnconfigure(0, weight=1)

        self.init_sql_view(self.workspace)

    def switch_tab(self, tab_name):
        """Switch between tabs."""
        # Clear workspace
        for widget in self.workspace.winfo_children():
            widget.destroy()
            
        if tab_name == "sql":
            self.init_sql_view(self.workspace)
        elif tab_name == "settings":
            self.init_settings_view(self.workspace)

    def init_sql_view(self, parent):
        """Initialize SQL workspace."""
        try:
            TextToSQLTab(parent, self)
            self.logger.info("Text-to-SQL view initialized")
        except Exception as e:
            self.logger.error(f"Text-to-SQL view failed: {e}")
            error_label = ctk.CTkLabel(
                parent,
                text=f"Text-to-SQL failed to load\n\n{e}",
                font=ctk.CTkFont(size=14),
            )
            error_label.pack(expand=True, pady=50)

    def init_settings_view(self, parent):
        """Initialize Settings workspace."""
        try:
            SettingsTab(parent, self)
            self.logger.info("Settings view initialized")
        except Exception as e:
            self.logger.error(f"Settings view failed: {e}")
            error_label = ctk.CTkLabel(
                parent,
                text=f"Settings failed to load\n\n{e}",
                font=ctk.CTkFont(size=14),
            )
            error_label.pack(expand=True, pady=50)

    def create_status_bar(self):
        """Create status bar at bottom of window."""
        self.status_frame = ctk.CTkFrame(
            self,
            height=34,
            corner_radius=0,
            fg_color=AppTheme.SIDEBAR_BG,
            border_width=0,
        )
        self.status_frame.grid(row=1, column=0, sticky="ew")
        self.status_frame.grid_propagate(False)
        self.status_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Ready",
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=AppTheme.TEXT_SECONDARY,
        )
        self.status_label.grid(row=0, column=0, padx=16, pady=6, sticky="w")

        privacy_label = ctk.CTkLabel(
            self.status_frame,
            text="Local mode",
            font=ctk.CTkFont(size=10),
            text_color=AppTheme.TEXT_MUTED,
        )
        privacy_label.grid(row=0, column=1, padx=16, pady=6, sticky="e")

    def update_status(self, message, color=None):
        """Update bottom and top status labels."""
        def apply_status():
            resolved_color = AppTheme.resolve_status_color(color)
            self.status_label.configure(text=message, text_color=resolved_color)
            if self.page_status_label:
                self.page_status_label.configure(text=message, text_color=resolved_color)

        self.after(0, apply_status)
        self.logger.info(f"Status: {message}")

    def change_theme(self, choice):
        """Change appearance mode from segmented control."""
        mode = "dark" if choice == "Dark" else "light"
        ctk.set_appearance_mode(mode)
        self.sync_theme_controls()
        self.logger.info(f"Switched to {mode} theme")

    def sync_theme_controls(self):
        """Keep segmented control in sync with active appearance mode."""
        current_mode = ctk.get_appearance_mode()
        if hasattr(self, "theme_selector"):
            self.theme_selector.set("Dark" if current_mode == "Dark" else "Light")