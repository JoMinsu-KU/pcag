"""
Hash Utility
============================================
이 모듈은 SHA-256 해시 계산을 위한 유틸리티 함수들을 제공합니다.
데이터 무결성 검증, 해시 체인 생성, 식별자 생성 등에 사용됩니다.

PCAG 파이프라인 위치:
  전체 시스템 공통 (Integrity Service, Evidence Ledger 등)
"""

import hashlib
from .canonicalize import canonicalize

GENESIS_HASH = hashlib.sha256(b"").hexdigest()
# "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
# 해시 체인의 시작점(Genesis Block) 또는 빈 값의 해시로 사용됨

def compute_hash(data: str) -> str:
    """
    문자열의 SHA-256 해시를 계산하여 16진수 문자열로 반환합니다.
    
    Args:
        data (str): 해싱할 입력 문자열
        
    Returns:
        str: 64자리 16진수 해시 문자열
    """
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

def compute_event_hash(prev_hash: str, payload: dict) -> str:
    """
    해시 체인(Hash Chain)을 위한 이벤트 해시를 계산합니다.
    
    H(n) = SHA256( H(n-1) + Canonical(Payload) )
    이전 해시와 현재 페이로드를 결합하여 체인 무결성을 보장합니다.
    
    Args:
        prev_hash (str): 직전 이벤트의 해시
        payload (dict): 현재 이벤트 데이터
        
    Returns:
        str: 현재 이벤트의 해시
    """
    canonical_payload = canonicalize(payload)
    # 이전 해시 뒤에 정규화된 페이로드를 붙여서 해싱
    return compute_hash(prev_hash + canonical_payload)

def compute_sensor_hash(sensor_snapshot: dict) -> str:
    """
    센서 스냅샷 데이터의 무결성 검증을 위한 해시를 계산합니다.
    
    Sensor Gateway가 데이터를 보낼 때 계산한 해시와
    Gateway Core가 받았을 때 계산한 해시를 비교하여 위변조 여부를 확인합니다.
    
    Args:
        sensor_snapshot (dict): 센서 데이터 딕셔너리
        
    Returns:
        str: 센서 데이터 해시
    """
    return compute_hash(canonicalize(sensor_snapshot))
