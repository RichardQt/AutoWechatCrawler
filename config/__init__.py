# Make config a package so it can be imported as `config`.
from .config_manager import (
    get_config,
    get_database_config,
    get_table_config,
    get_crawler_config,
    get_article_id_config,
    get_db_operation_config,
    get_ui_automation_config,
)
