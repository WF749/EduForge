"""文档处理器"""
from typing import Optional
import PyPDF2
from docx import Document
from pptx import Presentation
import os
import struct
import subprocess
import shutil
from PIL import Image

# 尝试导入pytesseract，如果失败则设置为None
try:
    import pytesseract
except ImportError:
    pytesseract = None

# 尝试导入moviepy，如果失败则设置为None
try:
    from moviepy.editor import VideoFileClip
except ImportError:
    VideoFileClip = None

# 尝试导入 win32com（Windows 下转换 .doc/.ppt 旧格式）
try:
    import win32com.client as win32
    HAS_WIN32COM = True
except ImportError:
    HAS_WIN32COM = False

# 尝试导入 olefile（解析 OLE2 二进制格式）
try:
    import olefile
    HAS_OLEFILE = True
except ImportError:
    HAS_OLEFILE = False

class DocumentProcessor:
    """文档处理器类"""
    
    def process(self, file_path: str) -> str:
        """处理文档，返回文本内容"""
        file_ext = file_path.split(".")[-1].lower()
        
        if file_ext == "pdf":
            return self._process_pdf(file_path)
        elif file_ext in ("docx", "doc"):
            return self._process_docx(file_path)
        elif file_ext in ("pptx", "ppt"):
            return self._process_pptx(file_path)
        elif file_ext in ["txt", "md"]:
            return self._process_text(file_path)
        elif file_ext in ["jpg", "jpeg", "png", "gif", "bmp"]:
            return self._process_image(file_path)
        elif file_ext in ["mp4", "avi", "mov", "wmv"]:
            return self._process_video(file_path)
        elif file_ext in ["mp3", "wav", "flac", "aac"]:
            return self._process_audio(file_path)
        else:
            raise Exception(f"不支持的文件类型: {file_ext}")
    
    def _process_pdf(self, file_path: str) -> str:
        """处理PDF文件"""
        try:
            with open(file_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page_num in range(len(reader.pages)):
                    page = reader.pages[page_num]
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            raise Exception(f"处理PDF文件失败: {str(e)}")
    
    def _process_docx(self, file_path: str) -> str:
        """处理Word文件（支持 .docx 和 .doc 旧格式）"""
        file_ext = file_path.split(".")[-1].lower()
        
        # .docx 直接用 python-docx 处理
        if file_ext == "docx":
            try:
                doc = Document(file_path)
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            if cell.text.strip():
                                text += cell.text + "\n"
                return text
            except Exception as e:
                raise Exception(f"处理Word文件失败: {str(e)}")
        
        # .doc 旧格式
        if file_ext == "doc":
            # 方式1: Windows COM 自动转换
            if HAS_WIN32COM:
                try:
                    converted = self._convert_with_win32(file_path, "docx")
                    if converted:
                        try:
                            doc = Document(converted)
                            text = "\n".join(p.text for p in doc.paragraphs)
                            for table in doc.tables:
                                for row in table.rows:
                                    for cell in row.cells:
                                        if cell.text.strip():
                                            text += "\n" + cell.text
                            return text
                        finally:
                            if os.path.exists(converted):
                                os.remove(converted)
                except Exception:
                    pass
            
            # 方式2: 尝试直接用 python-docx 打开
            try:
                doc = Document(file_path)
                text = "\n".join(p.text for p in doc.paragraphs)
                if text.strip():
                    return text
            except Exception:
                pass
            
            # 方式3: 提取二进制可见文本
            try:
                return self._extract_text_from_binary(file_path)
            except Exception:
                pass
            
            raise Exception("不支持旧版 .doc 格式，请将文件另存为 .docx 格式后重新上传")
        
        raise Exception(f"不支持的Word文件格式: {file_ext}")
    
    def _process_pptx(self, file_path: str) -> str:
        """处理PPT文件（支持 .pptx 和 .ppt 旧格式）"""
        file_ext = file_path.split(".")[-1].lower()
        
        # .pptx 直接用 python-pptx 处理
        if file_ext == "pptx":
            try:
                prs = Presentation(file_path)
                text = ""
                for slide_num, slide in enumerate(prs.slides, 1):
                    text += f"\n--- 第{slide_num}页 ---\n"
                    for shape in slide.shapes:
                        if hasattr(shape, "text") and shape.text.strip():
                            text += shape.text + "\n"
                        if shape.has_table:
                            for row in shape.table.rows:
                                for cell in row.cells:
                                    if cell.text.strip():
                                        text += cell.text + "\n"
                return text
            except Exception as e:
                raise Exception(f"处理PPT文件失败: {str(e)}")
        
        # .ppt 旧格式
        if file_ext == "ppt":
            # 方式1: 使用 olefile 解析 OLE2 结构（最可靠）
            if HAS_OLEFILE:
                try:
                    text = self._extract_ppt_with_olefile(file_path)
                    if text and text.strip() and len(text.strip()) > 20:
                        return text
                except Exception as e:
                    print(f"olefile 提取PPT文本失败: {e}")
            
            # 方式2: Windows COM 自动转换
            if HAS_WIN32COM:
                try:
                    converted = self._convert_with_win32(file_path, "pptx")
                    if converted:
                        try:
                            prs = Presentation(converted)
                            text = ""
                            for slide_num, slide in enumerate(prs.slides, 1):
                                text += f"\n--- 第{slide_num}页 ---\n"
                                for shape in slide.shapes:
                                    if hasattr(shape, "text") and shape.text.strip():
                                        text += shape.text + "\n"
                            return text
                        finally:
                            if os.path.exists(converted):
                                os.remove(converted)
                except Exception:
                    pass
            
            # 方式3: 尝试直接用 python-pptx 打开
            try:
                prs = Presentation(file_path)
                text = ""
                for slide in prs.slides:
                    for shape in slide.shapes:
                        if hasattr(shape, "text"):
                            text += shape.text + "\n"
                if text.strip():
                    return text
            except Exception:
                pass
            
            raise Exception("不支持旧版 .ppt 格式，请将文件另存为 .pptx 格式后重新上传")
        
        raise Exception(f"不支持的PPT文件格式: {file_ext}")
    
    def _convert_with_win32(self, file_path: str, target_ext: str) -> Optional[str]:
        """使用 Windows COM 将旧格式转换为新格式"""
        abs_path = os.path.abspath(file_path)
        output_path = abs_path.rsplit(".", 1)[0] + f"_converted.{target_ext}"
        
        try:
            if target_ext == "docx":
                word = win32.Dispatch("Word.Application")
                word.Visible = False
                doc = word.Documents.Open(abs_path)
                doc.SaveAs2(output_path, FileFormat=16)  # 16 = docx
                doc.Close()
                word.Quit()
            elif target_ext == "pptx":
                ppt = win32.Dispatch("PowerPoint.Application")
                ppt.Visible = False
                presentation = ppt.Presentations.Open(abs_path, WithWindow=False)
                presentation.SaveAs(output_path, FileFormat=24)  # 24 = pptx
                presentation.Close()
                ppt.Quit()
            
            if os.path.exists(output_path):
                return output_path
        except Exception as e:
            print(f"COM 转换失败: {e}")
            if os.path.exists(output_path):
                os.remove(output_path)
        return None
    
    def _extract_text_from_binary(self, file_path: str) -> str:
        """从二进制文件中提取可见文本（兜底方案）"""
        # 优先尝试 olefile 方式
        if HAS_OLEFILE and file_path.lower().endswith('.ppt'):
            try:
                text = self._extract_ppt_with_olefile(file_path)
                if text and text.strip():
                    return text
            except Exception:
                pass
        
        with open(file_path, "rb") as f:
            raw = f.read()
        
        for encoding in ('utf-8', 'gbk', 'gb2312', 'utf-16-le'):
            try:
                decoded = raw.decode(encoding, errors='ignore')
                cleaned = ""
                for ch in decoded:
                    if ch.isprintable() or ch in ("\n", "\r", "\t"):
                        cleaned += ch
                    elif cleaned and not cleaned.endswith("\n"):
                        cleaned += "\n"
                lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
                text_parts = [line for line in lines if len(line) >= 2]
                if len(text_parts) > 5:
                    return "\n".join(text_parts)
            except Exception:
                continue
        
        raise Exception("无法从文件中提取文本内容")
    
    def _extract_ppt_with_olefile(self, file_path: str) -> str:
        """使用 olefile 从 .ppt (OLE2) 文件中正确提取文本"""
        ole = olefile.OleFileIO(file_path)
        try:
            if not ole.exists("PowerPoint Document"):
                raise Exception("不是有效的 PowerPoint 文件")
            
            stream = ole.openstream("PowerPoint Document")
            data = stream.read()
            
            texts = []
            offset = 0
            while offset < len(data) - 8:
                rec_ver_inst = struct.unpack_from('<H', data, offset)[0]
                rec_ver = rec_ver_inst & 0x0F
                rec_type = struct.unpack_from('<H', data, offset + 2)[0]
                rec_len = struct.unpack_from('<I', data, offset + 4)[0]
                
                # 容器记录：不跳过数据，递归进入子记录
                if rec_ver == 0x0F:
                    offset += 8
                    continue
                
                # 安全检查
                if rec_len > len(data) - offset - 8 or rec_len > 50000000:
                    offset += 8
                    continue
                
                # 提取文本记录
                if rec_type in (0x0FA0, 0x0FA8) and rec_len > 0:
                    text_data = data[offset + 8:offset + 8 + rec_len]
                    text = self._decode_ppt_text(text_data, rec_type, rec_len)
                    if text and text.strip() and len(text.strip()) >= 2:
                        clean = text.strip()
                        # 过滤掉纯符号/占位符和PPT模板噪音
                        if all(c in '* \n\r\t' for c in clean):
                            pass
                        elif any(kw in clean for kw in ('マスタ', 'レベル', '書式設定')):
                            pass  # 日文PPT模板文字
                        else:
                            texts.append(clean)
                
                offset += 8 + rec_len
            
            if texts:
                return "\n".join(texts)
            raise Exception("未找到文本内容")
        finally:
            ole.close()
    
    def _decode_ppt_text(self, text_data: bytes, rec_type: int, rec_len: int) -> Optional[str]:
        """智能解码 PPT 文本记录（处理编码不一致问题）"""
        # TextCharsAtom (0x0FA8): 标准 UTF-16-LE
        if rec_type == 0x0FA8:
            try:
                return text_data.decode('utf-16-le')
            except Exception:
                return None
        
        # TextBytesAtom (0x0FA0): 理论上单字节，但很多PPT实际存储UTF-16-LE
        # 策略：同时尝试 UTF-16-LE 和 GBK，用 CJK 字符得分选最优
        candidates = []
        
        if rec_len >= 4 and rec_len % 2 == 0:
            try:
                text_u16 = text_data.decode('utf-16-le')
                cjk = sum(1 for c in text_u16 if '\u4e00' <= c <= '\u9fff')
                printable = sum(1 for c in text_u16 if c.isprintable() or c in '\n\r\t ')
                score = cjk * 3 + printable
                if printable > len(text_u16) * 0.3:
                    candidates.append((score, text_u16))
            except Exception:
                pass
        
        try:
            text_gbk = text_data.decode('gbk')
            cjk = sum(1 for c in text_gbk if '\u4e00' <= c <= '\u9fff')
            printable = sum(1 for c in text_gbk if c.isprintable() or c in '\n\r\t ')
            score = cjk * 3 + printable
            if printable > len(text_gbk) * 0.3:
                candidates.append((score, text_gbk))
        except Exception:
            pass
        
        try:
            text_u8 = text_data.decode('utf-8')
            cjk = sum(1 for c in text_u8 if '\u4e00' <= c <= '\u9fff')
            printable = sum(1 for c in text_u8 if c.isprintable() or c in '\n\r\t ')
            score = cjk * 3 + printable
            if printable > len(text_u8) * 0.3:
                candidates.append((score, text_u8))
        except Exception:
            pass
        
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
        
        return None
    
    def _process_text(self, file_path: str) -> str:
        """处理文本文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        except Exception as e:
            raise Exception(f"处理文本文件失败: {str(e)}")
    
    def _process_image(self, file_path: str) -> str:
        """处理图片文件"""
        try:
            # 打开图片
            image = Image.open(file_path)
            
            # 使用OCR提取文本
            text = f"[图片文件] {os.path.basename(file_path)}"
            if pytesseract is not None:
                try:
                    text = pytesseract.image_to_string(image, lang="chi_sim+eng")
                    if not text:
                        text = f"[图片文件] {os.path.basename(file_path)}"
                except Exception:
                    pass
            
            return text
        except Exception as e:
            raise Exception(f"处理图片文件失败: {str(e)}")
    
    def _process_video(self, file_path: str) -> str:
        """处理视频文件 - 多关键帧提取 + LLM摘要"""
        try:
            # 构建视频描述
            text = f"[视频文件] {os.path.basename(file_path)}\n"
            
            if VideoFileClip is not None:
                try:
                    # 打开视频
                    clip = VideoFileClip(file_path)
                    
                    # 获取视频信息
                    duration = clip.duration
                    fps = clip.fps
                    size = clip.size
                    
                    text += f"时长: {duration:.2f}秒\n"
                    text += f"分辨率: {size[0]}x{size[1]}\n"
                    text += f"帧率: {fps}fps\n"
                    
                    # 多关键帧提取策略
                    num_keyframes = min(5, max(1, int(duration / 30)))  # 每30秒一帧，最多5帧
                    keyframe_times = []
                    if duration > 0:
                        if num_keyframes == 1:
                            keyframe_times = [min(1.0, duration / 2)]
                        else:
                            step = duration / (num_keyframes + 1)
                            keyframe_times = [step * (i + 1) for i in range(num_keyframes)]
                    
                    frame_texts = []
                    temp_dir = os.path.dirname(file_path)
                    
                    for idx, t in enumerate(keyframe_times):
                        try:
                            thumbnail_path = os.path.join(temp_dir, f"_keyframe_{idx}.jpg")
                            clip.save_frame(thumbnail_path, t=t)
                            
                            # 对关键帧进行OCR
                            if pytesseract is not None:
                                try:
                                    image = Image.open(thumbnail_path)
                                    frame_text = pytesseract.image_to_string(image, lang="chi_sim+eng")
                                    if frame_text and frame_text.strip():
                                        timestamp = f"{int(t//60)}:{int(t%60):02d}"
                                        frame_texts.append(f"[{timestamp}] {frame_text.strip()}")
                                except Exception:
                                    pass
                            
                            # 清理临时文件
                            if os.path.exists(thumbnail_path):
                                os.remove(thumbnail_path)
                        except Exception:
                            pass
                    
                    clip.close()
                    
                    if frame_texts:
                        text += "\n关键帧文本内容:\n"
                        text += "\n".join(frame_texts) + "\n"
                    
                    # 使用LLM生成视频内容摘要
                    if frame_texts:
                        try:
                            from .llm_service import llm_service
                            summary_prompt = f"""请根据以下视频关键帧提取的文本信息，生成一段简洁的视频内容摘要（100字以内）：

视频文件: {os.path.basename(file_path)}
时长: {duration:.0f}秒
关键帧文本:
{chr(10).join(frame_texts)}

请直接输出摘要内容，不要其他说明。"""
                            summary = llm_service.chat(summary_prompt, purpose="document_summary")
                            if summary and len(summary.strip()) > 10:
                                text += f"\n视频内容摘要: {summary.strip()}\n"
                        except Exception:
                            pass
                    
                except Exception:
                    pass
            else:
                text += "视频信息需要moviepy库支持，当前未安装。\n"
            
            return text
        except Exception as e:
            raise Exception(f"处理视频文件失败: {str(e)}")
    
    def _process_audio(self, file_path: str) -> str:
        """处理音频文件"""
        try:
            # 构建音频描述
            text = f"[音频文件] {os.path.basename(file_path)}\n"
            text += "音频文件内容需要通过语音识别技术提取，当前仅提供文件信息。\n"
            
            return text
        except Exception as e:
            raise Exception(f"处理音频文件失败: {str(e)}")