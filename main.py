"""
SchemaVaultLocal Desktop Application
Main entry point - SQL-focused local data workbench

Core module:
- Text-to-SQL: Natural language database queries
"""

import sys
import customtkinter as ctk

from config.settings import GUIConfig, initialize_all_configs
from gui.app import MainApplication
from utils.logger import setup_logger


def main():
    """Main application entry point"""
    
    # Initialize logging first
    logger = setup_logger("Main")
    logger.info("=" * 60)
    logger.info("Starting SchemaVaultLocal Application")
    logger.info("=" * 60)
    
    # Initialize all module configurations
    try:
        logger.info("Initializing configuration...")
        initialize_all_configs()
        logger.info("✓ Configuration initialized successfully")
    except Exception as e:
        logger.error(f"✗ Failed to initialize configuration: {e}")
        logger.exception("Configuration error details:")
        print(f"\nFATAL ERROR: Could not initialize configuration.\nCheck logs for details.")
        sys.exit(1)
    
    # Set CustomTkinter appearance
    try:
        logger.info("Setting up GUI theme...")
        ctk.set_appearance_mode(GUIConfig.THEME)
        ctk.set_default_color_theme("blue")
        logger.info("✓ GUI theme configured")
    except Exception as e:
        logger.error(f"✗ Failed to set GUI theme: {e}")
        logger.info("Continuing with default theme...")
    
    # Create and run main application
    try:
        logger.info("Launching main application window...")
        app = MainApplication()
        logger.info("✓ Application window created")
        logger.info("Application running. Close window to exit.")
        
        app.mainloop()
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"✗ Fatal application error: {e}")
        logger.exception("Application error details:")
        print(f"\nFATAL ERROR: {e}\nCheck logs for details.")
        sys.exit(1)
    finally:
        logger.info("=" * 60)
        logger.info("Application shutdown complete")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()