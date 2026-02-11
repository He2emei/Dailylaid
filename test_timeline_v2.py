# test_timeline_v2.py
"""时间线 SVG 模板 v2 - 现代设计趋势"""

def template_glassmorphism(date: str, activities: list) -> str:
    """毛玻璃风格 - 半透明卡片 + 模糊背景"""
    
    width = 500
    card_height = 80
    gap = 15
    total_height = len(activities) * (card_height + gap) + 120
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_height}">
  <defs>
    <!-- 背景渐变 -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#1a1a2e"/>
      <stop offset="50%" style="stop-color:#16213e"/>
      <stop offset="100%" style="stop-color:#0f3460"/>
    </linearGradient>
    
    <!-- 毛玻璃效果 -->
    <filter id="glass" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="0"/>
    </filter>
    
    <!-- 发光效果 -->
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    
    <!-- 装饰圆圈 -->
    <radialGradient id="blob1" cx="50%" cy="50%">
      <stop offset="0%" style="stop-color:#e94560;stop-opacity:0.6"/>
      <stop offset="100%" style="stop-color:#e94560;stop-opacity:0"/>
    </radialGradient>
    <radialGradient id="blob2" cx="50%" cy="50%">
      <stop offset="0%" style="stop-color:#0f4c75;stop-opacity:0.8"/>
      <stop offset="100%" style="stop-color:#0f4c75;stop-opacity:0"/>
    </radialGradient>
  </defs>
  
  <!-- 背景 -->
  <rect width="{width}" height="{total_height}" fill="url(#bgGrad)"/>
  
  <!-- 装饰光斑 -->
  <circle cx="400" cy="100" r="150" fill="url(#blob1)"/>
  <circle cx="50" cy="300" r="120" fill="url(#blob2)"/>
  
  <!-- 标题 -->
  <text x="{width//2}" y="45" text-anchor="middle" fill="white" font-family="Arial" font-size="22" font-weight="600">
    {date}
  </text>
  <text x="{width//2}" y="68" text-anchor="middle" fill="rgba(255,255,255,0.5)" font-family="Arial" font-size="12">
    TIME LOG
  </text>
'''
    
    colors = ["#e94560", "#00d9ff", "#ffd700", "#00ff88", "#ff6b6b"]
    y = 90
    
    for i, act in enumerate(activities):
        color = colors[i % len(colors)]
        
        # 毛玻璃卡片
        svg += f'''
  <!-- 卡片 {i+1} -->
  <rect x="30" y="{y}" width="{width-60}" height="{card_height}" rx="16" 
        fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.15)" stroke-width="1"/>
  
  <!-- 时间指示器 -->
  <circle cx="55" cy="{y + card_height//2}" r="8" fill="{color}" filter="url(#glow)"/>
  <circle cx="55" cy="{y + card_height//2}" r="4" fill="white"/>
  
  <!-- 活动名称 -->
  <text x="80" y="{y + 32}" fill="white" font-family="Arial" font-size="16" font-weight="500">
    {act["name"]}
  </text>
  
  <!-- 时间区间 -->
  <text x="80" y="{y + 55}" fill="rgba(255,255,255,0.6)" font-family="Arial" font-size="13">
    {act["start"]} → {act["end"]}
  </text>
  
  <!-- 时长 -->
  <text x="{width-50}" y="{y + card_height//2 + 5}" text-anchor="end" fill="{color}" font-family="Arial" font-size="12" font-weight="600">
    {calculate_duration(act["start"], act["end"])}
  </text>
