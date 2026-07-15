"""
This is the deterministic pool which inputs the Report from the Firefighter and just retrieves the 
data that is asked of it from that firefighter's corresponding pool. It does nothing more!
"""
import aiosqlite
from models import Report
from typing import Any
from datetime import datetime

DB1_PATH = 'data/vitals.db'
DB2_PATH = 'data/vitals2.db'
DB3_PATH = 'data/vitals3.db'

FF_DB = {1: DB1_PATH, 2: DB2_PATH, 3: DB3_PATH}

# The CSV pools for each of the data types
FILES = {
    "ALL_LOG": '*',
    "ELEVATION": 'elevation',
    "HR":'hr',
    "O2": 'o2',
    "TEMP" :'temp'
}

async def get_data(report: Report, ff: int) -> dict[str, list[Any]]:
    """
    Parses the report and returns a dictionary with the type of data as the key to a list of the chunks.
    """
    result = {}

    # Convert the time into a text
    start_time = report.time.isoformat() if isinstance(report.time, datetime) else str(report.time)
    
    # Read the list of data needed!
    DB_PATH = FF_DB[ff]
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
                raise ValueError (f"no dataset with such name! augh: {re}")
                continue
            
            da = FILES[re]
            if da == "*":
                select_columns = "*"
                null_check_clause = "" # Can't do * IS NOT NULL safely
            else:
                # If 'time' is missing from your config, append it safely
                select_columns = da if "time" in da else f"{da}, time"
                null_check_clause = f"AND {da} IS NOT NULL"

            query = f"""
                WITH OrderedLogs AS (
                    SELECT {select_columns},
                           ROW_NUMBER() OVER (ORDER BY time ASC) as row_num
                    FROM all_logs
                    WHERE time >= ? {null_check_clause}
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

