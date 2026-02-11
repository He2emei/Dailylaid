# test_timeline_templates.py
"""时间线 SVG 模板 - 多种风格"""

def template_modern(date: str, activities: list) -> str:
    """现代风格 - 渐变色 + 阴影"""
    
    width = 800
    hour_height = 45
    left_margin = 70
    bar_width = 650
    start_hour = 6
    end_hour = 24
    total_hours = end_hour - start_hour
    total_height = total_hours * hour_height + 120
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_height}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#667eea"/>
      <stop offset="100%" style="stop-color:#764ba2"/>
    </linearGradient>
    <linearGradient id="green" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#11998e"/>
      <stop offset="100%" style="stop-color:#38ef7d"/>
    </linearGradient>
    <linearGradient id="blue" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#4facfe"/>
      <stop offset="100%" style="stop-color:#00f2fe"/>
    </linearGradient>
    <linearGradient id="orange" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#f093fb"/>
      <stop offset="100%" style="stop-color:#f5576c"/>
    </linearGradient>
    <linearGradient id="purple" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#5f2c82"/>
      <stop offset="100%" style="stop-color:#49a09d"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="2" dy="3" stdDeviation="3" flood-opacity="0.3"/>
    </filter>
  </defs>
  
  <!-- 背景 -->
  <rect width="{width}" height="{total_height}" fill="#1a1a2e"/>
  
  <!-- 标题 -->
  <text x="{width//2}" y="45" text-anchor="middle" fill="white" font-family="Arial" font-size="24" font-weight="bold">
    📅 {date}
  </text>
  <text x="{width//2}" y="70" text-anchor="middle" fill="#888" font-family="Arial" font-size="14">
    Daily Timeline
  </text>
'''
    
    gradients = ["green", "blue", "orange", "purple"]
    y_offset = 90
    
    # 时间轴线
    for h in range(start_hour, end_hour + 1):
        y = y_offset + (h - start_hour) * hour_height
        svg += f'  <text x="55" y="{y + 5}" text-anchor="end" fill="#666" font-family="Arial" font-size="12">{h:02d}:00</text>\n'
        svg += f'  <line x1="{left_margin}" y1="{y}" x2="{left_margin + bar_width}" y2="{y}" stroke="#333" stroke-width="1"/>\n'
    
    # 活动块
    for i, act in enumerate(activities):
        sh, sm = map(int, act["start"].split(":"))
        eh, em = map(int, act["end"].split(":"))
        
        start_y = y_offset + (sh - start_hour) * hour_height + sm * hour_height / 60
        end_y = y_offset + (eh - start_hour) * hour_height + em * hour_height / 60
        height = max(end_y - start_y, 30)
        
        grad = gradients[i % len(gradients)]
        svg += f'''
  <rect x="{left_margin + 5}" y="{start_y}" width="{bar_width - 10}" height="{height}" 
        rx="8" fill="url(#{grad})" filter="url(#shadow)"/>
  <text x="{left_margin + 15}" y="{start_y + height/2 + 5}" fill="white" font-family="Arial" font-size="13" font-weight="bold">
    {act["start"]}-{act["end"]} {act["name"]}
  </text>
