from datetime import datetime, timezone
from io import BytesIO

from flask import Blueprint, Response, g, jsonify, request

from app.extensions.database import db
from app.infrastructure.persistence.models.patient_hr_record_model import PatientHeartRateRecordModel
from app.infrastructure.persistence.models.patient_profile_model import PatientProfileModel
from app.presentation.api.auth_api import auth_required
from app.wiring import container


patient_report_api = Blueprint("patient_report_api", __name__)


def _extract_filename(content_disposition: str | None, default: str = "alfred_report.pdf") -> str:
    if not content_disposition:
        return default
    for part in content_disposition.split(";"):
        part = part.strip()
        if part.lower().startswith("filename="):
            return part.split("=", 1)[1].strip().strip('"') or default
    return default


def _calc_summary(records):
    if not records:
        return {
            "count": 0,
            "avg_bpm": None,
            "min_bpm": None,
            "max_bpm": None,
            "normal_rate_percent": None,
            "severity_counts": {"normal": 0, "caution": 0, "warning": 0, "critical": 0},
        }

    bpms = [r.bpm for r in records]
    severity_counts = {"normal": 0, "caution": 0, "warning": 0, "critical": 0}
    normal_count = 0

    for r in records:
        sev = (r.severity or "normal").lower()
        if sev not in severity_counts:
            severity_counts[sev] = 0
        severity_counts[sev] += 1
        if sev == "normal":
            normal_count += 1

    return {
        "count": len(records),
        "avg_bpm": round(sum(bpms) / len(bpms), 2),
        "min_bpm": min(bpms),
        "max_bpm": max(bpms),
        "normal_rate_percent": round((normal_count / len(records)) * 100, 2),
        "severity_counts": severity_counts,
    }


@patient_report_api.route("/profile", methods=["GET"])
@auth_required
def get_profile():
    user = g.current_user
    profile = PatientProfileModel.query.filter_by(user_id=user.id).first()
    if not profile:
        return jsonify({"status": "success", "profile": None})
    return jsonify({"status": "success", "profile": profile.to_dict()})


@patient_report_api.route("/profile", methods=["PUT"])
@auth_required
def upsert_profile():
    user = g.current_user
    data = request.get_json(silent=True) or {}

    profile = PatientProfileModel.query.filter_by(user_id=user.id).first()
    if not profile:
        profile = PatientProfileModel(user_id=user.id)
        db.session.add(profile)

    for field in [
        "patient_name", "age", "gender",
        "baseline_hr_rest", "baseline_hr_min", "baseline_hr_max",
        "diagnosis_notes", "medications",
        "consent_analytics", "consent_pdf_export",
    ]:
        if field in data:
            setattr(profile, field, data[field])

    db.session.commit()
    return jsonify({"status": "success", "profile": profile.to_dict()})


@patient_report_api.route("/hr-records", methods=["POST"])
@auth_required
def create_hr_record():
    user = g.current_user
    data = request.get_json(silent=True) or {}

    bpm = data.get("bpm")
    if bpm is None:
        return jsonify({"status": "error", "message": "bpm is required"}), 400

    try:
        bpm = int(bpm)
    except Exception:
        return jsonify({"status": "error", "message": "bpm must be an integer"}), 400

    record = PatientHeartRateRecordModel(
        user_id=user.id,
        bpm=bpm,
        severity=str(data.get("severity", "normal")),
        risk=data.get("risk"),
        mood=data.get("mood"),
        source=str(data.get("source", "manual")),
        note=data.get("note"),
        recorded_at=datetime.now(timezone.utc),
    )
    db.session.add(record)
    db.session.commit()

    return jsonify({"status": "success", "record": record.to_dict()}), 201


@patient_report_api.route("/hr-records", methods=["GET"])
@auth_required
def list_hr_records():
    user = g.current_user
    limit = request.args.get("limit", default=200, type=int)
    limit = max(1, min(limit, 1000))

    records = (
        PatientHeartRateRecordModel.query
        .filter_by(user_id=user.id)
        .order_by(PatientHeartRateRecordModel.recorded_at.desc())
        .limit(limit)
        .all()
    )
    return jsonify({
        "status": "success",
        "records": [r.to_dict() for r in records],
        "summary": _calc_summary(records),
    })


