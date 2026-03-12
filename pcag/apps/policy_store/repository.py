"""
Policy Store 저장소 (Repository)
================================
DB CRUD 연산을 캡슐화합니다.
routes.py는 이 repository를 통해서만 DB에 접근합니다.
"""
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from pcag.core.database.models import PolicyRecord


class PolicyRepository:
    """정책 저장소 — DB CRUD"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_active_version(self) -> str | None:
        """현재 활성 정책 버전 ID 반환"""
        record = self.db.query(PolicyRecord).filter(PolicyRecord.is_active == True).first()
        return record.policy_version_id if record else None
    
    def get_policy(self, version: str) -> PolicyRecord | None:
        """특정 버전의 정책 레코드 반환"""
        return self.db.query(PolicyRecord).filter(PolicyRecord.policy_version_id == version).first()
    
    def create_policy(self, policy_version_id: str, issued_at_ms: int, 
                     document: dict, created_by: str = None) -> PolicyRecord:
        """새 정책 생성 (활성화는 별도)"""
        record = PolicyRecord(
            policy_version_id=policy_version_id,
            issued_at_ms=issued_at_ms,
            document=document,  # JSONB accepts dict directly, no json.dumps needed
            is_active=False,
            created_by=created_by
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
    
    def activate_policy(self, version: str) -> PolicyRecord | None:
        """특정 버전을 활성화 (이전 활성 정책은 비활성화)"""
        # 기존 활성 정책 비활성화
        self.db.query(PolicyRecord).filter(PolicyRecord.is_active == True).update({"is_active": False})
        
        # 대상 정책 활성화
        record = self.get_policy(version)
        if record:
            record.is_active = True
            self.db.commit()
            self.db.refresh(record)
        return record
    
    def update_asset_profile(self, version: str, asset_id: str, profile: dict) -> bool:
        """특정 자산의 정책 프로필 업데이트"""
        record = self.get_policy(version)
        if not record:
            return False
        
        doc = record.get_document()
        
        # Create a copy to ensure modification is detected
        # (SQLAlchemy JSON type might not track in-place mutations)
        import copy
        new_doc = copy.deepcopy(doc)
        
        if "assets" not in new_doc:
            new_doc["assets"] = {}
        new_doc["assets"][asset_id] = profile
        
        # Assign new dictionary and flag as modified
        record.document = new_doc
        flag_modified(record, "document")
        
        self.db.commit()
        return True
    
    def list_versions(self) -> list[str]:
        """모든 정책 버전 목록"""
        records = self.db.query(PolicyRecord.policy_version_id).all()
        return [r[0] for r in records]
