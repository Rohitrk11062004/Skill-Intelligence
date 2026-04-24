"""One-off read-only report of persisted learning paths (run from backend/)."""
import asyncio

from sqlalchemy import text

from app.db.session import engine


async def main() -> None:
    async with engine.connect() as conn:
        n = (await conn.execute(text("SELECT COUNT(*) FROM learning_plans"))).scalar()
        print("learning_plans count:", n)
        if not n:
            print("No learning plans in database.")
            return

        rows = (
            await conn.execute(
                text(
                    """
 SELECT id, user_id, role_id, total_hours_estimate, status, created_at, updated_at
            FROM learning_plans
            ORDER BY updated_at DESC
            LIMIT 3
        """
                )
            )
        ).fetchall()
        print("\nLatest plans (up to 3):")
        for r in rows:
            print(dict(r._mapping))

        plan_id = rows[0].id
        items = (
            await conn.execute(
                text(
                    """
            SELECT id, "order", skill_id, title, resource_type, skill_band,
                   estimated_hours, status,
                   LENGTH(COALESCE(subtopics_json, '')) AS subtopics_json_len
            FROM learning_plan_items
            WHERE plan_id = :pid
            ORDER BY "order"
            LIMIT 25
        """
                ),
                {"pid": plan_id},
            )
        ).fetchall()
        print("\nItems for most recently updated plan (first 25 rows):")
        for r in items:
            print(dict(r._mapping))

        cnt = (
            await conn.execute(
                text("SELECT COUNT(*) FROM learning_plan_items WHERE plan_id = :pid"),
                {"pid": plan_id},
            )
        ).scalar()
        print("\nTotal items in that plan:", cnt)

        st = (
            await conn.execute(
                text(
                    """
            SELECT COUNT(*) FROM learning_plan_item_subtopics st
            JOIN learning_plan_items i ON i.id = st.item_id
            WHERE i.plan_id = :pid
        """
                ),
                {"pid": plan_id},
            )
        ).scalar()
        ss = (
            await conn.execute(
                text(
                    """
            SELECT COUNT(*) FROM learning_plan_item_sub_subtopics sss
            JOIN learning_plan_item_subtopics st ON st.id = sss.subtopic_id
            JOIN learning_plan_items i ON i.id = st.item_id
            WHERE i.plan_id = :pid
        """
                ),
                {"pid": plan_id},
            )
        ).scalar()
        res = (
            await conn.execute(
                text(
                    """
            SELECT COUNT(*) FROM learning_plan_item_resources r
            JOIN learning_plan_items i ON i.id = r.item_id
            WHERE i.plan_id = :pid
        """
                ),
                {"pid": plan_id},
            )
        ).scalar()
        print("Normalized subtopics:", st, "| sub-subtopics:", ss, "| resources:", res)

        sample_res = (
            await conn.execute(
                text(
                    """
            SELECT r.title, r.provider, LEFT(r.url, 80) AS url_preview, r.resource_type
            FROM learning_plan_item_resources r
            JOIN learning_plan_items i ON i.id = r.item_id
            WHERE i.plan_id = :pid
            ORDER BY i."order", r.rank
            LIMIT 6
        """
                ),
                {"pid": plan_id},
            )
        ).fetchall()
        print("\nSample resources (up to 6):")
        for r in sample_res:
            print(dict(r._mapping))

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
