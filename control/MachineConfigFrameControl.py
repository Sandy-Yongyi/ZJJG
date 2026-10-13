

def _load_range(cfg: dict, key: str, default_min: int, default_max: int):
    pass  # 采数显示项目不使用此接口


def _get_param_range_rules(sn: int | None = None, strategy_name="frame_by_frame"):
    pass  # 采数显示项目不使用此接口


FLAT_CONFIG_KEY = "flat"


def _get_toml_path(strategy_name: str) -> str:
    pass  # 采数显示项目不使用此接口


def _normalize_origin_pos_for_ui(cfg: dict) -> dict:
    pass  # 采数显示项目不使用此接口


def _normalize_config_for_ui(cfg: dict) -> dict:
    pass  # 采数显示项目不使用此接口


def _normalize_origin_pos_for_save(values: dict) -> dict:
    pass  # 采数显示项目不使用此接口


def _normalize_ui_values_for_save(values: dict) -> dict:
    pass  # 采数显示项目不使用此接口


def load_machine_config_for_ui(sn: int, strategy_name="frame_by_frame") -> dict:
    pass  # 采数显示项目不使用此接口


def save_machine_config_from_ui(sn: int, values: dict, control_queue=None, strategy_name="frame_by_frame"):
    pass  # 采数显示项目不使用此接口


def _validate_params(values: dict, param_range_rules: dict):
    pass  # 采数显示项目不使用此接口


def _save_to_toml(sn: int, values: dict, toml_path: str, english=False):
    pass  # 采数显示项目不使用此接口


def _notify_plc(sn: int, values: dict, control_queue, toml_path: str, english=False):
    pass  # 采数显示项目不使用此接口