@patient_report_api.route("/hrv/summary", methods=["GET"])
@auth_required
def hrv_summary():
    """
    GET /api/patient-report/hrv/summary
    Returns aggregated HRV statistics for the authenticated user.
    Used in conference evaluation tables (BME11).
    """
    import math as _math
    user = g.current_user
    limit = request.args.get("limit", default=500, type=int)
    limit = max(1, min(limit, 2000))

    records = (
        PatientHeartRateRecordModel.query
        .filter(
            PatientHeartRateRecordModel.user_id == user.id,
            PatientHeartRateRecordModel.hrv_rmssd.isnot(None),
        )
        .order_by(PatientHeartRateRecordModel.recorded_at.desc())
        .limit(limit)
        .all()
    )

    if not records:
        return jsonify({"status": "success", "hrv_summary": None,
                        "message": "No HRV data recorded yet."})

    rmssd_vals = [r.hrv_rmssd for r in records if r.hrv_rmssd is not None]
    sdnn_vals  = [r.hrv_sdnn  for r in records if r.hrv_sdnn  is not None]
    pnn50_vals = [r.hrv_pnn50 for r in records if r.hrv_pnn50 is not None]

    def _stats(vals):
        if not vals:
            return None
        n = len(vals)
        mean = sum(vals) / n
        sd = _math.sqrt(sum((v - mean) ** 2 for v in vals) / n)
        return {
            "mean":   round(mean, 2),
            "std":    round(sd, 2),
            "min":    round(min(vals), 2),
            "max":    round(max(vals), 2),
            "n":      n,
        }

    risk_counts = {"normal": 0, "low_hrv": 0, "very_low_hrv": 0}
    for r in records:
        key = (r.hrv_risk or "normal").lower()
        risk_counts[key] = risk_counts.get(key, 0) + 1

    low_hrv_rate = round(
        (risk_counts.get("low_hrv", 0) + risk_counts.get("very_low_hrv", 0))
        / len(records) * 100, 2
    ) if records else 0.0

    return jsonify({
        "status": "success",
        "hrv_summary": {
            "n_records":      len(records),
            "rmssd_ms":       _stats(rmssd_vals),
            "sdnn_ms":        _stats(sdnn_vals),
            "pnn50_pct":      _stats(pnn50_vals),
            "risk_distribution": risk_counts,
            "low_hrv_rate_pct": low_hrv_rate,
        },
    })


