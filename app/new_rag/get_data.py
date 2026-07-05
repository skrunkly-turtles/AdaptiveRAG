"""
This is the deterministic pool which inputs the Report from the Firefighter and just retrieves the 
data that is asked of it. It does nothing more!
"""
import aiosqlite
from models import Report
from typing import Any
from datetime import datetime

DB_PATH = 'vitals.db'

# The CSV pools for each of the data types
FILES = {
    "ALL_LOG": '*',
    "ELEVATION": 'elevation',
    "HR":'hr',
    "O2_LOG": 'o2',
    "TEMP" :'temp'
}

async def get_data(report: Report) -> dict[str, list[Any]]:
    """
    Parses the report and returns a dictionary with the type of data as the key to a list of the chunks.
    """
    result = {}

    # Convert the time into a text
    start_time = report.time.isoformat() if isinstance(report.time, datetime) else str(report.time)
    
    # Read the list of data needed!
    async with aiosqlite.connect(DB_PATH) as db:
        for re in report.data:
            if re == "SUMMARIES":
                async with db.execute("SELECT metric, num, avg, min, max, med FROM summaries") as cursor:
                    rows = await cursor.fetchall()
                    result[re] = [{"metric": r[0], "num": r[1], "avg": r[2], "min": r[3], "max": r[4], "med": r[5]}
                        for r in rows
                    ]
                continue
            if re not in FILES:
                raise ValueError (f"no dataset with such name! augh")
                continue
            
            da = FILES[re]
            d = "*" if da =="*" else f"{d}, time"
            query = f"""
                WITH OrderedLogs AS (
                    SELECT {d}, time,
                           ROW_NUMBER() OVER (ORDER BY time ASC) as row_num
                    FROM all_logs
                    WHERE time >= ? AND {d} IS NOT NULL
                )
                SELECT * FROM OrderedLogs
                WHERE (row_num - 1) % ? = 0
                LIMIT ?
            """
            async with db.execute(query, (start_time, report.resolution, report.chunks)) as cursor:
                rows = await cursor.fetchall()
                if re == "ALL_LOG":
                    head = [desc[0] for desc in cursor.description]
                    result[re] = [
                        {head[i]: row[i] for i in range(len(head)) if head[i] != 'row_num'}
                        for row in rows
                    ]
                else:
                    result[re] = [row[0] for row in rows]
        return result 


