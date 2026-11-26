import uuid
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import (
    apply_safe_ordering,
    envelope_response,
    paginated_envelope_response,
    parse_bool_param,
)
from config.exceptions import DomainError
from .models import RateSnapshot
from .services import create_rate_snapshot, get_current_rate_snapshot


RATE_Q = Decimal("0.0001")


def _rate_str(val: Decimal | str | int | float) -> str:
    return str(Decimal(str(val)).quantize(RATE_Q, rounding=ROUND_HALF_UP))


def serialize_rate_snapshot(snap: RateSnapshot) -> dict:
    return {
        "id": str(snap.id),
        "snapshotId": snap.snapshot_code,
        "sourceMode": snap.source_mode,
        "isCurrent": snap.is_current,
        "entryUsdRate": _rate_str(snap.live_usd_sell),
        "entryHasGoldTry": _rate_str(snap.live_has_gold_try_sell),
        "liveUsdSell": _rate_str(snap.live_usd_sell),
        "liveEurSell": _rate_str(snap.live_eur_sell),
        "liveHasGoldTrySell": _rate_str(snap.live_has_gold_try_sell),
        "fxBaseRates": {k: _rate_str(v) for k, v in (snap.fx_base_rates or {}).items()},
        "createdAt": snap.created_at.isoformat(),
        "updatedAt": snap.created_at.isoformat(),
    }


class UpdateRatesSerializer(serializers.Serializer):
    sourceMode = serializers.ChoiceField(choices=["auto", "manual"], required=False)
    liveUsdSell = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0.0001"), required=False
    )
    liveEurSell = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("0.0001"), required=False
    )
    liveHasGoldTrySell = serializers.DecimalField(
        max_digits=14, decimal_places=4, min_value=Decimal("1"), required=False
    )
    fxBaseRates = serializers.DictField(
        child=serializers.DecimalField(max_digits=16, decimal_places=4, min_value=Decimal("0.0001")),
        required=False,
    )


class MarketRatesView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=["Market"], summary="Aktif piyasa kuru snapshot'ını getir")
    def get(self, request: Request):
        snap = get_current_rate_snapshot()
        return envelope_response(serialize_rate_snapshot(snap), request)


def _apply_rate_snapshot_update(request: Request, data: dict) -> RateSnapshot:
    current = get_current_rate_snapshot()
    merged_rates = current.get_decimal_rates()
    if "fxBaseRates" in data:
        for code, val in data["fxBaseRates"].items():
            merged_rates[code.upper()] = Decimal(str(val))
    if "liveUsdSell" in data:
        merged_rates["USD"] = data["liveUsdSell"]
    if "liveEurSell" in data:
        merged_rates["EUR"] = data["liveEurSell"]

    return create_rate_snapshot(
        fx_base_rates=merged_rates,
        source_mode=data.get("sourceMode", RateSnapshot.SourceMode.MANUAL),
        live_has_gold_try_sell=data.get("liveHasGoldTrySell"),
        actor=request.user,
    )


class OpsRatesUpdateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "rates:edit"

    @extend_schema(
        tags=["OPS - Market"],
        summary="Aktif piyasa kurlarını güncelle (yeni immutable snapshot üretir)",
        request=UpdateRatesSerializer,
    )
    def patch(self, request: Request):
        serializer = UpdateRatesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        snap = _apply_rate_snapshot_update(request, serializer.validated_data)
        return envelope_response(serialize_rate_snapshot(snap), request)


class OpsRateSnapshotListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "pricing:read",
        "POST": "rates:edit",
    }

    @extend_schema(tags=["OPS - Market"], summary="Kur snapshot geçmişini listele")
    def get(self, request: Request):
        qs = RateSnapshot.objects.all()
        source_mode = (request.query_params.get("sourceMode") or request.query_params.get("source_mode") or "").strip()
        if source_mode:
            qs = qs.filter(source_mode=source_mode)
        is_current = parse_bool_param(request.query_params.get("isCurrent") or request.query_params.get("is_current"))
        if is_current is not None:
            qs = qs.filter(is_current=is_current)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(snapshot_code__icontains=q) | Q(source_mode__icontains=q))
        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={
                "createdAt": "created_at",
                "created_at": "created_at",
                "snapshotId": "snapshot_code",
                "liveHasGoldTrySell": "live_has_gold_try_sell",
                "liveUsdSell": "live_usd_sell",
            },
            default="-created_at",
        )
        return paginated_envelope_response(qs, request, serialize_rate_snapshot)

    @extend_schema(
        tags=["OPS - Market"],
        summary="Yeni immutable piyasa kuru snapshot'ı oluştur",
        request=UpdateRatesSerializer,
    )
    def post(self, request: Request):
        serializer = UpdateRatesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        snap = _apply_rate_snapshot_update(request, serializer.validated_data)
        return envelope_response(serialize_rate_snapshot(snap), request, status=201)


class OpsRateSnapshotDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "pricing:read"

    @extend_schema(tags=["OPS - Market"], summary="Kur snapshot detayını getir")
    def get(self, request: Request, snapshot_id: str):
        snap = RateSnapshot.objects.filter(snapshot_code=snapshot_id).first()
        if snap is None:
            try:
                uuid.UUID(str(snapshot_id))
            except (ValueError, TypeError):
                snap = None
            else:
                snap = RateSnapshot.objects.filter(id=snapshot_id).first()
        if snap is None:
            raise DomainError("Kur snapshot kaydı bulunamadı.", code="SNAPSHOT_NOT_FOUND", status_code=404)
        return envelope_response(serialize_rate_snapshot(snap), request)


MarketRatesPublicView = MarketRatesView
