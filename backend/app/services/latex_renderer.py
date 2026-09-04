"""LaTeX公式渲染服务 - 将LaTeX公式渲染为PNG图片，用于PPT插入"""
import os
import re
import hashlib
import tempfile
from typing import Optional, Tuple

try:
    import matplotlib
    matplotlib.use('Agg')  # 无GUI后端
    import matplotlib.pyplot as plt
    from matplotlib import mathtext
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# 公式缓存目录
_CACHE_DIR = os.path.join(tempfile.gettempdir(), "latex_render_cache")
os.makedirs(_CACHE_DIR, exist_ok=True)


def has_latex(text: str) -> bool:
    """检测文本中是否包含LaTeX公式"""
    if not text:
        return False
    return bool(re.search(r'\$\$[\s\S]+?\$\$|\$[^$\n]+?\$', text))


def render_latex_to_png(
    latex: str,
    font_size: int = 20,
    dpi: int = 200,
    text_color: str = "#2C3E50",
) -> Optional[str]:
    """
    将LaTeX公式渲染为PNG图片
    返回值: PNG文件路径，失败返回None
    """
    if not MATPLOTLIB_AVAILABLE:
        return None

    latex = latex.strip()
    if not latex:
        return None

    # 基于内容生成缓存文件名
    cache_key = hashlib.md5(f"{latex}_{font_size}_{dpi}_{text_color}".encode()).hexdigest()
    cache_path = os.path.join(_CACHE_DIR, f"latex_{cache_key}.png")
    if os.path.exists(cache_path):
        return cache_path

    try:
        fig, ax = plt.subplots(figsize=(0.01, 0.01))
        ax.axis('off')
        fig.patch.set_alpha(0)

        # matplotlib 使用 $ 包裹表示数学模式
        if not latex.startswith('$'):
            latex = f'${latex}$'

        text_obj = ax.text(
            0, 0.5, latex,
            fontsize=font_size,
            color=text_color,
            ha='left', va='center',
            transform=ax.transAxes,
        )

        fig.savefig(
            cache_path,
            dpi=dpi,
            transparent=True,
            bbox_inches='tight',
            pad_inches=0.05,
        )
        plt.close(fig)
        return cache_path
    except Exception as e:
        plt.close('all')
        print(f"LaTeX渲染失败: {e}, 公式: {latex[:60]}")
        return None


def render_text_with_formulas(
    text: str,
    font_size: int = 20,
    dpi: int = 200,
    text_color: str = "#2C3E50",
    bg_color: str = "white",
) -> Optional[str]:
    """
    将包含LaTeX公式的整段文本渲染为PNG图片。
    普通文本 + 公式混排时使用。
    返回值: PNG文件路径，失败返回None
    """
    if not MATPLOTLIB_AVAILABLE:
        return None

    text = text.strip()
    if not text:
        return None

    cache_key = hashlib.md5(f"full_{text}_{font_size}_{dpi}".encode()).hexdigest()
    cache_path = os.path.join(_CACHE_DIR, f"text_{cache_key}.png")
    if os.path.exists(cache_path):
        return cache_path

    try:
        # 将 $$...$$ 和 $...$ 转为 matplotlib 可识别的格式
        # matplotlib text 中 $...$ 本身就是数学模式
        display_text = text
        # $$...$$ → $...$ (matplotlib 只需单$)
        display_text = re.sub(r'\$\$([\s\S]+?)\$\$', r'$\1$', display_text)

        fig, ax = plt.subplots(figsize=(0.01, 0.01))
        ax.axis('off')
        if bg_color == 'transparent':
            fig.patch.set_alpha(0)
        else:
            fig.patch.set_facecolor(bg_color)

        ax.text(
            0, 0.5, display_text,
            fontsize=font_size,
            color=text_color,
            ha='left', va='center',
            transform=ax.transAxes,
            usetex=False,  # 使用 mathtext 而非完整 TeX
        )

        fig.savefig(
            cache_path,
            dpi=dpi,
            transparent=(bg_color == 'transparent'),
            bbox_inches='tight',
            pad_inches=0.08,
        )
        plt.close(fig)
        return cache_path
    except Exception as e:
        plt.close('all')
        print(f"文本+公式渲染失败: {e}, 文本: {text[:60]}")
        return None


def extract_formulas(text: str) -> list:
    """提取文本中所有LaTeX公式"""
    formulas = []
    # 先提取块级公式
    for m in re.finditer(r'\$\$([\s\S]+?)\$\$', text):
        formulas.append(('display', m.group(1).strip(), m.start(), m.end()))
    # 再提取行内公式（排除已匹配的块级）
    display_ranges = [(f[2], f[3]) for f in formulas]
    for m in re.finditer(r'\$([^$\n]+?)\$', text):
        in_display = any(s <= m.start() < e for s, e in display_ranges)
        if not in_display:
            formulas.append(('inline', m.group(1).strip(), m.start(), m.end()))
    return formulas


def strip_latex(text: str) -> str:
    """移除文本中的LaTeX标记，返回纯文本（作为后备方案）"""
    result = re.sub(r'\$\$([\s\S]+?)\$\$', r' [公式] ', text)
    result = re.sub(r'\$([^$\n]+?)\$', r'\1', result)
    return result.strip()
