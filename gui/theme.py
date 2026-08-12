"""Centralized UI tokens for a clean dark/light CustomTkinter experience."""


class AppTheme:
    """Shared color/typography tokens."""

    # Core surfaces
    APP_BG = ("#FCFCFC", "#111111")
    SIDEBAR_BG = ("#FFFFFF", "#15171B")
    CONTENT_BG = ("#FCFCFC", "#111111")
    CARD_BG = ("#FFFFFF", "#191919")
    CARD_SUBTLE_BG = ("#F7F8FA", "#161616")
    INPUT_BG = ("#FFFFFF", "#161616")

    # Borders
    BORDER = ("#E3E3E5", "#3A3A3A")
    BORDER_SOFT = ("#ECECEF", "#2E2E2E")

    # Text
    TEXT_PRIMARY = ("#1A1A1A", "#EEEEEE")
    TEXT_SECONDARY = ("#505A6B", "#B4B4B4")
    TEXT_MUTED = ("#707A8C", "#9A9A9A")

    # Brand / semantic
    BRAND = ("#2563EB", "#5B9DFF")
    BRAND_HOVER = ("#1D4ED8", "#4B8EEF")
    SUCCESS = ("#1A7F37", "#6CB16C")
    SUCCESS_HOVER = ("#176B2F", "#5DA35D")
    WARNING = ("#9A6B00", "#FFCC4A")
    WARNING_HOVER = ("#835C00", "#E6B840")
    DANGER = ("#C0392B", "#D4544F")
    DANGER_HOVER = ("#A93226", "#BE4A45")
    TEXT_ON_ACCENT = ("#FFFFFF", "#F7FAFF")

    NEUTRAL_BTN = ("#F1F3F6", "#222222")
    NEUTRAL_BTN_HOVER = ("#E7EBF0", "#2A2A2A")
    NEUTRAL_BTN_TEXT = ("#2A3342", "#D6D6D6")

    STATUS_COLORS = {
        "green": SUCCESS,
        "success": SUCCESS,
        "blue": BRAND,
        "info": BRAND,
        "orange": WARNING,
        "warning": WARNING,
        "red": DANGER,
        "error": DANGER,
        "gray": TEXT_MUTED,
        "muted": TEXT_MUTED,
    }

    @classmethod
    def resolve_status_color(cls, color):
        """Map semantic status keys to themed colors."""
        if not color:
            return cls.TEXT_MUTED
        return cls.STATUS_COLORS.get(color, color)