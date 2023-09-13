import os
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource


class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """
    Taken from https://docs.pydantic.dev/latest/usage/pydantic_settings/#adding-sources
    """

    def __init__(self, settings_cls: type[BaseSettings]):
        super().__init__(settings_cls)
        try:
            self.settings_dict = yaml.load(Path(os.environ.get('SETTINGS_FILE', 'settings.yaml')).read_text('utf-8'), Loader=yaml.Loader)
        except FileNotFoundError:
            self.settings_dict = defaultdict(lambda: None)
            print('settings.yaml not found. Using defaults.')

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> Tuple[Any, str, bool]:
        field_value = self.settings_dict[field_name] if field_name in self.settings_dict else field.default
        return field_value, field_name, False

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
    ) -> Any:
        return value

    def __call__(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}

        for field_name, field in self.settings_cls.model_fields.items():
            field_value, field_key, value_is_complex = self.get_field_value(
                field, field_name
            )
            field_value = self.prepare_field_value(
                field_name, field, field_value, value_is_complex
            )
            if field_value is not None:
                d[field_key] = field_value

        return d


class LogLevel(str, Enum):
    CRITICAL = 'CRITICAL'
    ERROR = 'ERROR'
    WARNING = 'WARNING'
    INFO = 'INFO'
    DEBUG = 'DEBUG'