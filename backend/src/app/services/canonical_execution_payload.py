"""Derivation and versioned serialization of CanonicalExecutionPayloadV1."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.core.errors import ValidationAppError
from app.schemas.approval import ApprovalAuthorization, ApprovalAuthorizationContent
from app.schemas.canonical_execution import (
    CanonicalAccountBindingV1,
    CanonicalExecutionPayloadV1,
    CanonicalExecutionPrincipalV1,
    CanonicalExecutionSerializationV1,
)
from app.schemas.trade_plan import (
    AuthorizationState,
    ExecutionMode,
    TradePlanRevision,
    TradePlanRevisionSemantic,
)
from app.services.canonical_serialization import (
    CanonicalSerializationError,
    canonical_json_bytes,
    canonical_sha256,
)


class CanonicalExecutionPayloadSerializerV1:
    """Build V1 only from persisted immutable plan and authorization schemas."""

    @classmethod
    def derive_from_plan(
        cls,
        plan: TradePlanRevision,
        authorization: ApprovalAuthorization,
        *,
        at: datetime | None = None,
    ) -> CanonicalExecutionSerializationV1:
        now = cls._aware(at or datetime.now(UTC))
        cls._validate_plan_and_authorization(plan, authorization, at=now)
        payload = CanonicalExecutionPayloadV1(
            organization_id=plan.organization_id,
            principal=CanonicalExecutionPrincipalV1(
                user_id=plan.user_id,
                account_id=plan.account_id,
                exchange_account_id=plan.exchange_account_id,
            ),
            operation=plan.operation,
            plan_id=plan.plan_id,
            immutable_plan_revision_id=plan.revision_id,
            approval_authorization_id=authorization.authorization_id,
            plan_content_hash=plan.content_hash,
            execution_venue=plan.execution_venue,
            execution_instrument=plan.execution_instrument,
            side=plan.side,
            order_type=plan.order_type,
            time_in_force=plan.time_in_force,
            quantity=plan.quantity,
            price=plan.limit_price,
            market_marker=plan.market_marker,
            reduce_only=plan.reduce_only,
            position_binding=None,
            account_binding=CanonicalAccountBindingV1(
                account_id=plan.account_id,
                exchange_account_id=plan.exchange_account_id,
                execution_mode=ExecutionMode.PAPER,
                expected_account_mode=plan.expected_account_mode,
                margin_mode=plan.margin_mode,
                position_mode=plan.position_mode,
            ),
            instrument_rule_version=plan.instrument_rules.rules_version,
            execution_policy_version=plan.execution_policy_version,
        )
        return cls.serialize(payload)

    @staticmethod
    def serialize(payload: CanonicalExecutionPayloadV1) -> CanonicalExecutionSerializationV1:
        canonical_bytes = canonical_json_bytes(payload)
        return CanonicalExecutionSerializationV1(
            payload=payload,
            canonical_bytes=canonical_bytes,
            sha256=hashlib.sha256(canonical_bytes).hexdigest(),
        )

    @classmethod
    def deserialize(cls, canonical_bytes: bytes) -> CanonicalExecutionPayloadV1:
        """Validate and parse exact canonical V1 bytes, including duplicate-key rejection."""
        try:
            decoded = json.loads(
                canonical_bytes.decode("utf-8"),
                object_pairs_hook=cls._object_without_duplicates,
                parse_float=cls._reject_json_float,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise CanonicalSerializationError("Invalid CanonicalExecutionPayloadV1 bytes.") from exc
        payload = CanonicalExecutionPayloadV1.model_validate(cls._decode_decimals(decoded))
        if canonical_json_bytes(payload) != canonical_bytes:
            raise CanonicalSerializationError("Payload bytes are valid JSON but not canonical V1.")
        return payload

    @classmethod
    def _validate_plan_and_authorization(
        cls,
        plan: TradePlanRevision,
        authorization: ApprovalAuthorization,
        *,
        at: datetime,
    ) -> None:
        if authorization.state is not AuthorizationState.AVAILABLE:
            raise ValidationAppError("Approval authorization is unavailable.")
        if cls._aware(authorization.expires_at) <= at:
            raise ValidationAppError("Approval authorization is expired.")
        if cls._aware(plan.valid_from) > at or cls._aware(plan.valid_until) <= at:
            raise ValidationAppError("Trade plan revision is outside its validity window.")

        semantic_values = {
            name: getattr(plan, name) for name in TradePlanRevisionSemantic.model_fields
        }
        semantic = TradePlanRevisionSemantic.model_validate(semantic_values)
        if not hmac.compare_digest(canonical_sha256(semantic), plan.content_hash):
            raise ValidationAppError("Trade plan content hash verification failed.")

        expected_binding = (
            plan.organization_id,
            plan.user_id,
            plan.account_id,
            plan.exchange_account_id,
            plan.operation,
            plan.plan_id,
            plan.revision_id,
            plan.content_hash,
            plan.execution_venue,
            plan.execution_instrument,
            plan.expected_account_mode,
            plan.permission_attestation_id,
            plan.permission_attestation_version,
        )
        actual_binding = (
            authorization.organization_id,
            authorization.user_id,
            authorization.account_id,
            authorization.exchange_account_id,
            authorization.operation,
            authorization.plan_id,
            authorization.revision_id,
            authorization.plan_content_hash,
            authorization.execution_venue,
            authorization.execution_instrument,
            authorization.verified_account_mode,
            authorization.permission_attestation_id,
            authorization.permission_attestation_version,
        )
        if actual_binding != expected_binding:
            raise ValidationAppError("Authorization does not match the immutable trade plan.")

        issuance_values = {
            name: getattr(authorization, name)
            for name in ApprovalAuthorizationContent.model_fields
        }
        issuance_values["created_at"] = cls._aware(authorization.created_at)
        issuance_values["expires_at"] = cls._aware(authorization.expires_at)
        issuance = ApprovalAuthorizationContent.model_validate(issuance_values)
        if not hmac.compare_digest(
            canonical_sha256(issuance),
            authorization.authorization_content_hash,
        ):
            raise ValidationAppError("Approval authorization content hash verification failed.")

    @staticmethod
    def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate canonical JSON key: {key}")
            result[key] = value
        return result

    @staticmethod
    def _reject_json_float(_value: str) -> None:
        raise ValueError("Binary/JSON floating-point values are not valid canonical decimals.")

    @classmethod
    def _decode_decimals(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [cls._decode_decimals(item) for item in value]
        if not isinstance(value, dict):
            return value
        if set(value) == {"scale", "value"}:
            coefficient = value["value"]
            scale = value["scale"]
            if (
                not isinstance(coefficient, str)
                or not isinstance(scale, int)
                or isinstance(scale, bool)
                or scale < 0
            ):
                raise CanonicalSerializationError("Invalid canonical Decimal object.")
            try:
                return Decimal(coefficient).scaleb(-scale)
            except Exception as exc:
                raise CanonicalSerializationError("Invalid canonical Decimal coefficient.") from exc
        return {key: cls._decode_decimals(item) for key, item in value.items()}

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