'''
        y += card_height + gap
    
    svg += '</svg>'
    return svg


def template_neon(date: str, activities: list) -> str:
    """赛博朋克/霓虹风格"""
    
    width = 600
    hour_height = 50
    left_margin = 80
    bar_width = 450
    start_hour = 8
    end_hour = 20
    total_hours = end_hour - start_hour
    total_height = total_hours * hour_height + 120
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_height}">
  <defs>
    <!-- 霓虹发光 -->
    <filter id="neonGlow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="4" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    
    <filter id="textGlow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  
  <!-- 纯黑背景 -->
  <rect width="{width}" height="{total_height}" fill="#0a0a0a"/>
  
  <!-- 网格线（赛博朋克风格） -->
  <g stroke="#1a1a2e" stroke-width="1">
'''
    
    # 横向网格
    for i in range(0, total_height, 20):
        svg += f'    <line x1="0" y1="{i}" x2="{width}" y2="{i}"/>\n'
    
    svg += '''  </g>
  
  <!-- 标题 -->
'''
    svg += f'''  <text x="{width//2}" y="45" text-anchor="middle" fill="#00ffff" font-family="Courier New" font-size="28" font-weight="bold" filter="url(#textGlow)">
    {date}
  </text>
  <text x="{width//2}" y="70" text-anchor="middle" fill="#ff00ff" font-family="Courier New" font-size="12" letter-spacing="8" filter="url(#textGlow)">
    TIMELINE
  </text>
'''
    
    y_offset = 90
    colors = ["#00ffff", "#ff00ff", "#ffff00", "#00ff00", "#ff6600"]
    
    # 时间轴主线
    svg += f'''
  <!-- 时间轴主线 -->
  <line x1="{left_margin}" y1="{y_offset}" x2="{left_margin}" y2="{y_offset + total_hours * hour_height}" 
        stroke="#00ffff" stroke-width="2" filter="url(#neonGlow)"/>
'''
    
    # 小时刻度
    for h in range(start_hour, end_hour + 1):
        y = y_offset + (h - start_hour) * hour_height
        svg += f'''  <text x="{left_margin - 10}" y="{y + 5}" text-anchor="end" fill="#666" font-family="Courier New" font-size="11">{h:02d}:00</text>
  <line x1="{left_margin - 5}" y1="{y}" x2="{left_margin + 5}" y2="{y}" stroke="#00ffff" stroke-width="2"/>
'''
    
    # 活动块
    for i, act in enumerate(activities):
        sh, sm = map(int, act["start"].split(":"))
        eh, em = map(int, act["end"].split(":"))
        
        if sh < start_hour:
            sh, sm = start_hour, 0
        if eh > end_hour:
            eh, em = end_hour, 0
            
        start_y = y_offset + (sh - start_hour) * hour_height + sm * hour_height / 60
        end_y = y_offset + (eh - start_hour) * hour_height + em * hour_height / 60
        height = max(end_y - start_y, 30)
        
        color = colors[i % len(colors)]
        
        svg += f'''
  <!-- {act["name"]} -->
  <rect x="{left_margin + 20}" y="{start_y}" width="{bar_width - 30}" height="{height}" 
        fill="none" stroke="{color}" stroke-width="2" rx="0" filter="url(#neonGlow)"/>
  <rect x="{left_margin + 20}" y="{start_y}" width="{bar_width - 30}" height="{height}" 
        fill="{color}" opacity="0.1"/>
  <text x="{left_margin + 35}" y="{start_y + height/2 + 5}" fill="{color}" font-family="Courier New" font-size="14" font-weight="bold">
    {act["name"]}
  </text>
  <text x="{left_margin + bar_width - 20}" y="{start_y + height/2 + 5}" text-anchor="end" fill="#fff" font-family="Courier New" font-size="11">
    {act["start"]}-{act["end"]}
  </text>
  <circle cx="{left_margin}" cy="{start_y + height/2}" r="6" fill="{color}" filter="url(#neonGlow)"/>
'''
    
    svg += '</svg>'
    return svg


def template_skeletal(date: str, activities: list) -> str:
    """极简线条风格 - 轻盈优雅"""
    
    width = 500
    item_height = 60
    gap = 20
    total_height = len(activities) * (item_height + gap) + 100
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_height}">
  <!-- 纯白背景 -->
  <rect width="{width}" height="{total_height}" fill="#fafafa"/>
  
  <!-- 标题 -->
  <text x="40" y="45" fill="#333" font-family="Georgia" font-size="20" font-style="italic">
    {date}
  </text>
  <line x1="40" y1="55" x2="200" y2="55" stroke="#333" stroke-width="1"/>
  
  <!-- 时间轴线 -->
  <line x1="60" y1="80" x2="60" y2="{total_height - 30}" stroke="#ddd" stroke-width="1"/>
'''
    
    y = 90
    for i, act in enumerate(activities):
        svg += f'''
  <!-- 节点 -->
  <circle cx="60" cy="{y + item_height//2}" r="6" fill="none" stroke="#333" stroke-width="1.5"/>
  <circle cx="60" cy="{y + item_height//2}" r="2" fill="#333"/>
  
  <!-- 连接线 -->
  <line x1="66" y1="{y + item_height//2}" x2="85" y2="{y + item_height//2}" stroke="#ddd" stroke-width="1"/>
  
  <!-- 内容 -->
  <text x="95" y="{y + item_height//2 - 8}" fill="#111" font-family="Georgia" font-size="15">
    {act["name"]}
  </text>
  <text x="95" y="{y + item_height//2 + 12}" fill="#999" font-family="Arial" font-size="12">
    {act["start"]} — {act["end"]} · {calculate_duration(act["start"], act["end"])}
  </text>
'''
        y += item_height + gap
    
    svg += '</svg>'
    return svg


def calculate_duration(start: str, end: str) -> str:
    """计算时长"""
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    
    total_mins = (eh * 60 + em) - (sh * 60 + sm)
    hours = total_mins // 60
    mins = total_mins % 60
    
    if hours > 0 and mins > 0:
        return f"{hours}h {mins}m"
    elif hours > 0:
        return f"{hours}h"
    else:
        return f"{mins}m"


# 测试数据
activities = [
    {"start": "09:00", "end": "10:30", "name": "改代码"},
    {"start": "10:30", "end": "11:30", "name": "开会讨论"},
    {"start": "12:00", "end": "13:00", "name": "午餐休息"},
    {"start": "14:00", "end": "16:00", "name": "写文档"},
    {"start": "16:30", "end": "17:30", "name": "Code Review"},
]

# 生成
templates = {
    "glass": template_glassmorphism,
    "neon": template_neon,
    "skeletal": template_skeletal,
}

for name, func in templates.items():
    svg = func("2026-02-07", activities)
    with open(f"test_timeline_{name}.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"已生成: test_timeline_{name}.svg")
