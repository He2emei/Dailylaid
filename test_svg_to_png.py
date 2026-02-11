# test_svg_to_png.py
"""SVG 转 PNG 测试 - 使用 subprocess 调用 Inkscape 或者用 Pillow"""

import os
import subprocess

def svg_to_png_inkscape(svg_path: str, png_path: str, width: int = None) -> bool:
    """使用 Inkscape 转换（如果安装了的话）"""
    try:
        cmd = ["inkscape", svg_path, "-o", png_path]
        if width:
            cmd.extend(["-w", str(width)])
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except:
        return False


def check_png_tools():
    """检查可用的转换工具"""
    tools = []
    
    # 检查 Inkscape
    try:
        result = subprocess.run(["inkscape", "--version"], capture_output=True)
        if result.returncode == 0:
            tools.append("inkscape")
    except:
        pass
    
    # 检查 Chrome/Edge (可以用 headless 模式截图)
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for p in chrome_paths:
        if os.path.exists(p):
            tools.append("chrome")
            break
    
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in edge_paths:
        if os.path.exists(p):
            tools.append("edge")
            break
    
    return tools


def svg_to_png_browser(svg_path: str, png_path: str, browser: str = "edge") -> bool:
    """使用浏览器 headless 模式截图"""
    abs_svg = os.path.abspath(svg_path)
    abs_png = os.path.abspath(png_path)
    
    if browser == "edge":
        exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if not os.path.exists(exe):
            exe = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    else:
        exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    
    if not os.path.exists(exe):
        return False
    
    try:
        cmd = [
            exe,
            "--headless",
            f"--screenshot={abs_png}",
            "--disable-gpu",
            "--window-size=800,1000",
            f"file:///{abs_svg.replace(os.sep, '/')}"
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=10)
        return os.path.exists(abs_png)
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    print("检查可用的 SVG→PNG 转换工具...")
    tools = check_png_tools()
    print(f"可用工具: {tools}")
    
    if "edge" in tools:
        print("\n尝试使用 Edge 转换...")
        if svg_to_png_browser("test_timeline_modern.svg", "test_output.png", "edge"):
            print("✅ 转换成功: test_output.png")
        else:
            print("❌ 转换失败")
    elif "chrome" in tools:
        print("\n尝试使用 Chrome 转换...")
        if svg_to_png_browser("test_timeline_modern.svg", "test_output.png", "chrome"):
            print("✅ 转换成功: test_output.png")
        else:
            print("❌ 转换失败")
    elif "inkscape" in tools:
        print("\n尝试使用 Inkscape 转换...")
        if svg_to_png_inkscape("test_timeline_modern.svg", "test_output.png"):
            print("✅ 转换成功: test_output.png")
        else:
            print("❌ 转换失败")
    else:
        print("\n没有找到可用的转换工具")
        print("建议安装: Inkscape 或使用 Chrome/Edge")
