import io
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import mplcyberpunk
import aiomysql
import pandas as pd
from datetime import datetime
from backend import get_db_creds


async def activity_server(start_date: datetime.date, end_date: datetime.date, timezone_offset: int = +3):
    # Ensure end_date is at least 3 days after start_date
    if (end_date - start_date).days < 3:
        raise ValueError("end_date must be at least 3 days after start_date.")

    # Determine x-axis granularity
    days_diff = (end_date - start_date).days
    if days_diff < 32:
        group_by = "DATE(FROM_UNIXTIME(epoch + %s * 3600))"
        freq = "D"
    elif days_diff < 185:
        group_by = "YEARWEEK(FROM_UNIXTIME(epoch + %s * 3600), 3)"
        freq = "W-MON"
    elif days_diff < 1100:
        group_by = "DATE_FORMAT(FROM_UNIXTIME(epoch + %s * 3600), '%%Y-%%m')"
        freq = "MS"  # Month start
    else:
        group_by = "YEAR(FROM_UNIXTIME(epoch + %s * 3600))"
        freq = "AS"  # Year start

    # Adjust dates for timezone offset
    start_epoch = int(start_date.timestamp()) - timezone_offset * 3600
    end_epoch = int(end_date.timestamp()) - timezone_offset * 3600

    # SQL query to fetch message counts
    query = f"""
        SELECT 
            {group_by} AS period,
            COUNT(*) AS message_count
        FROM 
            `880368659858616321`
        WHERE 
            epoch BETWEEN %s AND %s
        GROUP BY 
            period
        ORDER BY 
            period ASC;
    """

    # Fetch data from the database
    async with aiomysql.connect(**get_db_creds('onsite')) as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(query, (timezone_offset, start_epoch, end_epoch))
            result = await cursor.fetchall()

    # Convert the results into a DataFrame
    df = pd.DataFrame(result, columns=['period', 'message_count'])

    # Convert period column to datetime format
    if freq == "W-MON":
        df['date'] = df['period'].astype(str).apply(
            lambda x: datetime.strptime(x + '-1', "%Y%W-%w"))  # Monday of that week
    elif freq in ["D", "MS", "AS"]:
        df['date'] = pd.to_datetime(df['period'])

    df.drop(columns=['period'], inplace=True)

    # Create a full date range for the x-axis
    full_range = pd.DataFrame({'date': pd.date_range(start=min(df['date']), end=max(df['date']), freq=freq)})

    # Merge and fill missing values
    df = full_range.merge(df, on='date', how='left').fillna(0)
    df['message_count'] = df['message_count'].astype(int)

    # Plotting
    plt.style.use("cyberpunk")  # Apply mplcyberpunk style

    fig, ax = plt.subplots(figsize=(12, 6), dpi=120)
    ax.plot(df['date'], df['message_count'], label="Messages", marker='o')

    # Format x-axis labels properly
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())

    plt.xticks(rotation=45, ha='right')
    ax.set_xlabel('Date')
    ax.set_ylabel('Number of Messages')
    ax.set_title('Activity Server: Messages Over Time')

    # Save and close the plot
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300)
    buf.seek(0)
    plt.close()

    return buf
