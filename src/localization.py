"""
Localization manager for Docker Software Manager
Handles loading and retrieving translated strings
"""

import json
import logging
import os
from typing import Dict, Optional
import locale

logger = logging.getLogger(__name__)


class LocalizationManager:
    """Manage application localization"""
    
    def __init__(self, lang_dir: str = "lang", default_lang: str = "en", database_manager=None):
        """
        Initialize localization manager
        
        Args:
            lang_dir: Directory containing language files
            default_lang: Default language code
            database_manager: DatabaseManager instance for saving preferences
        """
        self.lang_dir = lang_dir
        self.default_lang = default_lang
        self.current_lang = default_lang
        self.translations: Dict[str, Dict] = {}
        self.db = database_manager
        
        # Load translations first
        self._load_translations()
        
        # Try to load saved language preference
        if self.db:
            saved_lang = self.db.get_setting('language')
            if saved_lang and saved_lang in self.translations:
                self.current_lang = saved_lang
                logger.info(f"Loaded saved language: {saved_lang}")
            else:
                # Auto-detect system language if no saved preference
                self._detect_system_language()
        else:
            # Auto-detect system language
            self._detect_system_language()
    
    def _detect_system_language(self):
        """Detect system language and set as current if available"""
        try:
            # Get system locale
            system_locale = locale.getdefaultlocale()[0]
            
            if system_locale:
                # Extract language code (e.g., 'en_US' -> 'en')
                lang_code = system_locale.split('_')[0].lower()
                
                # Check if we have translations for this language
                lang_file = os.path.join(self.lang_dir, f"{lang_code}.json")
                if os.path.exists(lang_file):
                    self.current_lang = lang_code
                    logger.info(f"Auto-detected language: {lang_code}")
                else:
                    logger.info(f"No translations for {lang_code}, using {self.default_lang}")
            
        except Exception as e:
            logger.warning(f"Could not detect system language: {e}")
    
    def _load_translations(self):
        """Load all available translation files"""
        if not os.path.exists(self.lang_dir):
            logger.warning(f"Language directory not found: {self.lang_dir}")
            return
        
        # Load all .json files in lang directory
        for filename in os.listdir(self.lang_dir):
            if filename.endswith('.json'):
                lang_code = filename[:-5]  # Remove .json extension
                filepath = os.path.join(self.lang_dir, filename)
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self.translations[lang_code] = json.load(f)
                    logger.info(f"Loaded translations: {lang_code}")
                    
                except Exception as e:
                    logger.error(f"Error loading {filename}: {e}")
        
        # Ensure default language is loaded
        if self.default_lang not in self.translations:
            logger.error(f"Default language {self.default_lang} not found!")
    
    def set_language(self, lang_code: str) -> bool:
        """
        Set current language
        
        Args:
            lang_code: Language code (e.g., 'en', 'ru')
            
        Returns:
            True if language was set successfully
        """
        if lang_code in self.translations:
            self.current_lang = lang_code
            
            # Save to database if available
            if self.db:
                self.db.set_setting('language', lang_code)
            
            logger.info(f"Language set to: {lang_code}")
            return True
        else:
            logger.warning(f"Language not available: {lang_code}")
            return False
    
    def get_available_languages(self) -> Dict[str, str]:
        """Get list of available languages with their names"""
        languages = {}
        for lang_code in self.translations.keys():
            # Get language name from translation file
            lang_data = self.translations[lang_code]
            lang_name = lang_data.get('app', {}).get('language_name', lang_code.upper())
            languages[lang_code] = lang_name
        return languages
    
    def get(self, key: str, **kwargs) -> str:
        """
        Get translated string
        
        Args:
            key: Translation key in dot notation (e.g., 'app.name')
            **kwargs: Format parameters for string interpolation
            
        Returns:
            Translated string or key if not found
        """
        # Try current language first
        text = self._get_from_dict(self.translations.get(self.current_lang, {}), key)
        
        # Fallback to default language
        if text is None and self.current_lang != self.default_lang:
            text = self._get_from_dict(self.translations.get(self.default_lang, {}), key)
        
        # Fallback to key itself
        if text is None:
            logger.warning(f"Translation not found: {key}")
            text = key
        
        # Apply string formatting if parameters provided
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError as e:
                logger.error(f"Missing format parameter for '{key}': {e}")
        
        return text
    
    def _get_from_dict(self, data: Dict, key: str) -> Optional[str]:
        """
        Get value from nested dictionary using dot notation
        
        Args:
            data: Dictionary to search
            key: Dot-separated key path
            
        Returns:
            Value or None if not found
        """
        keys = key.split('.')
        current = data
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        
        return current if isinstance(current, str) else None
    
    def __call__(self, key: str, **kwargs) -> str:
        """
        Shorthand for get() method
        
        Args:
            key: Translation key
            **kwargs: Format parameters
            
        Returns:
            Translated string
        """
        return self.get(key, **kwargs)


# Global instance
_localization = None


def get_localization() -> LocalizationManager:
    """Get global localization instance"""
    global _localization
    if _localization is None:
        _localization = LocalizationManager()
    return _localization


def init_localization(database_manager=None):
    """Initialize localization with database support"""
    global _localization
    _localization = LocalizationManager(database_manager=database_manager)
    return _localization


def set_language(lang_code: str) -> bool:
    """Set global language"""
    return get_localization().set_language(lang_code)


def t(key: str, **kwargs) -> str:
    """
    Translate string (shorthand function)
    
    Args:
        key: Translation key
        **kwargs: Format parameters
        
    Returns:
        Translated string
    """
    return get_localization().get(key, **kwargs)


# Export singleton for direct access
localization_manager = get_localization()
