"""
Policy Store 저장소 계층.

핵심 역할은 정책 문서를 CRUD하는 것뿐 아니라,
"정책 버전은 불변"이라는 PCAG semantics를 DB 레벨에서 지키는 것이다.
"""

import copy
import time
import uuid

from sqlalchemy.orm import Session

from pcag.core.database.models import PolicyRecord


class PolicyRepository:
    """정책 버전 조회/생성/활성화/파생 생성을 담당한다."""

    def __init__(self, db: Session):
        self.db = db

    def get_active_version(self) -> str | None:
        record = self.db.query(PolicyRecord).filter(PolicyRecord.is_active == True).first()
        return record.policy_version_id if record else None

    def get_policy(self, version: str) -> PolicyRecord | None:
        return self.db.query(PolicyRecord).filter(PolicyRecord.policy_version_id == version).first()

    def create_policy(self, policy_version_id: str, issued_at_ms: int, document: dict, created_by: str = None) -> PolicyRecord:
        record = PolicyRecord(
            policy_version_id=policy_version_id,
            issued_at_ms=issued_at_ms,
            document=document,
            is_active=False,
            created_by=created_by,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def activate_policy(self, version: str) -> PolicyRecord | None:
        # active 포인터는 하나만 존재해야 하므로,
        # 새 버전을 활성화할 때 기존 active는 먼저 내려준다.
        self.db.query(PolicyRecord).filter(PolicyRecord.is_active == True).update({"is_active": False})

        record = self.get_policy(version)
        if record:
            record.is_active = True
            self.db.commit()
            self.db.refresh(record)
        return record

    def update_asset_profile(
        self,
        version: str,
        asset_id: str,
        profile: dict,
        *,
        new_policy_version_id: str | None = None,
        created_by: str | None = None,
        change_reason: str | None = None,
    ) -> PolicyRecord | None:
        """
        Clone an existing policy version and update one asset profile.

        The original version remains immutable. A new policy record is
        created and returned.
        """
        # 기존 레코드를 덮어쓰지 않고 새 버전을 파생시키는 이유는,
        # 감사 관점에서 "어떤 정책이 언제부터 적용됐는지"를 추적 가능하게 만들기 위해서다.
        record = self.get_policy(version)
        if not record:
            return None

        doc = copy.deepcopy(record.get_document())
        doc.setdefault("assets", {})
        doc["assets"][asset_id] = profile

        metadata = doc.setdefault("metadata", {})
        metadata["derived_from_version"] = version
        metadata["updated_asset_id"] = asset_id
        if change_reason:
            metadata["change_reason"] = change_reason

        issued_at_ms = int(time.time() * 1000)
        candidate_version = new_policy_version_id or f"{version}-rev-{issued_at_ms}-{uuid.uuid4().hex[:8]}"
        # 버전 충돌 가능성은 낮지만, 실서비스에서는 절대 중복되면 안 되므로 확인한다.
        while self.get_policy(candidate_version):
            candidate_version = f"{version}-rev-{issued_at_ms}-{uuid.uuid4().hex[:8]}"

        doc["policy_version_id"] = candidate_version

        return self.create_policy(
            policy_version_id=candidate_version,
            issued_at_ms=issued_at_ms,
            document=doc,
            created_by=created_by,
        )

    def list_versions(self) -> list[str]:
        records = self.db.query(PolicyRecord.policy_version_id).all()
        return [row[0] for row in records]