'''
    
    svg += '</svg>'
    return svg


def template_minimal(date: str, activities: list) -> str:
    """极简风格 - 白底 + 细线"""
    
    width = 700
    hour_height = 40
    left_margin = 60
    bar_width = 580
    start_hour = 8
    end_hour = 20
    total_hours = end_hour - start_hour
    total_height = total_hours * hour_height + 100
    
    colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DFE6E9"]
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_height}">
  <rect width="{width}" height="{total_height}" fill="white"/>
  
  <text x="30" y="40" fill="#333" font-family="Helvetica" font-size="20" font-weight="bold">{date}</text>
  <line x1="30" y1="55" x2="{width-30}" y2="55" stroke="#eee" stroke-width="2"/>
'''
    
    y_offset = 75
    
    for h in range(start_hour, end_hour + 1):
        y = y_offset + (h - start_hour) * hour_height
        svg += f'  <text x="50" y="{y + 4}" text-anchor="end" fill="#aaa" font-family="Helvetica" font-size="11">{h:02d}</text>\n'
        svg += f'  <line x1="{left_margin}" y1="{y}" x2="{left_margin + bar_width}" y2="{y}" stroke="#f0f0f0" stroke-width="1"/>\n'
    
    for i, act in enumerate(activities):
        sh, sm = map(int, act["start"].split(":"))
        eh, em = map(int, act["end"].split(":"))
        
        if sh < start_hour or eh > end_hour:
            continue
            
        start_y = y_offset + (sh - start_hour) * hour_height + sm * hour_height / 60
        end_y = y_offset + (eh - start_hour) * hour_height + em * hour_height / 60
        height = max(end_y - start_y, 25)
        
        color = colors[i % len(colors)]
        svg += f'''
  <rect x="{left_margin + 5}" y="{start_y + 2}" width="{bar_width - 10}" height="{height - 4}" 
        rx="4" fill="{color}" opacity="0.85"/>
  <text x="{left_margin + 12}" y="{start_y + height/2 + 4}" fill="#333" font-family="Helvetica" font-size="12">
    {act["name"]}
  </text>
  <text x="{left_margin + bar_width - 15}" y="{start_y + height/2 + 4}" text-anchor="end" fill="#666" font-family="Helvetica" font-size="10">
    {act["start"]}-{act["end"]}
  </text>
'''
    
    svg += '</svg>'
    return svg


def template_card(date: str, activities: list) -> str:
    """卡片风格 - 圆角卡片 + 图标"""
    
    width = 400
    card_height = 70
    gap = 10
    total_height = len(activities) * (card_height + gap) + 100
    
    colors = [
        ("#667eea", "#764ba2"),  # 紫色
        ("#f093fb", "#f5576c"),  # 粉色
        ("#4facfe", "#00f2fe"),  # 蓝色
        ("#43e97b", "#38f9d7"),  # 绿色
        ("#fa709a", "#fee140"),  # 橙色
    ]
    
    icons = ["💻", "📞", "🍽️", "📝", "👥", "🎯"]
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_height}">
  <defs>
    <filter id="cardShadow" x="-10%" y="-10%" width="120%" height="130%">
      <feDropShadow dx="0" dy="4" stdDeviation="8" flood-opacity="0.15"/>
    </filter>
'''
    
    for i, (c1, c2) in enumerate(colors):
        svg += f'''    <linearGradient id="grad{i}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{c1}"/>
      <stop offset="100%" style="stop-color:{c2}"/>
    </linearGradient>
'''
    
    svg += f'''  </defs>
  
  <rect width="{width}" height="{total_height}" fill="#f5f7fa"/>
  
  <text x="{width//2}" y="45" text-anchor="middle" fill="#333" font-family="Arial" font-size="18" font-weight="bold">
    {date}
  </text>
'''
    
    y = 70
    for i, act in enumerate(activities):
        icon = icons[i % len(icons)]
        grad = f"grad{i % len(colors)}"
        
        svg += f'''
  <rect x="20" y="{y}" width="{width-40}" height="{card_height}" rx="12" fill="url(#{grad})" filter="url(#cardShadow)"/>
  <text x="35" y="{y + 42}" fill="white" font-size="28">{icon}</text>
  <text x="75" y="{y + 30}" fill="white" font-family="Arial" font-size="15" font-weight="bold">{act["name"]}</text>
  <text x="75" y="{y + 50}" fill="rgba(255,255,255,0.8)" font-family="Arial" font-size="12">{act["start"]} - {act["end"]}</text>
'''
        y += card_height + gap
    
    svg += '</svg>'
    return svg


# 生成测试
activities = [
    {"start": "09:00", "end": "10:30", "name": "改代码"},
    {"start": "10:30", "end": "11:30", "name": "开会讨论"},
    {"start": "12:00", "end": "13:00", "name": "午餐休息"},
    {"start": "14:00", "end": "16:00", "name": "写文档"},
    {"start": "16:30", "end": "17:30", "name": "Code Review"},
]

# 保存三种模板
templates = {
    "modern": template_modern,
    "minimal": template_minimal,
    "card": template_card,
}

for name, func in templates.items():
    svg = func("2026-02-07", activities)
    with open(f"test_timeline_{name}.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"已生成: test_timeline_{name}.svg")
