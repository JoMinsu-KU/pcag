"""
Canonicalize Utility
============================================
이 모듈은 JSON 객체를 결정론적(Deterministic) 문자열로 변환하는 기능을 제공합니다.
해시 계산의 일관성을 보장하기 위해 키 정렬, 공백 제거, 부동소수점 처리 등을 수행합니다.

PCAG 파이프라인 위치:
  전체 시스템 공통 (특히 Hashing 및 Integrity Check 시 사용)

관련 문서:
  - plans/PCAG_Schema_Definitions.md §Hashing
"""

import json
from typing import Any

def canonicalize(obj: Any) -> str:
    """
    Python 객체를 결정적(Canonical) JSON 문자열로 변환합니다.
    
    해시 계산 시 입력 데이터의 순서나 공백 차이로 인해 해시값이 달라지는 것을 방지합니다.
    재귀적으로 딕셔너리 키를 정렬하고, 부동소수점 정밀도를 고정합니다.
    
    Args:
        obj (Any): 변환할 Python 객체 (dict, list, str, int, float, bool, None)
        
    Returns:
        str: 정규화된 JSON 문자열
    """
    if obj is None:
        return "null"
    elif isinstance(obj, bool):
        return "true" if obj else "false"
    elif isinstance(obj, (int, float)):
        if isinstance(obj, bool): # Python bool is int instance
            return "true" if obj else "false"
        if isinstance(obj, float):
            # 부동소수점 오차 방지를 위해 소수점 3자리로 고정
            return f"{round(obj, 3):.3f}"
        return str(obj)
    elif isinstance(obj, str):
        return json.dumps(obj)
    elif isinstance(obj, list):
        # 리스트 내부 요소들도 재귀적으로 정규화
        return "[" + ",".join(canonicalize(item) for item in obj) + "]"
    elif isinstance(obj, dict):
        # 딕셔너리 키를 알파벳 순으로 정렬하여 순서 보장
        sorted_keys = sorted(obj.keys())
        return "{" + ",".join(f'{json.dumps(key)}:{canonicalize(obj[key])}' for key in sorted_keys) + "}"
    else:
        # JSON 호환되지 않는 타입은 문자열로 변환하여 처리
        # (일반적으로는 발생하지 않아야 함)
        return json.dumps(str(obj))
