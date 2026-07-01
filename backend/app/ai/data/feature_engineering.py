# app/ai/data/feature_engineering.py

import pandas as pd
import numpy as np
from app.ai.config import FEATURE_COLUMNS


def add_time_derived_features(df, timestamp_col=None):
    """
    Trích xuất feature thời gian cho cả training và realtime inference.

    Dùng import lồng để tránh mọi lỗi scope hoặc circular import.
    """
    # ✅ Import nội bộ – chống mọi lỗi datetime scope
    from datetime import datetime

    # =====================================================
    # LẤY GIỜ
    # =====================================================
    if timestamp_col is not None and timestamp_col in df.columns:
        times = pd.to_datetime(df[timestamp_col])
        df["hour"] = times.dt.hour
    else:
        # Realtime inference → lấy giờ hệ thống
        df["hour"] = datetime.now().hour

    # =====================================================
    # NIGHT FEATURE (20h - 6h)
    # =====================================================
    df["is_night"] = df["hour"].apply(
        lambda x: 1 if (x >= 20 or x <= 6) else 0
    )

    # =====================================================
    # DARK FEATURE (light_level < 50)
    # =====================================================
    if "light_level" in df.columns:
        df["is_dark"] = (
            pd.to_numeric(df["light_level"], errors="coerce")
            .fillna(100)  # nếu lỗi parse → coi như đủ sáng
            .apply(lambda x: 1 if float(x) < 50 else 0)
        )
    else:
        df["is_dark"] = 0

    return df


def finalize_features(df):
    """
    Đảm bảo:
    - Đủ tất cả cột trong FEATURE_COLUMNS
    - Không NaN
    - Đúng thứ tự model yêu cầu
    """

    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        ).fillna(0.0)

    return df[FEATURE_COLUMNS]


def transform_to_features(raw_data):
    """
    Wrapper dùng cho realtime inference.
    raw_data: dict từ sensor payload
    """

    df = pd.DataFrame([raw_data])

    df = add_time_derived_features(df)
    df = finalize_features(df)

    return df