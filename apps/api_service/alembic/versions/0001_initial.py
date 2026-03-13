"""initial — create all tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), unique=True, index=True, nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="customer", index=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "vehicles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_vehicle_id", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("license_plate", sa.String(32), unique=True, nullable=True),
        sa.Column("make", sa.String(100), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("model_year", sa.Integer(), nullable=True),
        sa.Column("color", sa.String(50), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true", index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "inspection_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), index=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), index=True, nullable=False),
        sa.Column("inspection_type", sa.String(50), nullable=False, server_default="pre_trip"),
        sa.Column("status", sa.String(50), nullable=False, server_default="created"),
        sa.Column("linked_pre_trip_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_sessions.id"), nullable=True),
        sa.Column("required_slots", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("accepted_slots", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finalized_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("comparison_status", sa.String(50), nullable=False, server_default="not_run"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "inspection_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("inspection_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_sessions.id"), index=True, nullable=False),
        sa.Column("image_type", sa.String(50), nullable=False, server_default="required_view", index=True),
        sa.Column("slot_code", sa.String(50), nullable=True, index=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="uploaded"),
        sa.Column("capture_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("object_key_raw", sa.Text(), nullable=False),
        sa.Column("object_key_processed", sa.Text(), nullable=True),
        sa.Column("object_key_thumbnail", sa.Text(), nullable=True),
        sa.Column("overlay_object_key", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("phash", sa.String(64), nullable=True),
        sa.Column("car_present", sa.Boolean(), nullable=True),
        sa.Column("car_confidence", sa.Float(), nullable=True),
        sa.Column("car_bbox", postgresql.JSONB(), nullable=True),
        sa.Column("quality_label", sa.String(64), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("view_label", sa.String(64), nullable=True),
        sa.Column("view_score", sa.Float(), nullable=True),
        sa.Column("accepted", sa.Boolean(), nullable=True),
        sa.Column("rejection_reason", sa.String(128), nullable=True),
        sa.Column("duplicate_of_image_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_images.id"), nullable=True),
        sa.Column("parent_damage_review_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_manual_damage_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pipeline_version", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "predicted_damages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("inspection_image_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_images.id"), index=True, nullable=False),
        sa.Column("damage_type", sa.String(50), nullable=False, server_default="scratch", index=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("bbox_norm", postgresql.JSONB(), nullable=False),
        sa.Column("centroid_x", sa.Float(), nullable=False),
        sa.Column("centroid_y", sa.Float(), nullable=False),
        sa.Column("area_norm", sa.Float(), nullable=False),
        sa.Column("mask_rle", postgresql.JSONB(), nullable=True),
        sa.Column("polygon_json", postgresql.JSONB(), nullable=True),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("model_version", sa.String(128), nullable=False),
        sa.Column("inference_run_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "damage_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("predicted_damage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("predicted_damages.id"), unique=True, nullable=False),
        sa.Column("inspection_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_sessions.id"), index=True, nullable=False),
        sa.Column("review_status", sa.String(50), nullable=False, server_default="pending", index=True),
        sa.Column("severity_hint", sa.String(32), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "manual_damages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("inspection_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_sessions.id"), index=True, nullable=False),
        sa.Column("base_image_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_images.id"), index=True, nullable=False),
        sa.Column("damage_type", sa.String(50), nullable=False, server_default="scratch"),
        sa.Column("bbox_norm", postgresql.JSONB(), nullable=False),
        sa.Column("centroid_x", sa.Float(), nullable=False),
        sa.Column("centroid_y", sa.Float(), nullable=False),
        sa.Column("area_norm", sa.Float(), nullable=False),
        sa.Column("polygon_json", postgresql.JSONB(), nullable=True),
        sa.Column("severity_hint", sa.String(32), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "inspection_damages_final",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("inspection_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_sessions.id"), index=True, nullable=False),
        sa.Column("view_slot", sa.String(50), nullable=False, index=True),
        sa.Column("base_image_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_images.id"), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_predicted_damage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("predicted_damages.id"), nullable=True),
        sa.Column("source_manual_damage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("manual_damages.id"), nullable=True),
        sa.Column("damage_type", sa.String(50), nullable=False, index=True),
        sa.Column("bbox_norm", postgresql.JSONB(), nullable=False),
        sa.Column("centroid_x", sa.Float(), nullable=False),
        sa.Column("centroid_y", sa.Float(), nullable=False),
        sa.Column("area_norm", sa.Float(), nullable=False),
        sa.Column("polygon_json", postgresql.JSONB(), nullable=True),
        sa.Column("severity_hint", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "inspection_comparisons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pre_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_sessions.id"), nullable=False),
        sa.Column("post_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_sessions.id"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="not_run"),
        sa.Column("diff_version", sa.String(64), nullable=False, server_default="v1"),
        sa.Column("summary_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("possible_new_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_confirmed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requires_admin_review", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("pre_session_id", "post_session_id", "diff_version"),
    )

    op.create_table(
        "damage_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("comparison_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_comparisons.id"), index=True, nullable=False),
        sa.Column("view_slot", sa.String(50), nullable=False, index=True),
        sa.Column("pre_damage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_damages_final.id"), nullable=True),
        sa.Column("post_damage_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_damages_final.id"), nullable=True),
        sa.Column("status", sa.String(64), nullable=False, index=True),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("iou_norm", sa.Float(), nullable=True),
        sa.Column("centroid_distance_norm", sa.Float(), nullable=True),
        sa.Column("area_similarity", sa.Float(), nullable=True),
        sa.Column("evidence_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "admin_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("comparison_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inspection_comparisons.id"), unique=True, nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), index=True, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="open", index=True),
        sa.Column("priority", sa.String(32), nullable=False, server_default="medium"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_note", sa.Text(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("admin_cases")
    op.drop_table("damage_matches")
    op.drop_table("inspection_comparisons")
    op.drop_table("inspection_damages_final")
    op.drop_table("manual_damages")
    op.drop_table("damage_reviews")
    op.drop_table("predicted_damages")
    op.drop_table("inspection_images")
    op.drop_table("inspection_sessions")
    op.drop_table("vehicles")
    op.drop_table("users")
