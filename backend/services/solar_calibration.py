"""태양광 일별 실측·NWP 쌍으로 시간별 예측 보정(α 스케일·잔차) 순수 함수."""

from __future__ import annotations

from typing import Any, Literal

CalibrationMode = Literal["scale", "residual_mean", "scale_and_residual"]
VALID_CALIBRATION_MODES = frozenset({"scale", "residual_mean", "scale_and_residual"})


def parse_calibration_mode(env_weights: dict[str, Any]) -> CalibrationMode:
    """environment_weights.solar_calibration_mode → 보정 모드."""
    raw = str(env_weights.get("solar_calibration_mode", "scale")).strip().lower()
    if raw in VALID_CALIBRATION_MODES:
        return raw  # type: ignore[return-value]
    return "scale"


def calibration_daily_rows_from_data(
    data: dict[str, Any],
    env_weights: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """일별 actual·NWP 행. solar_calibration_data_source=residual_demo 이면 검증용 블록."""
    source = str(env_weights.get("solar_calibration_data_source", "main")).strip().lower()
    if source == "residual_demo":
        return residual_demo_pairs_from_data(data)
    return (
        list(data.get("actual_solar_daily_kwh") or []),
        list(data.get("nwp_predicted_daily_kwh") or []),
    )


def residual_demo_pairs_from_data(
    data: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """dummy_data.jsonc의 solar_calibration_residual_demo 블록(흐린날·잔차 테스트용)."""
    block = data.get("solar_calibration_residual_demo") or {}
    if not isinstance(block, dict):
        return [], []
    actual = block.get("actual_solar_daily_kwh") or []
    nwp = block.get("nwp_predicted_daily_kwh") or []
    return list(actual), list(nwp)


def _align_daily_pairs(
    actual_rows: list[dict[str, Any]],
    nwp_rows: list[dict[str, Any]],
) -> list[tuple[str, float, float]]:
    """(date, actual_kwh, nwp_predicted_daily_kwh) 짝 목록, 날짜 오름차순."""
    nwp_by_date: dict[str, float] = {}
    for r in nwp_rows:
        if not isinstance(r, dict):
            continue
        ds = r.get("date")
        if ds is None:
            continue
        try:
            nwp_by_date[str(ds)] = float(r.get("nwp_predicted_daily_kwh", 0.0))
        except (TypeError, ValueError):
            continue

    pairs: list[tuple[str, float, float]] = []
    for r in actual_rows:
        if not isinstance(r, dict):
            continue
        ds = r.get("date")
        if ds is None:
            continue
        key = str(ds)
        if key not in nwp_by_date:
            continue
        try:
            a = float(r.get("actual_kwh", 0.0))
        except (TypeError, ValueError):
            continue
        pairs.append((key, a, nwp_by_date[key]))
    pairs.sort(key=lambda x: x[0])
    return pairs


def _window_tail(items: list[Any], window_days: int) -> list[Any]:
    w = max(0, int(window_days))
    if w > 0 and len(items) > w:
        return items[-w:]
    return items


def alpha_from_daily_pairs(
    actual_rows: list[dict[str, Any]],
    nwp_rows: list[dict[str, Any]],
    *,
    window_days: int = 30,
) -> float | None:
    """동일 날짜에 대해 actual_kwh / nwp_predicted_daily_kwh 비율의 평균(최근 window_days)."""
    pairs = _align_daily_pairs(actual_rows, nwp_rows)
    ratios: list[float] = []
    for _, a, n in _window_tail(pairs, window_days):
        if n < 1e-9:
            continue
        ratios.append(a / n)
    if not ratios:
        return None
    return sum(ratios) / len(ratios)


def daily_alpha_series(
    actual_rows: list[dict[str, Any]],
    nwp_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """일별 α_d = actual_kwh / nwp (Prophet·발표용 시계열)."""
    out: list[dict[str, Any]] = []
    for ds, a, n in _align_daily_pairs(actual_rows, nwp_rows):
        if n < 1e-9:
            continue
        out.append({"date": ds, "alpha": round(a / n, 6)})
    return out


def residuals_from_daily_pairs(
    actual_rows: list[dict[str, Any]],
    nwp_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """일별 잔차 residual_d = actual_kwh − nwp_predicted_daily_kwh (Prophet·특수일 분석용)."""
    out: list[dict[str, Any]] = []
    for ds, a, n in _align_daily_pairs(actual_rows, nwp_rows):
        out.append({"date": ds, "residual_kwh": round(a - n, 4)})
    return out


def mean_residual_kwh(
    actual_rows: list[dict[str, Any]],
    nwp_rows: list[dict[str, Any]],
    *,
    window_days: int = 30,
) -> float | None:
    """최근 window_days 일의 평균 일 잔차(kWh). 1차 보정에서 일합 오프셋으로 사용."""
    pairs = _align_daily_pairs(actual_rows, nwp_rows)
    vals = [a - n for _, a, n in _window_tail(pairs, window_days)]
    if not vals:
        return None
    return sum(vals) / len(vals)


def scale_forecast_hourly(
    rows: list[dict[str, Any]],
    alpha: float,
) -> list[dict[str, Any]]:
    """predicted_solar_kwh에 α를 곱한다(음수 방지, 소수 4자리)."""
    if alpha <= 0.0 or not rows:
        return [dict(r) for r in rows]
    out: list[dict[str, Any]] = []
    for r in rows:
        r2 = dict(r)
        try:
            v = float(r2.get("predicted_solar_kwh", 0.0))
        except (TypeError, ValueError):
            v = 0.0
        r2["predicted_solar_kwh"] = round(max(0.0, v * alpha), 4)
        out.append(r2)
    return out


def add_residual_to_hourly(
    rows: list[dict[str, Any]],
    residual_kwh: float,
    *,
    distribution: Literal["proportional", "uniform"] = "proportional",
) -> list[dict[str, Any]]:
    """일 잔차를 시간별 predicted_solar_kwh에 분배해 더한다."""
    if not rows or abs(residual_kwh) < 1e-12:
        return [dict(r) for r in rows]
    out: list[dict[str, Any]] = []
    values: list[float] = []
    for r in rows:
        try:
            values.append(max(0.0, float(r.get("predicted_solar_kwh", 0.0))))
        except (TypeError, ValueError):
            values.append(0.0)
    total = sum(values)
    n = len(rows)
    for r, v in zip(rows, values):
        r2 = dict(r)
        if distribution == "uniform":
            add = residual_kwh / n
        elif total > 1e-9:
            add = residual_kwh * (v / total)
        else:
            add = residual_kwh / n
        r2["predicted_solar_kwh"] = round(max(0.0, v + add), 4)
        out.append(r2)
    return out


def apply_solar_calibration(
    hourly_rows: list[dict[str, Any]],
    actual_rows: list[dict[str, Any]],
    nwp_rows: list[dict[str, Any]],
    *,
    mode: CalibrationMode = "scale",
    window_days: int = 30,
    residual_distribution: Literal["proportional", "uniform"] = "proportional",
    alpha_override: float | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """시간별 태양광 예측에 1차 보정 적용. meta에 α·잔차·일별 시계열 요약.

    ``alpha_override``: 외부에서 계산한 α(예: Prophet ``alpha_forecast``)가 있으면
    rolling mean α 대신 이 값으로 스케일한다. 양수일 때만 적용되며, 비교 가능하도록
    ``meta["rolling_alpha"]``에는 rolling 결과를 항상 함께 기록한다.

    ``meta["alpha_source"]``:
        - ``"override"``  — ``alpha_override`` 사용 (Prophet 경로)
        - ``"rolling_mean"`` — 기존 ``alpha_from_daily_pairs`` 결과
        - ``None`` — α를 만들 수 없는 입력(빈 행 등)
    """
    meta: dict[str, Any] = {
        "mode": mode,
        "window_days": window_days,
        "alpha": None,
        "alpha_source": None,
        "rolling_alpha": None,
        "mean_residual_kwh": None,
        "daily_alpha_series": daily_alpha_series(actual_rows, nwp_rows),
        "daily_residual_series": residuals_from_daily_pairs(actual_rows, nwp_rows),
        "applied": False,
    }
    if not hourly_rows or not actual_rows or not nwp_rows:
        return [dict(r) for r in hourly_rows], meta

    rows = [dict(r) for r in hourly_rows]
    rolling_alpha = alpha_from_daily_pairs(actual_rows, nwp_rows, window_days=window_days)
    mean_res = mean_residual_kwh(actual_rows, nwp_rows, window_days=window_days)
    meta["rolling_alpha"] = rolling_alpha
    meta["mean_residual_kwh"] = mean_res

    # alpha_override가 양수이면 우선 사용; 0 이하·None이면 rolling으로 폴백.
    if alpha_override is not None and alpha_override > 0:
        alpha: float | None = float(alpha_override)
        alpha_source: str | None = "override"
    elif rolling_alpha is not None:
        alpha = rolling_alpha
        alpha_source = "rolling_mean"
    else:
        alpha = None
        alpha_source = None
    meta["alpha"] = alpha
    meta["alpha_source"] = alpha_source

    if mode in ("scale", "scale_and_residual") and alpha is not None and alpha > 0:
        rows = scale_forecast_hourly(rows, alpha)
        meta["applied"] = True
    if mode in ("residual_mean", "scale_and_residual") and mean_res is not None:
        rows = add_residual_to_hourly(
            rows, mean_res, distribution=residual_distribution
        )
        meta["applied"] = True

    return rows, meta
