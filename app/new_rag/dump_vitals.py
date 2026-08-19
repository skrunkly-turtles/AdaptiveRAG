"""
This just makes it so i can read all the files yay
"""
import asyncio
import aiosqlite
from pathlib import Path
from pool_maker import FF_DB

OUTPUT_PATH = Path(__file__).parent / "vitals_report.md"
METRICS = ("hr", "o2", "elevation", "temp", "respiration", "hrv", "body_temp", "gait")


async def dump_one_ff(ff: int, path: str) -> str:
    lines = [f"## Firefighter {ff}", ""]

    if not Path(path).exists():
        lines.append("_(no database yet)_\n")
        return "\n".join(lines)

    async with aiosqlite.connect(path) as db:
        # Latest reading
        async with db.execute(
            "SELECT time, hr, o2, elevation, temp, respiration, hrv, body_temp, gait "
            "FROM all_logs ORDER BY time DESC LIMIT 1"
        ) as cursor:
            latest = await cursor.fetchall()

        if latest:
            lines.append(f"full reading! ({len(latest)} readings:")
            lines.append("")
            lines.append("| hr | o2 | elevation | temp | respiration | hrv | body_temp | gait |")
            lines.append("|---|---|---|---|---|---|---|---|")
            for row in latest:
                lines.append("| " + " |".join(str(v) for v in row) + " |")
            lines.append("")
        else:
            lines.append("_(no readings logged yet)_")
            lines.append("")

        # Summary stats table
        async with db.execute("SELECT metric, num, avg, min, max, med FROM summaries") as cursor:
            rows = await cursor.fetchall()

        if rows:
            lines.append("**Summary stats:**")
            lines.append("")
            lines.append("| metric | count | avg | min | max | median |")
            lines.append("|---|---|---|---|---|---|")
            for metric, num, avg, mn, mx, med in rows:
                lines.append(f"| {metric} | {num} | {avg} | {mn} | {mx} | {med} |")
            lines.append("")

    return "\n".join(lines)


async def main():
    sections = []
    for ff, path in FF_DB.items():
        sections.append(await dump_one_ff(ff, path))

    report = "# Vitals Report\n\n" + "\n".join(sections)
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())