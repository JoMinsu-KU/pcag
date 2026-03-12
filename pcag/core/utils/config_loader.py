"""
PCAG Config 로더
================
YAML 설정 파일을 로드하여 시스템 전체에서 사용할 수 있게 합니다.
실제 공정 연결 시 config 파일만 변경하면 코드 수정 없이 동작합니다.

config 파일 위치: 프로젝트 루트/config/
"""
import os
import logging
import yaml
import re

logger = logging.getLogger(__name__)

# 프로젝트 루트 경로
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")

# 캐시 — 파일당 1번만 로드
_cache = {}


def load_config(filename: str, required: bool = False) -> dict:
    """
    config/ 디렉토리에서 YAML 파일 로드
    
    Args:
        filename: 파일명 (예: "services.yaml")
        required: If True, raise FileNotFoundError when file is missing
    
    Returns:
        dict: YAML 파일 내용
    """
    if filename in _cache:
        return _cache[filename]
    
    filepath = os.path.join(CONFIG_DIR, filename)
    
    if not os.path.exists(filepath):
        if required:
            logger.critical(f"[FAIL-HARD] Config file missing: {filepath}")
            raise FileNotFoundError(f"Required config file not found: {filepath}")
        else:
            logger.warning(f"Config file not found: {filepath}, returning empty dict")
            return {}
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            data = yaml.safe_load(content) or {}
            
        # Post-process: Environment variable substitution
        data = _substitute_env_vars(data)
            
        _cache[filename] = data
        logger.info(f"Config loaded: {filepath}")
        return data
    except Exception as e:
        logger.critical(f"[FAIL-HARD] Config parse error in {filepath}: {e}")
        raise e


def load_required_config(filename: str) -> dict:
    """
    Load a config file and raise FileNotFoundError if it doesn't exist.
    """
    return load_config(filename, required=True)


def _substitute_env_vars(data):
    """
    Recursively substitute environment variables in string values.
    Pattern: ${VAR:default} or ${VAR}
    """
    if isinstance(data, dict):
        return {k: _substitute_env_vars(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_substitute_env_vars(v) for v in data]
    elif isinstance(data, str):
        def replace(match):
            var_name = match.group(1)
            default_val = match.group(2) if match.group(2) is not None else ""
            return os.environ.get(var_name, default_val)
        
        # Regex for ${VAR} or ${VAR:default}
        # ([^}:]+) captures VAR name
        # (?::([^}]*))? captures :default part optionally
        pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
        return re.sub(pattern, replace, data)
    else:
        return data


def get_service_urls() -> dict:
    """서비스 URL 설정 로드"""
    config = load_config("services.yaml")
    services = config.get("services", {})
    return {name: svc.get("url", "") for name, svc in services.items()}


def get_sensor_mappings() -> dict:
    """센서 매핑 설정 로드"""
    return load_config("sensor_mappings.yaml")


def get_cbf_mappings() -> list:
    """CBF 상태 매핑 설정 로드"""
    config = load_config("cbf_mappings.yaml")
    return config.get("mappings", [])


def clear_cache():
    """캐시 초기화 (테스트용)"""
    _cache.clear()


def get_auth_config() -> dict:
    """인증 설정 로드"""
    config = load_config("services.yaml")
    # 기본값 제거, 설정 없으면 빈 dict 반환 (상위에서 검증)
    return config.get("auth", {})
