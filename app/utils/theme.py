from pathlib import Path
from typing import Optional

from loguru import logger

from app.utils.app_info import AppInfo

theme_data_folder = AppInfo().theme_data_folder
theme_storage_folder = AppInfo().theme_storage_folder


class Themes:
    def __init__(self, theme_name: Optional[str] = None):
        self.theme_name = theme_name or self.get_default_theme_name()
        self.validate_theme()

    def get_default_theme_name(self) -> str:
        """
        Get the default theme name by scanning the theme data folder.
        """
        for folder in theme_data_folder.iterdir():
            if folder.is_dir():
                return folder.name
        return "RimPy"  # Fallback to "RimPy" if no theme folders are found

    def validate_theme(self):
        supported_themes = [
            folder.name for folder in theme_data_folder.iterdir() if folder.is_dir()
        ] + [
            folder.name for folder in theme_storage_folder.iterdir() if folder.is_dir()
        ]

        if self.theme_name not in supported_themes:
            # If the provided theme is not supported, default to "RimPy"
            self.theme_name = "RimPy"
            logger.error(
                f"Invalid theme '{self.theme_name}' detected. Defaulting to 'RimPy' theme."
            )

    def style_sheet(self) -> str:
        theme_data_folder_path = theme_data_folder / self.theme_name / "style.qss"
        theme_storage_folder_path = theme_storage_folder / self.theme_name / "style.qss"

        if theme_data_folder_path.exists():
            stylesheet_path = theme_data_folder_path
        elif theme_storage_folder_path.exists():
            stylesheet_path = theme_storage_folder_path
        else:
            raise FileNotFoundError("Stylesheet file not found in either folder.")

        return stylesheet_path.read_text()

    def theme_icon(self, icon_name: str) -> Path:
        theme_folder = theme_data_folder / self.theme_name / "icons"
        icon_path = theme_folder / f"{icon_name}.png"

        if not icon_path.exists():
            raise FileNotFoundError(f"Icon file not found: {icon_path}")

        return icon_path

    @classmethod
    def get_available_themes(cls) -> list[Path]:
        """
        Get a list of available theme folders in the theme data folder.
        """
        available_themes = []
        for folder in theme_data_folder.iterdir():
            if folder.is_dir():
                stylesheet_path = folder / "style.qss"
                if stylesheet_path.exists():
                    available_themes.append(folder)
                else:
                    logger.warning(
                        f"Skipping folder '{folder.name}' as it doesn't contain a valid stylesheet."
                    )

        # Read themes from theme_folder
        for folder in theme_storage_folder.iterdir():
            if folder.is_dir():
                stylesheet_path = folder / "style.qss"
                if stylesheet_path.exists():
                    available_themes.append(folder)
                else:
                    logger.warning(
                        f"Skipping folder '{folder.name}' in theme_folder as it doesn't contain a valid stylesheet."
                    )

        return available_themes
