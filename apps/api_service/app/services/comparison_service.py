from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select

from apps.api_service.app.db import models
from packages.shared_py.car_inspection.enums import ComparisonStatus, ReviewStatus, AdminCaseStatus, REQUIRED_SLOTS
from apps.api_service.app.domain.comparisons import bbox_iou, centroid_distance_normalized, area_similarity, match_score

DIFF_VERSION = "v1"
HIGH_CONF_NEW_SOURCE_TYPES = {"manual", "predicted_confirmed", "predicted_auto_high"}
LOW_CONF_NEW_SOURCE_TYPES = {"predicted_auto_low", "predicted_uncertain"}

def build_final_state(db: Session, inspection_session_id):
    finals = db.execute(
        select(models.InspectionDamageFinal).where(models.InspectionDamageFinal.inspection_session_id == inspection_session_id)
    ).scalars().all()
    by_slot = {}
    for item in finals:
        by_slot.setdefault(item.view_slot, []).append(item)
    return by_slot

def ensure_admin_case(db: Session, comparison: models.InspectionComparison, vehicle_id, summary: str):
    existing = db.execute(
        select(models.AdminCase).where(models.AdminCase.comparison_id == comparison.id)
    ).scalar_one_or_none()
    if existing:
        return existing
    case = models.AdminCase(
        comparison_id=comparison.id,
        vehicle_id=vehicle_id,
        status=AdminCaseStatus.OPEN.value,
        title="Likely new vehicle damage requires review",
        summary=summary,
        opened_at=datetime.now(timezone.utc),
    )
    db.add(case)
    db.flush()
    return case

def run_post_trip_comparison(db: Session, post_session: models.InspectionSession):
    if not post_session.linked_pre_trip_session_id:
        post_session.comparison_status = ComparisonStatus.NO_REFERENCE_BASELINE.value
        db.flush()
        return None

    pre_session = db.get(models.InspectionSession, post_session.linked_pre_trip_session_id)
    pre_by_slot = build_final_state(db, pre_session.id)
    post_by_slot = build_final_state(db, post_session.id)

    comparison = db.execute(
        select(models.InspectionComparison).where(
            models.InspectionComparison.pre_session_id == pre_session.id,
            models.InspectionComparison.post_session_id == post_session.id,
            models.InspectionComparison.diff_version == DIFF_VERSION,
        )
    ).scalar_one_or_none()

    if not comparison:
        comparison = models.InspectionComparison(
            pre_session_id=pre_session.id,
            post_session_id=post_session.id,
            diff_version=DIFF_VERSION,
            status=ComparisonStatus.NOT_RUN.value,
            summary_json={},
        )
        db.add(comparison)
        db.flush()

    # remove prior matches for reruns
    for old in db.execute(select(models.DamageMatch).where(models.DamageMatch.comparison_id == comparison.id)).scalars().all():
        db.delete(old)
    db.flush()

    matched_count = 0
    possible_new_count = 0
    new_confirmed_count = 0
    requires_admin_review = False
    details = []

    for slot in REQUIRED_SLOTS:
        pre_items = pre_by_slot.get(slot, [])
        post_items = post_by_slot.get(slot, [])

        for post in post_items:
            best = None
            best_score = -1.0
            best_metrics = None
            for pre in pre_items:
                if pre.damage_type != post.damage_type:
                    continue
                iou = bbox_iou(pre.bbox_norm, post.bbox_norm)
                cdist = centroid_distance_normalized((pre.centroid_x, pre.centroid_y), (post.centroid_x, post.centroid_y))
                asim = area_similarity(pre.area_norm, post.area_norm)
                score = match_score(iou, cdist, asim)
                if score > best_score:
                    best = pre
                    best_score = score
                    best_metrics = (iou, cdist, asim)

            status = "possible_new"
            pre_damage_id = None
            is_new_candidate = False
            if best and best_score >= 0.65:
                status = "matched_existing"
                pre_damage_id = best.id
                matched_count += 1
            elif best and best_score >= 0.45:
                status = "possible_match"
                pre_damage_id = best.id
                requires_admin_review = True
            else:
                is_new_candidate = True

            if is_new_candidate:
                if post.source_type in HIGH_CONF_NEW_SOURCE_TYPES:
                    status = "new_confirmed"
                    new_confirmed_count += 1
                    requires_admin_review = True
                elif post.source_type in LOW_CONF_NEW_SOURCE_TYPES:
                    status = "possible_new"
                    possible_new_count += 1
                    requires_admin_review = True
                else:
                    status = "possible_new"
                    possible_new_count += 1
                    requires_admin_review = True

            if status in {"possible_match", "new_confirmed"}:
                requires_admin_review = True

            match = models.DamageMatch(
                comparison_id=comparison.id,
                view_slot=slot,
                pre_damage_id=pre_damage_id,
                post_damage_id=post.id,
                status=status,
                match_score=max(best_score, 0.0),
                iou_norm=best_metrics[0] if best_metrics else None,
                centroid_distance_norm=best_metrics[1] if best_metrics else None,
                area_similarity=best_metrics[2] if best_metrics else None,
                evidence_json={"slot": slot},
            )
            db.add(match)
            details.append({
                "view_slot": slot,
                "post_damage_id": str(post.id),
                "pre_damage_id": str(pre_damage_id) if pre_damage_id else None,
                "status": status,
                "match_score": round(max(best_score, 0.0), 4),
            })

    comparison.matched_count = matched_count
    comparison.possible_new_count = possible_new_count
    comparison.new_confirmed_count = new_confirmed_count
    comparison.requires_admin_review = requires_admin_review
    comparison.summary_json = {
        "matched_count": matched_count,
        "possible_new_count": possible_new_count,
        "new_confirmed_count": new_confirmed_count,
        "details": details,
    }
    comparison.status = (
        ComparisonStatus.ADMIN_CASE_CREATED.value if requires_admin_review
        else ComparisonStatus.NO_NEW_DAMAGE.value
    )

    if requires_admin_review:
        ensure_admin_case(
            db,
            comparison,
            post_session.vehicle_id,
            f"{new_confirmed_count} confirmed new damage(s), {possible_new_count} possible new damage(s).",
        )
        post_session.comparison_status = ComparisonStatus.ADMIN_CASE_CREATED.value
    else:
        post_session.comparison_status = ComparisonStatus.NO_NEW_DAMAGE.value

    db.flush()
    return comparison
