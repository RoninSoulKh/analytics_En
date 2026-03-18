import io
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from datetime import datetime, timedelta

def get_cf_data(zone_id, api_token, days_back):
    """Отримує історичні дані з Cloudflare GraphQL API"""
    url = "https://api.cloudflare.com/client/v4/graphql"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
    
    since_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    query = f"""
    query {{
      viewer {{
        zones(filter: {{zoneTag: "{zone_id}"}}) {{
          httpRequests1dGroups(limit: 1000, filter: {{date_geq: "{since_date}"}}) {{
            dimensions {{ date }}
            sum {{ threats }}
          }}
        }}
      }}
    }}
    """
    try:
        r = requests.post(url, headers=headers, json={"query": query}, timeout=10)
        data = r.json()
        zones = data.get("data", {}).get("viewer", {}).get("zones", [])
        if not zones: return {}
        
        groups = zones[0].get("httpRequests1dGroups", [])
        
        result = {}
        for g in groups:
            date_str = g.get("dimensions", {}).get("date")
            threats = g.get("sum", {}).get("threats", 0)
            if date_str: result[date_str] = threats
            
        return result
    except Exception as e:
        print(f"Graph CF API Error: {e}")
        return None

def generate_cf_chart(period_type, zone_id, api_token):
    """Генерує графік атак з Cloudflare у стилі ліній із заливкою"""
    
    if not zone_id or not api_token: return None
    
    days_back = 7 if period_type == "week" else 30 if period_type == "month" else 365
    cf_data = get_cf_data(zone_id, api_token, days_back)
    
    if cf_data is None: return None

    # Кольорова тема сайту Energy Analytics (Cloudflare Style)
    theme = {
        'bg': '#1e1e2f',
        'panel': '#2a2a40',
        'accent': '#00f2fe',
        'fill': '#005f8f',
        'text': '#e2e8f0',
        'grid': '#3f3f5a'
    }

    plt.rcParams.update({
        'figure.facecolor': theme['bg'],
        'axes.facecolor': theme['panel'],
        'text.color': theme['text'],
        'axes.labelcolor': theme['text'],
        'xtick.color': theme['text'],
        'ytick.color': theme['text'],
        'axes.edgecolor': theme['bg'],
    })

    fig, ax = plt.subplots(figsize=(10, 5))

    x_labels = []
    y_values = []
    now = datetime.now()

    if period_type == "week":
        for i in range(6, -1, -1):
            d = now - timedelta(days=i)
            d_str = d.strftime("%Y-%m-%d")
            x_labels.append(d.strftime("%a\n%d.%m"))
            y_values.append(cf_data.get(d_str, 0))
            
    elif period_type == "month":
        grouped = {}
        for i in range(29, -1, -1):
            d = now - timedelta(days=i)
            d_str = d.strftime("%Y-%m-%d")
            
            block_num = (29 - i) // 5 
            if block_num not in grouped: grouped[block_num] = {"val": 0, "label": f"{d.strftime('%d.%m')} - "}
            
            grouped[block_num]["val"] += cf_data.get(d_str, 0)
            if (29 - i) % 5 == 4 or i == 0:
                grouped[block_num]["label"] += d.strftime("%d.%m")
                
        for k in sorted(grouped.keys()):
            x_labels.append(grouped[k]["label"])
            y_values.append(grouped[k]["val"])

    elif period_type == "year":
        grouped = {}
        for i in range(365, -1, -1):
            d = now - timedelta(days=i)
            d_str = d.strftime("%Y-%m-%d")
            month_key = d.strftime("%Y-%m")
            month_label = d.strftime("%b '%y")
            
            if month_key not in grouped:
                grouped[month_key] = {"val": 0, "label": month_label}
            grouped[month_key]["val"] += cf_data.get(d_str, 0)
            
        for k in sorted(grouped.keys()):
            x_labels.append(grouped[k]["label"])
            y_values.append(grouped[k]["val"])


    x_pos = range(len(x_labels))
    ax.plot(x_pos, y_values, color=theme['accent'], linewidth=2.5, marker='o', markersize=6, markerfacecolor=theme['bg'], markeredgecolor=theme['accent'], markeredgewidth=2)
    ax.fill_between(x_pos, y_values, color=theme['accent'], alpha=0.2)
    
    # Підставляємо текстові мітки назад на вісь X
    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_labels)

    # Додаємо цифри над точками (якщо не 0)
    for i, val in enumerate(y_values):
        if val > 0:
            ax.annotate(f'{int(val)}',
                        xy=(i, val),
                        xytext=(0, 8),  # Відступ вище
                        textcoords="offset points",
                        ha='center', va='bottom', color=theme['accent'], fontweight='bold', fontsize=9)

    title = "External Threats Blocked"
    ax.set_title(title, color=theme['text'], pad=20, weight='bold', fontsize=14)
    ax.set_ylabel('Total Bot Attacks', color=theme['text'], fontsize=12, labelpad=10)

    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    plt.xticks(rotation=0 if period_type == "week" else 45, ha='center' if period_type == "week" else 'right', fontsize=9)
    plt.yticks(fontsize=10)

    if not y_values or max(y_values) == 0:
        ax.set_ylim(0, 5)
    else:
        ax.set_ylim(0, max(y_values) * 1.25) # Ще більше місця зверху

    ax.grid(axis='y', linestyle='--', alpha=0.3, color=theme['grid'])
    for spine in ['top', 'right', 'left', 'bottom']:
        ax.spines[spine].set_visible(False)

    plt.tight_layout()

    buffer = io.BytesIO()
    buffer.name = 'jarvis_chart.png'
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', transparent=False)
    buffer.seek(0)
    plt.close()
    
    return buffer