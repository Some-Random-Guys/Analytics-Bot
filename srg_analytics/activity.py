import matplotlib.pyplot as plt
import mplcyberpunk
import aiomysql
import pandas as pd
from datetime import datetime, timedelta
import asyncio
from backend import get_db_creds


async def activity_server(start_date, end_date, timezone_offset: int = +3):
    # Ensure end_date is at least 3 days after start_date
    if (end_date - start_date).days < 3:
        raise ValueError("end_date must be at least 3 days after start_date.")

    # Determine x-axis granularity
    days_diff = (end_date - start_date).days
    if days_diff < 32:
        date_format = "%Y-%m-%d"  # Daily labels
        date_interval = 'D'  # Pandas date range frequency
        group_by = "DATE(FROM_UNIXTIME(epoch + %s * 3600))"
    elif days_diff < 185:
        date_format = "%Y-%m-%d"  # Weekly labels
        date_interval = 'W'  # Pandas date range frequency
        group_by = "YEARWEEK(FROM_UNIXTIME(epoch + %s * 3600), 3)"
    elif days_diff < 1100:
        date_format = "%Y-%m"  # Monthly labels
        date_interval = 'MS'  # Pandas date range frequency
        group_by = "DATE_FORMAT(FROM_UNIXTIME(epoch + %s * 3600), '%%Y-%%m')"
    else:
        date_format = "%Y"  # Yearly labels
        date_interval = 'AS'  # Pandas date range frequency
        group_by = "YEAR(FROM_UNIXTIME(epoch + %s * 3600))"

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
    async with aiomysql.connect(get_db_creds('onsite')) as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(query, (timezone_offset, start_epoch, end_epoch))
            result = await cursor.fetchall()

    # Prepare data for plotting
    periods = []
    message_counts = []
    for row in result:
        periods.append(row[0])
        message_counts.append(row[1])

    # Create a date range for x-axis labels
    if date_interval == 'AS':  # Annual Start frequency
        date_range = pd.date_range(start=start_date, end=end_date, freq='YS')
    else:
        date_range = pd.date_range(start=start_date, end=end_date, freq=date_interval)

    # Create a DataFrame to handle missing periods
    df = pd.DataFrame({'period': periods, 'message_count': message_counts})

    # Convert 'period' to datetime
    if date_format == "%Y-%m-%d":
        df['date'] = pd.to_datetime(df['period'])
    elif date_format == "%Y-%m":
        df['date'] = pd.to_datetime(df['period'] + '-01')
    elif date_format == "%Y":
        df['date'] = pd.to_datetime(df['period'] + '-01-01')
    else:
        # For weekly data, we need to parse the year and week number
        df['date'] = df['period'].apply(lambda x: datetime.strptime(f"{x}-1", "%Y%W-%w"))

    # Reindex DataFrame to include all dates in the range
    df = df.set_index('date').reindex(date_range, fill_value=0).reset_index()
    df.rename(columns={'index': 'date'}, inplace=True)

    # Plotting
    plt.style.use("cyberpunk")  # Apply mplcyberpunk style

    fig, ax = plt.subplots(figsize=(12, 6), dpi=120)
    ax.plot(df['date'], df['message_count'], label="Messages", marker='o')

    # Set x-axis label formatting
    ax.set_xticks(df['date'])
    ax.set_xticklabels([dt.strftime(date_format) for dt in df['date']], rotation=45, ha='right')

    # Set labels and title
    ax.set_xlabel('Date')
    ax.set_ylabel('Number of Messages')
    ax.set_title('Activity Server: Messages Over Time')

    # Save plot
    plt.tight_layout()
    plt.savefig("activity_server_graph.png", dpi=300)
    plt.close()

# Example usage (with placeholder dates):
# asyncio.run(activity_server(datetime(2023, 1, 1), datetime(2023, 2, 1)))
