import io
import sqlite3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta

def generate_stats_chart(days=7, db_path="security_logs.db"):
    theme_colors = {
        'fig_bg': '#101018',
        'ax_bg': '#151520',
        'bars': '#ef4444',
        'grid': '#313244',
        'text': '#cdd6f4',
        'spines': '#313244'
    }
    
    plt.rcParams.update({
        'figure.facecolor': theme_colors['fig_bg'],
        'axes.facecolor': theme_colors['ax_bg'],
        'grid.color': theme_colors['grid'],
        'text.color': theme_colors['text'],
        'axes.labelcolor': theme_colors['text'],
        'xtick.color': theme_colors['text'],
        'ytick.color': theme_colors['text'],
        'axes.edgecolor': theme_colors['spines'],
    })
    
    fig, ax = plt.subplots(figsize=(10, 5))
    
    dates = [datetime.now() - timedelta(days=i) for i in range(days-1, -1, -1)]
    date_strings = [d.strftime('%Y-%m-%d') for d in dates]
    values_dict = {d: 0 for d in date_strings}

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT DATE(timestamp), COUNT(*) 
                FROM logs 
                WHERE DATE(timestamp) >= DATE('now', '-{days} days')
                GROUP BY DATE(timestamp)
            ''')
            for row in cursor.fetchall():
                date_key, count = row
                if date_key in values_dict:
                    values_dict[date_key] = count
    except Exception as e:
        print(f"Помилка БД: {e}")

    values = [values_dict[d] for d in date_strings]

    ax.bar(dates, values, color=theme_colors['bars'], alpha=0.9, width=0.6, align='center')

    ax.set_title(f'SOC Attacks Blocked (Last {days} Days)', color=theme_colors['text'], pad=20, weight='bold', fontsize=14)
    ax.set_ylabel('Incidents Count', color=theme_colors['text'], fontsize=12, pad=10)

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    plt.xticks(rotation=45, ha='right', fontsize=10)
    plt.yticks(fontsize=10)

    if max(values) == 0:
        ax.set_ylim(0, 5)

    ax.grid(axis='y', linestyle='--', alpha=0.7)
    
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    
    ax.spines['bottom'].set_linewidth(1)

    plt.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    plt.close()
    
    return buffer