# test_timeline_svg.py
"""生成时间线 SVG 示例"""

def generate_timeline_svg(date: str, activities: list) -> str:
    """生成一天的时间线 SVG
    
    Args:
        date: 日期 (如 2026-02-07)
        activities: 活动列表 [{"start": "09:00", "end": "10:00", "name": "改代码", "color": "#4CAF50"}, ...]
    
    Returns:
        SVG 字符串
    """
    
    # SVG 配置
    width = 800
    hour_height = 50
    left_margin = 60
    bar_width = 600
    
    # 计算时间范围 (6:00 - 24:00)
    start_hour = 6
    end_hour = 24
    total_hours = end_hour - start_hour
    total_height = total_hours * hour_height + 100
    
    svg_parts = []
    
    # SVG 头部
    svg_parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_height}" viewBox="0 0 {width} {total_height}">
  <defs>
    <style>
      .title {{ font: bold 20px sans-serif; fill: #333; }}
      .hour-label {{ font: 14px sans-serif; fill: #666; }}
      .activity-text {{ font: 14px sans-serif; fill: white; }}
      .grid-line {{ stroke: #e0e0e0; stroke-width: 1; }}
    </style>
  </defs>
  
  <!-- 背景 -->
  <rect width="{width}" height="{total_height}" fill="#fafafa"/>
  
  <!-- 标题 -->
  <text x="{width//2}" y="35" text-anchor="middle" class="title">📅 {date} 时间日志</text>
''')
    
    # 绘制时间网格
    y_offset = 60
    for h in range(start_hour, end_hour + 1):
        y = y_offset + (h - start_hour) * hour_height
        # 小时标签
        svg_parts.append(f'  <text x="50" y="{y + 5}" text-anchor="end" class="hour-label">{h:02d}:00</text>')
        # 网格线
        svg_parts.append(f'  <line x1="{left_margin}" y1="{y}" x2="{left_margin + bar_width}" y2="{y}" class="grid-line"/>')
    
    # 绘制活动块
    colors = ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#E91E63", "#00BCD4"]
    
    for i, act in enumerate(activities):
        start_time = act["start"]
        end_time = act["end"]
        name = act["name"]
        color = act.get("color", colors[i % len(colors)])
        
        # 解析时间
        sh, sm = map(int, start_time.split(":"))
        eh, em = map(int, end_time.split(":"))
        
        start_y = y_offset + (sh - start_hour) * hour_height + sm * hour_height / 60
        end_y = y_offset + (eh - start_hour) * hour_height + em * hour_height / 60
        height = end_y - start_y
        
        # 活动条
        svg_parts.append(f'''
  <!-- {name} -->
  <rect x="{left_margin + 10}" y="{start_y}" width="{bar_width - 20}" height="{height}" 
        rx="6" fill="{color}" opacity="0.9"/>
  <text x="{left_margin + 20}" y="{start_y + height/2 + 5}" class="activity-text">{start_time}-{end_time} {name}</text>
''')
    
    svg_parts.append('</svg>')
    
    return '\n'.join(svg_parts)


# 测试数据
activities = [
    {"start": "09:00", "end": "10:30", "name": "改代码", "color": "#4CAF50"},
    {"start": "10:30", "end": "11:30", "name": "开会讨论", "color": "#2196F3"},
    {"start": "12:00", "end": "13:00", "name": "午餐休息", "color": "#FF9800"},
    {"start": "14:00", "end": "16:00", "name": "写文档", "color": "#9C27B0"},
    {"start": "16:30", "end": "17:30", "name": "Code Review", "color": "#E91E63"},
]

svg_content = generate_timeline_svg("2026-02-07", activities)

# 保存到文件
with open("test_timeline.svg", "w", encoding="utf-8") as f:
    f.write(svg_content)

print("已生成 test_timeline.svg")
print(f"文件大小: {len(svg_content)} 字节")