@patient_report_api.route("/hrv/live", methods=["GET"])
@auth_required
def hrv_live():
    """
    GET /api/patient-report/hrv/live
    Returns the current HRV from the in-memory sliding window analyzer.
    """
    try:
        from app.ai.services.heart_rate_ai import get_monitor
        monitor = get_monitor()
        if monitor is None:
            return jsonify({"status": "success", "hrv": None,
                            "message": "Monitor not initialised."})
        result = monitor.hrv_analyzer.compute()
        return jsonify({
            "status": "success",
            "hrv": result.to_dict() if result else None,
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@patient_report_api.route("/report.pdf", methods=["GET"])
@auth_required
def export_patient_report_pdf():
    user = g.current_user

    profile = PatientProfileModel.query.filter_by(user_id=user.id).first()
    if profile and profile.consent_pdf_export is False:
        return jsonify({"status": "error", "message": "User disabled PDF export consent"}), 403

    records = (
        PatientHeartRateRecordModel.query
        .filter_by(user_id=user.id)
        .order_by(PatientHeartRateRecordModel.recorded_at.desc())
        .limit(1000)
        .all()
    )
    summary  = _calc_summary(records)
    abnormal = [r for r in records if (r.severity or "").lower() in ("warning", "critical", "caution")]

    try:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos
    except Exception:
        return jsonify({"status": "error", "message": "PDF library not installed (fpdf2)"}), 500

    # ── helpers ──────────────────────────────────────────────
    import unicodedata

    def _s(text):
        """Sanitise to Helvetica-safe (Latin-1) characters."""
        if text is None:
            return ""
        nfkd = unicodedata.normalize("NFKD", str(text))
        return nfkd.encode("ascii", "ignore").decode("ascii").strip()

    GEN_TIME = datetime.now(timezone.utc)

    # palette
    C_DARK   = (10,  15,  35)
    C_GOLD   = (220, 160,  10)
    C_WHITE  = (255, 255, 255)
    C_LTGRAY = (245, 246, 248)
    C_MDGRAY = (160, 168, 185)
    C_TEXT   = ( 30,  35,  55)
    C_GREEN  = ( 20, 160,  90)
    C_ORANGE = (200, 110,  10)
    C_RED    = (190,  35,  50)

    p_name   = _s(profile.patient_name if profile and profile.patient_name else user.username) or "Unknown"
    bl_min   = float(profile.baseline_hr_min)  if profile and profile.baseline_hr_min  else 50.0
    bl_max   = float(profile.baseline_hr_max)  if profile and profile.baseline_hr_max  else 120.0
    bl_rest  = float(profile.baseline_hr_rest) if profile and profile.baseline_hr_rest else None

    # ── Alfred AI narrative ──────────────────────────────────
    def _alfred_narrative():
        cnt   = summary["count"]
        if cnt == 0:
            return (
                "Insufficient data for a complete cardiac assessment. No heart rate readings have been "
                "recorded in the monitoring system. Please ensure the Coospo H6 sensor is active and "
                "that the patient remains logged in during monitoring sessions."
            )
        avg   = summary["avg_bpm"]  or 0.0
        lo    = summary["min_bpm"]  or 0
        hi    = summary["max_bpm"]  or 0
        npct  = summary["normal_rate_percent"] or 0.0
        sev   = summary["severity_counts"]
        crit  = sev.get("critical", 0)
        warn  = sev.get("warning",  0)
        caut  = sev.get("caution",  0)

        in_range = bl_min <= avg <= bl_max
        if npct >= 90:
            status = "within stable and satisfactory parameters"
            prognosis = "Cardiovascular status appears well-controlled. Routine monitoring is sufficient."
        elif npct >= 70:
            status = "showing mild-to-moderate variability that warrants closer observation"
            prognosis = "Recommend increased monitoring frequency and a lifestyle assessment consultation."
        else:
            status = "demonstrating significant irregularity that warrants prompt medical review"
            prognosis = "I strongly advise scheduling a clinical consultation at the earliest opportunity."

        para1 = (
            f"Based on analysis of {cnt} recorded cardiac readings, the patient's heart rate is "
            f"{status}. The mean heart rate of {avg:.1f} BPM "
            f"{'aligns with' if in_range else 'falls outside'} the established personal baseline range "
            f"of {bl_min:.0f}-{bl_max:.0f} BPM"
        )
        if bl_rest:
            para1 += f" (documented resting baseline: {bl_rest:.0f} BPM)"
        para1 += (
            f". The recorded range spans {lo}-{hi} BPM over the observation period. "
            f"Normal readings account for {npct:.1f}% of all samples. {prognosis}"
        )

        paras = [para1]
        if crit > 0:
            paras.append(
                f"CRITICAL ALERT: {crit} critical cardiac event{'s were' if crit > 1 else ' was'} "
                f"logged, indicating heart rate exceeding emergency thresholds. If the patient experienced "
                f"accompanying symptoms such as palpitations, chest pain, dizziness, or loss of "
                f"consciousness, immediate medical evaluation is non-negotiable."
            )
        if warn + caut > 0:
            paras.append(
                f"A total of {warn + caut} cautionary event{'s were' if warn+caut > 1 else ' was'} "
                f"flagged. These episodes may correspond to physical exertion, postural changes, emotional "
                f"stress, or suboptimal medication timing. Correlation with the patient's activity log is "
                f"recommended."
            )
        if crit == 0 and warn == 0 and caut == 0:
            paras.append(
                "No abnormal cardiac events were detected during the monitored period. "
                "All readings remain within acceptable bounds — a commendable result."
            )
        return "\n\n".join(paras)

    def _recommendations():
        sev  = summary["severity_counts"]
        recs = []
        if sev.get("critical", 0) > 0:
            recs.append("URGENT: Schedule a cardiology consultation — critical cardiac events were recorded.")
            recs.append("Ensure emergency contacts are notified and the alert system remains active at all times.")
        if sev.get("warning", 0) > 0:
            recs.append("Review medication schedule and timing in relation to the recorded warning-level readings.")
            recs.append("Consider parallel blood-pressure monitoring to complement heart rate tracking.")
        if summary["max_bpm"] and summary["max_bpm"] > 120:
            recs.append("Investigate contributors to peak heart rate: physical exertion, anxiety, or caffeine intake.")
        if summary["min_bpm"] and summary["min_bpm"] < 50:
            recs.append("Low HR episodes detected. Evaluate for bradycardia in the context of current medications.")
        if not recs:
            recs.append("Maintain current monitoring schedule. No immediate clinical intervention appears necessary.")
            recs.append("Continue adequate hydration, regular mild exercise, and consistent sleep patterns.")
        recs.append("All data should be reviewed by the attending physician at the next scheduled appointment.")
        return recs

    # ── FPDF subclass ────────────────────────────────────────
    class AlfredPDF(FPDF):
        def header(self):
            self.set_fill_color(*C_DARK)
            self.rect(0, 0, 210, 24, "F")
            self.set_fill_color(*C_GOLD)
            self.rect(0, 24, 210, 1.5, "F")

            self.set_xy(14, 5)
            self.set_text_color(*C_GOLD)
            self.set_font("Helvetica", "B", 12)
            self.cell(120, 7, "ALFRED SMART HOME  |  ALFRED AI", new_x=XPos.RIGHT, new_y=YPos.TOP)

            self.set_xy(14, 13)
            self.set_text_color(*C_MDGRAY)
            self.set_font("Helvetica", "", 7.5)
            self.cell(120, 6, "Cardiac Health Monitoring Report  -  CONFIDENTIAL", new_x=XPos.RIGHT, new_y=YPos.TOP)

            self.set_xy(140, 6)
            self.set_text_color(*C_MDGRAY)
            self.set_font("Helvetica", "", 7.5)
            self.cell(55, 5, GEN_TIME.strftime("%Y-%m-%d  %H:%M UTC"), align="R", new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.set_xy(140, 13)
            self.cell(55, 5, f"Page {self.page_no()}", align="R", new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.ln(14)

        def footer(self):
            self.set_y(-16)
            self.set_fill_color(*C_DARK)
            self.rect(0, self.get_y() - 1, 210, 18, "F")
            self.set_text_color(90, 95, 115)
            self.set_font("Helvetica", "I", 6.5)
            self.cell(
                0, 8,
                "CONFIDENTIAL  |  Generated by Alfred AI - Alfred Smart Home v2.0  |  "
                "This report is for monitoring support only and does not constitute a clinical diagnosis.",
                align="C",
            )

    pdf = AlfredPDF()
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.add_page()
    pdf.set_margins(14, 14, 14)
    W = 182  # usable width

    def cell_right(width, height, text="", **kwargs):
        pdf.cell(width, height, text, new_x=XPos.RIGHT, new_y=YPos.TOP, **kwargs)

    def cell_next(width, height, text="", **kwargs):
        pdf.cell(width, height, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT, **kwargs)

    def sec_hdr(title):
        pdf.set_fill_color(*C_DARK)
        pdf.set_text_color(*C_GOLD)
        pdf.set_font("Helvetica", "B", 8.5)
        cell_next(W, 8, f"  {title}", fill=True)
        pdf.ln(2)

    def divider():
        pdf.set_draw_color(*C_GOLD)
        pdf.line(14, pdf.get_y(), 196, pdf.get_y())
        pdf.ln(4)

    # ════════════════════════════════════════════════════════
    # 01  PATIENT IDENTIFICATION
    # ════════════════════════════════════════════════════════
    sec_hdr("01  PATIENT IDENTIFICATION")

    age_str    = str(profile.age)    if profile and profile.age    else "N/A"
    gender_str = _s(profile.gender).title() if profile and profile.gender else "N/A"

    id_fields = [
        ("Patient Name", p_name),       ("System User",   _s(user.username)),
        ("Age",          age_str),       ("User ID",       f"UID-{user.id:04d}"),
        ("Gender",       gender_str),    ("Report Date",   GEN_TIME.strftime("%d %B %Y  %H:%M UTC")),
    ]
    col = W / 2
    for i, (label, value) in enumerate(id_fields):
        x = 14 + (col if i % 2 == 1 else 0)
        if i % 2 == 0:
            row_y = pdf.get_y()
        pdf.set_xy(x, row_y)
        pdf.set_fill_color(*C_LTGRAY)
        pdf.set_text_color(*C_MDGRAY)
        pdf.set_font("Helvetica", "", 6.5)
        cell_right(col - 2, 5, label.upper(), fill=True)
        pdf.set_xy(x, row_y + 5)
        pdf.set_text_color(*C_TEXT)
        pdf.set_font("Helvetica", "B", 10)
        cell_right(col - 2, 7, value)
        if i % 2 == 1:
            pdf.ln(14)

    pdf.ln(3)
    divider()

    # ════════════════════════════════════════════════════════
    # 02  ALFRED AI EXECUTIVE SUMMARY
    # ════════════════════════════════════════════════════════
    sec_hdr("02  ALFRED AI EXECUTIVE SUMMARY")
    narrative = _alfred_narrative()
    pdf.set_text_color(*C_TEXT)
    for para in narrative.split("\n\n"):
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(W, 5.5, _s(para).strip())
        pdf.ln(2)
    pdf.ln(1)
    divider()

    # ════════════════════════════════════════════════════════
    # 03  VITAL STATISTICS
    # ════════════════════════════════════════════════════════
    sec_hdr("03  HEART RATE VITAL STATISTICS")

    stats = [
        ("Total Readings",    str(summary["count"]),                                    C_TEXT),
        ("Average BPM",       f"{summary['avg_bpm']:.1f}" if summary["avg_bpm"] else "--", C_TEXT),
        ("Minimum BPM",       str(summary["min_bpm"] or "--"),                          C_GREEN),
        ("Maximum BPM",       str(summary["max_bpm"] or "--"),                          C_RED),
        ("Normal Rate",       f"{summary['normal_rate_percent'] or 0:.1f}%",            C_GREEN),
        ("Abnormal Events",   str(len(abnormal)),                                       C_RED if abnormal else C_GREEN),
    ]
    cw = W / 3
    for i, (label, value, color) in enumerate(stats):
        x = 14 + (i % 3) * cw
        if i % 3 == 0:
            stat_y = pdf.get_y()
        pdf.set_xy(x, stat_y)
        pdf.set_fill_color(238, 240, 245)
        pdf.rect(x, stat_y, cw - 3, 17, "F")
        pdf.set_xy(x + 3, stat_y + 2)
        pdf.set_text_color(*C_MDGRAY)
        pdf.set_font("Helvetica", "", 6.5)
        cell_right(cw - 6, 4, label.upper())
        pdf.set_xy(x + 3, stat_y + 7)
        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "B", 15)
        cell_right(cw - 6, 9, value)
        if i % 3 == 2 or i == len(stats) - 1:
            pdf.ln(20)

    pdf.ln(1)

    # Severity bar chart
    sev_total = max(summary["count"], 1)
    sev_items = [
        ("NORMAL",   summary["severity_counts"].get("normal",   0), C_GREEN),
        ("CAUTION",  summary["severity_counts"].get("caution",  0), (200, 170, 10)),
        ("WARNING",  summary["severity_counts"].get("warning",  0), C_ORANGE),
        ("CRITICAL", summary["severity_counts"].get("critical", 0), C_RED),
    ]
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(*C_TEXT)
    cell_next(W, 5, "Severity Distribution")
    bar_y      = pdf.get_y()
    bar_max_w  = W - 62
    for j, (lbl, cnt, clr) in enumerate(sev_items):
        by = bar_y + j * 10
        pdf.set_xy(14, by)
        pdf.set_text_color(*C_TEXT)
        pdf.set_font("Helvetica", "", 7.5)
        cell_right(30, 8, lbl)
        # background bar
        pdf.set_fill_color(225, 227, 232)
        pdf.rect(46, by + 1.5, bar_max_w, 5, "F")
        # value bar
        bw = max(2, int((cnt / sev_total) * bar_max_w))
        pdf.set_fill_color(*clr)
        pdf.rect(46, by + 1.5, bw, 5, "F")
        # count
        pdf.set_xy(46 + bar_max_w + 4, by)
        pdf.set_text_color(*clr)
        pdf.set_font("Helvetica", "B", 7.5)
        cell_right(12, 8, str(cnt))
        # percentage
        pct = cnt / sev_total * 100
        pdf.set_text_color(*C_MDGRAY)
        pdf.set_font("Helvetica", "", 6.5)
        pdf.set_xy(46 + bar_max_w + 16, by + 1)
        cell_right(16, 8, f"({pct:.0f}%)")

    pdf.ln(len(sev_items) * 10 + 5)
    divider()

    # ════════════════════════════════════════════════════════
    # 04  ABNORMAL EVENTS TIMELINE
    # ════════════════════════════════════════════════════════
    sec_hdr("04  ABNORMAL EVENTS TIMELINE")

    if not abnormal:
        pdf.set_text_color(*C_GREEN)
        pdf.set_font("Helvetica", "B", 9)
        cell_next(W, 8, "  No abnormal events detected during the monitored period.")
    else:
        c1, c2, c3, c4 = 50, 20, 28, W - 50 - 20 - 28

        def _evt_hdr():
            pdf.set_fill_color(*C_DARK)
            pdf.set_text_color(*C_GOLD)
            pdf.set_font("Helvetica", "B", 7)
            cell_right(c1, 6, "  TIMESTAMP", fill=True)
            cell_right(c2, 6, "BPM", fill=True, align="C")
            cell_right(c3, 6, "SEVERITY", fill=True, align="C")
            cell_next(c4, 6, "RISK  /  MOOD", fill=True)

        _evt_hdr()
        sorted_abn = sorted(abnormal, key=lambda r: r.recorded_at or datetime.min, reverse=True)
        for idx, r in enumerate(sorted_abn[:60]):
            ts      = r.recorded_at.strftime("%Y-%m-%d  %H:%M:%S") if r.recorded_at else "-"
            sev_str = (r.severity or "").upper()
            risk_str= _s(r.risk  or "").replace("_", " ").title()
            mood_str= _s(r.mood  or "-")
            detail  = f"{risk_str[:20]}  /  {mood_str[:20]}"

            if sev_str == "CRITICAL":
                txt_c = C_RED;    bg_c = (255, 234, 237)
            elif sev_str == "WARNING":
                txt_c = C_ORANGE; bg_c = (255, 248, 225)
            else:
                txt_c = (140, 100, 0); bg_c = (255, 253, 235)

            fill_c = bg_c if idx % 2 == 0 else C_LTGRAY
            pdf.set_fill_color(*fill_c)
            pdf.set_text_color(*C_TEXT)
            pdf.set_font("Helvetica", "", 7.5)
            cell_right(c1, 6, f"  {ts}", fill=True)
            pdf.set_text_color(*txt_c)
            pdf.set_font("Helvetica", "B", 7.5)
            cell_right(c2, 6, str(r.bpm), fill=True, align="C")
            cell_right(c3, 6, sev_str, fill=True, align="C")
            pdf.set_text_color(*C_TEXT)
            pdf.set_font("Helvetica", "", 7)
            cell_next(c4, 6, detail, fill=True)
            if (idx + 1) % 32 == 0:
                pdf.add_page()
                _evt_hdr()

    pdf.ln(3)
    divider()

    # ════════════════════════════════════════════════════════
    # 05  CLINICAL PROFILE
    # ════════════════════════════════════════════════════════
    sec_hdr("05  CLINICAL PROFILE &amp; MEDICATION LOG")

    if not profile:
        pdf.set_text_color(*C_MDGRAY)
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(W, 8,
                 "  No clinical profile on record. Complete the patient profile in the dashboard.",
                 new_x="LMARGIN", new_y="NEXT")
    else:
        cl_fields = [
            ("Resting Baseline HR",  f"{profile.baseline_hr_rest or 'N/A'} BPM"),
            ("Safe HR Range",        f"{profile.baseline_hr_min or 'N/A'} - {profile.baseline_hr_max or 'N/A'} BPM"),
            ("Age",                  f"{profile.age or 'N/A'} years"),
            ("Gender",               _s(profile.gender or "N/A").title()),
        ]
        cw2 = W / 2
        for i, (lbl, val) in enumerate(cl_fields):
            x = 14 + (cw2 if i % 2 == 1 else 0)
            if i % 2 == 0:
                cl_y = pdf.get_y()
            pdf.set_xy(x, cl_y)
            pdf.set_text_color(*C_MDGRAY)
            pdf.set_font("Helvetica", "", 6.5)
            cell_right(cw2 - 2, 5, lbl.upper())
            pdf.set_xy(x, cl_y + 5)
            pdf.set_text_color(*C_TEXT)
            pdf.set_font("Helvetica", "B", 9.5)
            cell_right(cw2 - 2, 7, _s(val))
            if i % 2 == 1:
                pdf.ln(14)
        pdf.ln(3)

        if profile.diagnosis_notes:
            pdf.set_text_color(*C_MDGRAY)
            pdf.set_font("Helvetica", "B", 7)
            cell_next(W, 5, "DIAGNOSIS &amp; CLINICAL NOTES")
            pdf.set_text_color(*C_TEXT)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.multi_cell(W, 5.5, _s(profile.diagnosis_notes))
            pdf.ln(3)

        if profile.medications:
            pdf.set_text_color(*C_MDGRAY)
            pdf.set_font("Helvetica", "B", 7)
            cell_next(W, 5, "CURRENT MEDICATIONS")
            pdf.set_text_color(*C_TEXT)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.multi_cell(W, 5.5, _s(profile.medications))
            pdf.ln(3)

    divider()

    # ════════════════════════════════════════════════════════
    # 06  ALFRED AI RECOMMENDATIONS
    # ════════════════════════════════════════════════════════
    sec_hdr("06  ALFRED AI RECOMMENDATIONS")
    for rec in _recommendations():
        bullet_y = pdf.get_y() + 2.5
        pdf.set_fill_color(*C_GOLD)
        pdf.rect(14, bullet_y, 3, 3, "F")
        pdf.set_xy(20, pdf.get_y())
        pdf.set_text_color(*C_TEXT)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(W - 6, 5.5, _s(rec))
        pdf.ln(1)

    pdf.ln(3)

    # ════════════════════════════════════════════════════════
    # 07  FULL SESSION LOG  (new page)
    # ════════════════════════════════════════════════════════
    pdf.add_page()
    sec_hdr(f"07  FULL SESSION LOG  (latest {min(len(records), 100)} of {len(records)} readings)")

    d1, d2, d3, d4 = 50, 18, 26, W - 50 - 18 - 26
    pdf.set_fill_color(*C_DARK)
    pdf.set_text_color(*C_GOLD)
    pdf.set_font("Helvetica", "B", 7)
    cell_right(d1, 6, "  TIMESTAMP", fill=True)
    cell_right(d2, 6, "BPM", fill=True, align="C")
    cell_right(d3, 6, "SEVERITY", fill=True, align="C")
    cell_next(d4, 6, "SOURCE", fill=True)

    for idx, r in enumerate(records[:100]):
        ts      = r.recorded_at.strftime("%Y-%m-%d  %H:%M:%S") if r.recorded_at else "-"
        sev_str = (r.severity or "normal").upper()
        src_str = _s(r.source or "-")

        if sev_str == "CRITICAL":
            txt_c = C_RED
        elif sev_str in ("WARNING", "CAUTION"):
            txt_c = C_ORANGE
        else:
            txt_c = C_TEXT

        fill_c = C_LTGRAY if idx % 2 == 0 else C_WHITE
        pdf.set_fill_color(*fill_c)
        pdf.set_text_color(*C_TEXT)
        pdf.set_font("Helvetica", "", 7)
        cell_right(d1, 5.5, f"  {ts}", fill=True)
        pdf.set_text_color(*txt_c)
        pdf.set_font("Helvetica", "B" if sev_str != "NORMAL" else "", 7)
        cell_right(d2, 5.5, str(r.bpm), fill=True, align="C")
        cell_right(d3, 5.5, sev_str, fill=True, align="C")
        pdf.set_text_color(*C_TEXT)
        pdf.set_font("Helvetica", "", 7)
        cell_next(d4, 5.5, src_str, fill=True)

    # sign-off
    pdf.ln(8)
    pdf.set_draw_color(*C_GOLD)
    pdf.line(14, pdf.get_y(), 90, pdf.get_y())
    pdf.ln(4)
    pdf.set_text_color(*C_TEXT)
    pdf.set_font("Helvetica", "B", 9)
    cell_next(W, 5, "Alfred  -  Your AI Health Guardian")
    pdf.set_text_color(*C_MDGRAY)
    pdf.set_font("Helvetica", "I", 8)
    cell_next(W, 5, f"Alfred Smart Home - Elderly Care Monitoring System  |  {GEN_TIME.strftime('%d %B %Y')}")

    # ── render ──────────────────────────────────────────────
    raw = pdf.output()
    pdf_bytes = raw.encode("latin-1") if isinstance(raw, str) else bytes(raw)

    safe_name = p_name.replace(" ", "_")[:30]
    filename  = f"alfred_report_{safe_name}_{GEN_TIME.strftime('%Y%m%d')}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@patient_report_api.route("/report/email", methods=["POST"])
@auth_required
def email_patient_report_pdf():
    notifier = container.email_notifier()
    payload = request.get_json(silent=True) or {}
    recipients = notifier.resolve_recipients(
        user_email=g.current_user.email,
        extra=payload.get("recipients", payload.get("email")),
    )

    report_response = export_patient_report_pdf.__wrapped__()
    if not isinstance(report_response, Response):
        return report_response

    pdf_bytes = report_response.get_data()
    filename = _extract_filename(report_response.headers.get("Content-Disposition"))
    subject = f"Patient Report: {g.current_user.username}"
    body = (
        f"Attached is the latest Alfred AI cardiac monitoring report for {g.current_user.username}.\n"
        f"Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"Recipients: {', '.join(recipients)}\n"
    )
    delivery = notifier.send_message(
        subject=subject,
        body=body,
        recipients=recipients,
        attachments=[
            {
                "filename": filename,
                "content": pdf_bytes,
                "mimetype": "application/pdf",
            }
        ],
    )

    if not delivery.get("sent"):
        reason = delivery.get("reason")
        status_code = 400 if reason == "no-recipients" else 503 if reason == "email-not-configured" else 502
        return jsonify({
            "status": "error",
            "message": "Failed to send patient report email",
            "filename": filename,
            "delivery": {"sent": False},
        }), status_code

    return jsonify({
        "status": "success",
        "message": "Patient report email sent successfully",
        "filename": filename,
        "delivery": {"sent": True, "recipients": recipients},
    })
