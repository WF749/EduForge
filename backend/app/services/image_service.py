"""PPT图片服务 - 为PPT幻灯片自动获取/生成配图"""
import os
import hashlib
import math
import random
from typing import Optional, Dict, List, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class ImageService:
    """PPT图片服务 - 为每页幻灯片提供配图"""

    # 图片缓存目录
    CACHE_DIR = "generated_courseware/_image_cache"

    # 主题色映射 (与PPT主题色一致)
    THEME_PALETTES = {
        "蓝色系": [(41, 128, 185), (52, 152, 219), (214, 234, 248), (174, 214, 241)],
        "绿色系": [(39, 174, 96), (46, 204, 113), (212, 239, 223), (171, 235, 198)],
        "红色系": [(192, 57, 43), (231, 76, 60), (245, 215, 210), (241, 148, 138)],
        "紫色系": [(142, 68, 173), (155, 89, 182), (232, 218, 239), (210, 180, 222)],
        "橙色系": [(211, 84, 0), (243, 156, 18), (253, 235, 208), (248, 196, 113)],
    }

    # 学科图标映射(Unicode符号)
    SUBJECT_ICONS = {
        "数学": ["\u2211", "\u222B", "\u03C0", "\u221A", "\u0394", "\u221E"],
        "物理": ["\u269B", "\u26A1", "\u2604", "\u2600", "\u2B50"],
        "化学": ["\u2697", "\u269B", "\u26A0"],
        "生物": ["\U0001F9EC", "\U0001F331", "\U0001F9EA"],
        "语文": ["\u7B14", "\u58A8", "\u7EB8", "\u7814"],
        "英语": ["A", "B", "C", "Aa"],
        "历史": ["\U0001F3DB", "\U0001F4DC", "\U0001F3F0"],
        "地理": ["\U0001F30D", "\U0001F5FA", "\u2603"],
        "信息技术": ["01", "</>" , "{}", "AI"],
        "计算机": ["01", "</>", "{}", "AI"],
        "general": ["\U0001F4DA", "\U0001F393", "\U0001F4A1", "\u2728"],
    }

    def __init__(self):
        os.makedirs(self.CACHE_DIR, exist_ok=True)

    def get_slide_image(
        self,
        core_topic: str,
        page_type: str = "knowledge",
        theme_color: str = "蓝色系",
        subject: str = "general",
        width: int = 800,
        height: int = 600,
        image_query: str = "",
    ) -> Optional[str]:
        """为幻灯片获取配图, 返回本地图片路径

        优先尝试在线搜索, 失败则用Pillow生成装饰图。
        """
        # 生成缓存key
        cache_key = hashlib.md5(
            f"{core_topic}_{page_type}_{theme_color}_{subject}_{width}x{height}".encode()
        ).hexdigest()
        cached_path = os.path.join(self.CACHE_DIR, f"{cache_key}.png")

        # 命中缓存直接返回
        if os.path.exists(cached_path):
            return cached_path

        # 尝试在线搜索
        query = image_query or core_topic
        online_path = self._try_online_search(query, cached_path, width, height)
        if online_path:
            return online_path

        # 使用Pillow生成装饰图
        if PILLOW_AVAILABLE:
            return self._generate_decorative_image(
                core_topic, theme_color, subject, width, height, cached_path
            )

        return None

    def get_images_for_slides(
        self,
        detailed_content: List[Dict],
        theme_color: str = "蓝色系",
        subject: str = "general",
    ) -> Dict[int, str]:
        """批量为幻灯片获取配图

        Returns:
            {page_num: image_path, ...} 仅包含知识点页
        """
        images = {}
        for page in detailed_content:
            page_type = page.get("page_type", "")
            if page_type not in ("knowledge",):
                continue
            page_num = page.get("page_num", 0)
            core_topic = page.get("core_topic", "")
            image_query = page.get("image_query", "")

            img_path = self.get_slide_image(
                core_topic=core_topic,
                page_type=page_type,
                theme_color=theme_color,
                subject=subject,
                width=800,
                height=600,
                image_query=image_query,
            )
            if img_path:
                images[page_num] = img_path

        return images

    # ==================== 在线图片搜索 ====================

    def _try_online_search(
        self, query: str, save_path: str, width: int, height: int
    ) -> Optional[str]:
        """尝试在线搜索图片"""
        if not REQUESTS_AVAILABLE:
            return None

        # 尝试 Pixabay API (需要配置API key)
        pixabay_key = os.environ.get("PIXABAY_API_KEY", "")
        if pixabay_key:
            result = self._search_pixabay(query, pixabay_key, save_path, width, height)
            if result:
                return result

        # 尝试 Pexels API
        pexels_key = os.environ.get("PEXELS_API_KEY", "")
        if pexels_key:
            result = self._search_pexels(query, pexels_key, save_path, width, height)
            if result:
                return result

        return None

    def _search_pixabay(
        self, query: str, api_key: str, save_path: str, width: int, height: int
    ) -> Optional[str]:
        """通过Pixabay API搜索图片"""
        try:
            url = "https://pixabay.com/api/"
            params = {
                "key": api_key,
                "q": query,
                "image_type": "illustration",
                "orientation": "horizontal",
                "per_page": 5,
                "safesearch": "true",
                "lang": "zh",
            }
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("hits", [])
                if hits:
                    img_url = hits[0].get("webformatURL", "")
                    if img_url:
                        return self._download_image(img_url, save_path)
        except Exception as e:
            print(f"Pixabay搜索失败: {e}")
        return None

    def _search_pexels(
        self, query: str, api_key: str, save_path: str, width: int, height: int
    ) -> Optional[str]:
        """通过Pexels API搜索图片"""
        try:
            url = "https://api.pexels.com/v1/search"
            headers = {"Authorization": api_key}
            params = {"query": query, "per_page": 5, "orientation": "landscape"}
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                photos = data.get("photos", [])
                if photos:
                    img_url = photos[0].get("src", {}).get("medium", "")
                    if img_url:
                        return self._download_image(img_url, save_path)
        except Exception as e:
            print(f"Pexels搜索失败: {e}")
        return None

    def _download_image(self, url: str, save_path: str) -> Optional[str]:
        """下载图片到本地"""
        try:
            resp = requests.get(url, timeout=15, stream=True)
            if resp.status_code == 200:
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(8192):
                        f.write(chunk)
                return save_path
        except Exception as e:
            print(f"图片下载失败: {e}")
        return None

    # ==================== Pillow 本地生成装饰图 ====================

    def _generate_decorative_image(
        self,
        core_topic: str,
        theme_color: str,
        subject: str,
        width: int,
        height: int,
        save_path: str,
    ) -> Optional[str]:
        """使用Pillow生成精美的装饰图"""
        try:
            palette = self.THEME_PALETTES.get(theme_color, self.THEME_PALETTES["蓝色系"])
            primary, accent, light, mid = palette

            img = Image.new("RGB", (width, height), light)
            draw = ImageDraw.Draw(img)

            # 绘制渐变背景
            self._draw_gradient(draw, width, height, light, (255, 255, 255))

            # 绘制装饰几何元素
            self._draw_decorations(draw, width, height, primary, accent, mid)

            # 绘制中心主题文字
            self._draw_topic_text(draw, img, core_topic, width, height, primary)

            # 绘制学科图标装饰
            self._draw_subject_icons(draw, img, subject, width, height, accent)

            # 添加底部渐变条
            self._draw_bottom_bar(draw, width, height, primary)

            img.save(save_path, "PNG", quality=95)
            return save_path

        except Exception as e:
            print(f"生成装饰图失败: {e}")
            return None

    def _draw_gradient(
        self,
        draw: "ImageDraw.Draw",
        width: int,
        height: int,
        color_start: Tuple[int, int, int],
        color_end: Tuple[int, int, int],
    ):
        """绘制垂直渐变背景"""
        for y in range(height):
            ratio = y / height
            r = int(color_start[0] + (color_end[0] - color_start[0]) * ratio)
            g = int(color_start[1] + (color_end[1] - color_start[1]) * ratio)
            b = int(color_start[2] + (color_end[2] - color_start[2]) * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

    def _draw_decorations(
        self,
        draw: "ImageDraw.Draw",
        width: int,
        height: int,
        primary: Tuple[int, int, int],
        accent: Tuple[int, int, int],
        mid: Tuple[int, int, int],
    ):
        """绘制装饰几何元素"""
        random.seed(hash((width, height, primary)))

        # 右上角大圆
        r1 = int(width * 0.35)
        cx1, cy1 = width - int(r1 * 0.4), -int(r1 * 0.3)
        alpha_color = tuple(min(255, c + 100) for c in accent)
        draw.ellipse(
            [cx1 - r1, cy1 - r1, cx1 + r1, cy1 + r1], fill=alpha_color
        )

        # 左下角中圆
        r2 = int(width * 0.22)
        cx2, cy2 = -int(r2 * 0.3), height - int(r2 * 0.5)
        alpha_color2 = tuple(min(255, c + 80) for c in mid)
        draw.ellipse(
            [cx2 - r2, cy2 - r2, cx2 + r2, cy2 + r2], fill=alpha_color2
        )

        # 散落小圆点装饰
        for _ in range(8):
            x = random.randint(int(width * 0.1), int(width * 0.9))
            y = random.randint(int(height * 0.1), int(height * 0.9))
            r = random.randint(3, 12)
            dot_color = tuple(min(255, c + 60) for c in primary)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=dot_color)

        # 装饰线条
        line_y = int(height * 0.15)
        line_color = tuple(min(255, c + 90) for c in primary)
        draw.line(
            [(int(width * 0.1), line_y), (int(width * 0.4), line_y)],
            fill=line_color,
            width=2,
        )
        line_y2 = int(height * 0.85)
        draw.line(
            [(int(width * 0.6), line_y2), (int(width * 0.9), line_y2)],
            fill=line_color,
            width=2,
        )

    def _draw_topic_text(
        self,
        draw: "ImageDraw.Draw",
        img: "Image.Image",
        topic: str,
        width: int,
        height: int,
        primary: Tuple[int, int, int],
    ):
        """绘制中心主题文字"""
        # 截短过长文字
        display_text = topic[:12] if len(topic) > 12 else topic

        # 尝试加载中文字体
        font = self._get_font(size=int(height * 0.1))
        small_font = self._get_font(size=int(height * 0.05))

        # 绘制文字背景半透明区域
        text_bbox = draw.textbbox((0, 0), display_text, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]

        pad_x, pad_y = 40, 20
        rect_x1 = (width - text_w) // 2 - pad_x
        rect_y1 = (height - text_h) // 2 - pad_y
        rect_x2 = (width + text_w) // 2 + pad_x
        rect_y2 = (height + text_h) // 2 + pad_y

        # 半透明白色背景
        bg_color = (255, 255, 255, 200)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle(
            [rect_x1, rect_y1, rect_x2, rect_y2],
            radius=15,
            fill=bg_color,
        )
        img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))

        # 重新获取draw对象
        draw = ImageDraw.Draw(img)

        # 绘制主题文字
        text_x = (width - text_w) // 2
        text_y = (height - text_h) // 2
        draw.text((text_x, text_y), display_text, fill=primary, font=font)

    def _draw_subject_icons(
        self,
        draw: "ImageDraw.Draw",
        img: "Image.Image",
        subject: str,
        width: int,
        height: int,
        accent: Tuple[int, int, int],
    ):
        """绘制学科相关图标装饰"""
        icons = self.SUBJECT_ICONS.get(subject, self.SUBJECT_ICONS["general"])
        icon_font = self._get_font(size=int(height * 0.06))
        icon_color = tuple(min(255, c + 40) for c in accent)

        positions = [
            (int(width * 0.08), int(height * 0.12)),
            (int(width * 0.88), int(height * 0.18)),
            (int(width * 0.12), int(height * 0.78)),
            (int(width * 0.85), int(height * 0.82)),
        ]

        for i, pos in enumerate(positions):
            if i < len(icons):
                try:
                    draw.text(pos, icons[i], fill=icon_color, font=icon_font)
                except Exception:
                    pass

    def _draw_bottom_bar(
        self,
        draw: "ImageDraw.Draw",
        width: int,
        height: int,
        primary: Tuple[int, int, int],
    ):
        """绘制底部装饰条"""
        bar_height = int(height * 0.03)
        draw.rectangle(
            [0, height - bar_height, width, height],
            fill=primary,
        )

    def _get_font(self, size: int = 36) -> "ImageFont.FreeTypeFont":
        """获取字体, 优先使用系统中文字体"""
        font_paths = [
            # Windows
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            # Linux
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            # macOS
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    return ImageFont.truetype(fp, size)
                except Exception:
                    continue

        # 回退到默认字体
        try:
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            return ImageFont.load_default()

    def generate_image_queries(
        self, detailed_content: List[Dict], topic: str, subject: str
    ) -> List[Dict]:
        """使用LLM为每页知识点生成图片搜索关键词

        会在每个 page dict 中添加 image_query 字段。
        """
        try:
            from .llm_service import llm_service
        except Exception:
            return detailed_content

        knowledge_pages = [
            p for p in detailed_content if p.get("page_type") == "knowledge"
        ]
        if not knowledge_pages:
            return detailed_content

        topics_text = "\n".join(
            [
                f"- 第{p.get('page_num', '?')}页: {p.get('core_topic', '')}"
                for p in knowledge_pages
            ]
        )

        prompt = f"""你是教育配图专家。请为以下PPT知识点页面各生成一个用于搜索教学配图的英文关键词(2-4个词)。

课程主题: {topic}
学科: {subject}

知识点页面:
{topics_text}

要求:
1. 关键词要能搜到与知识点相关的教学插图
2. 使用英文关键词(便于图库搜索)
3. 关键词简洁准确, 2-4个英文单词

请严格以JSON数组输出, 每个元素对应一个知识点页, 格式:
[{{"page_num": 页码, "image_query": "english keywords"}}]
只输出JSON, 不要其他内容。"""

        try:
            response = llm_service.chat(prompt, [], purpose="structured_extract")
            import json
            # 尝试解析
            text = response.strip()
            if "```" in text:
                start = text.find("```") + 3
                if text[start:].startswith("json"):
                    start += 4
                end = text.find("```", start)
                if end > start:
                    text = text[start:end].strip()
            import re
            json_match = re.search(r"\[.*\]", text, re.DOTALL)
            if json_match:
                queries = json.loads(json_match.group())
                if isinstance(queries, list):
                    query_map = {
                        item.get("page_num"): item.get("image_query", "")
                        for item in queries
                        if isinstance(item, dict)
                    }
                    for page in detailed_content:
                        pn = page.get("page_num")
                        if pn in query_map:
                            page["image_query"] = query_map[pn]
        except Exception as e:
            print(f"LLM生成图片关键词失败: {e}")

        return detailed_content


# 单例
image_service = ImageService()
