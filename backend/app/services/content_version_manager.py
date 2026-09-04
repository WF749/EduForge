"""内容版本管理服务 - 管理生成资料的修改、版本控制和内容回流"""
import json
import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from .. import paths
from .. import knowledge_store


class ContentVersion:
    """内容版本数据类"""
    def __init__(self, version_id: str, content: str, timestamp: float, 
                 author: str = "system", note: str = ""):
        self.version_id = version_id
        self.content = content
        self.timestamp = timestamp
        self.author = author
        self.note = note


class ContentItem:
    """内容项数据类"""
    def __init__(self, item_id: str, content_type: str, title: str):
        self.item_id = item_id
        self.content_type = content_type  # ppt, lesson_plan, animation, etc.
        self.title = title
        self.versions: List[ContentVersion] = []
        self.current_version: Optional[str] = None
        self.created_at = datetime.now().timestamp()
        self.updated_at = self.created_at
        self.tags: List[str] = []
        self.metadata: Dict[str, Any] = {}


class ContentVersionManager:
    """内容版本管理器"""
    
    def __init__(self):
        self.version_dir = Path(paths.DATA_DIR) / "content_versions"
        self.version_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.version_dir / "index.json"
        self.items: Dict[str, ContentItem] = {}
        self._load_index()
    
    def _load_index(self):
        """加载索引文件"""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item_id, item_data in data.items():
                        item = ContentItem(
                            item_id=item_id,
                            content_type=item_data.get("content_type", "unknown"),
                            title=item_data.get("title", "未命名")
                        )
                        item.created_at = item_data.get("created_at", item.created_at)
                        item.updated_at = item_data.get("updated_at", item.updated_at)
                        item.tags = item_data.get("tags", [])
                        item.metadata = item_data.get("metadata", {})
                        item.current_version = item_data.get("current_version")
                        
                        # 加载版本信息
                        versions_data = item_data.get("versions", [])
                        for v_data in versions_data:
                            version = ContentVersion(
                                version_id=v_data.get("version_id", ""),
                                content="",  # 实际内容存在单独文件中
                                timestamp=v_data.get("timestamp", 0),
                                author=v_data.get("author", "system"),
                                note=v_data.get("note", "")
                            )
                            item.versions.append(version)
                        
                        self.items[item_id] = item
            except Exception as e:
                print(f"加载内容索引失败: {e}")
    
    def _save_index(self):
        """保存索引文件"""
        data = {}
        for item_id, item in self.items.items():
            data[item_id] = {
                "item_id": item.item_id,
                "content_type": item.content_type,
                "title": item.title,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
                "tags": item.tags,
                "metadata": item.metadata,
                "current_version": item.current_version,
                "versions": [
                    {
                        "version_id": v.version_id,
                        "timestamp": v.timestamp,
                        "author": v.author,
                        "note": v.note
                    } for v in item.versions
                ]
            }
        
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _get_item_dir(self, item_id: str) -> Path:
        """获取内容项的目录"""
        return self.version_dir / item_id
    
    def _get_version_file(self, item_id: str, version_id: str) -> Path:
        """获取版本文件路径"""
        return self._get_item_dir(item_id) / f"{version_id}.json"
    
    def create_item(self, content_type: str, title: str, content: str, 
                    tags: List[str] = None, metadata: Dict[str, Any] = None) -> str:
        """创建新的内容项
        
        Returns:
            内容项ID
        """
        import uuid
        item_id = str(uuid.uuid4())
        
        item = ContentItem(
            item_id=item_id,
            content_type=content_type,
            title=title
        )
        item.tags = tags or []
        item.metadata = metadata or {}
        
        # 创建目录
        self._get_item_dir(item_id).mkdir(parents=True, exist_ok=True)
        
        # 创建第一个版本
        version_id = "v1"
        self._save_version(item, version_id, content, "system", "初始版本")
        
        self.items[item_id] = item
        self._save_index()
        
        return item_id
    
    def _save_version(self, item: ContentItem, version_id: str, content: str, 
                      author: str, note: str):
        """保存版本"""
        version = ContentVersion(
            version_id=version_id,
            content=content,
            timestamp=datetime.now().timestamp(),
            author=author,
            note=note
        )
        item.versions.append(version)
        item.current_version = version_id
        item.updated_at = version.timestamp
        
        # 保存内容到文件
        version_file = self._get_version_file(item.item_id, version_id)
        with open(version_file, "w", encoding="utf-8") as f:
            json.dump({
                "content": content,
                "metadata": item.metadata
            }, f, ensure_ascii=False, indent=2)
    
    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """获取内容项信息"""
        item = self.items.get(item_id)
        if not item:
            return None
        
        return {
            "item_id": item.item_id,
            "content_type": item.content_type,
            "title": item.title,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "tags": item.tags,
            "metadata": item.metadata,
            "current_version": item.current_version,
            "versions_count": len(item.versions)
        }
    
    def get_content(self, item_id: str, version_id: str = None) -> Optional[str]:
        """获取内容"""
        item = self.items.get(item_id)
        if not item:
            return None
        
        version_id = version_id or item.current_version
        if not version_id:
            return None
        
        version_file = self._get_version_file(item_id, version_id)
        if not version_file.exists():
            return None
        
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("content", "")
        except Exception:
            return None
    
    def update_content(self, item_id: str, content: str, author: str = "user", 
                       note: str = "", auto_backflow: bool = True) -> bool:
        """更新内容（创建新版本）
        
        Args:
            item_id: 内容项ID
            content: 新内容
            author: 修改者
            note: 修改说明
            auto_backflow: 是否自动回流到知识库
            
        Returns:
            是否成功
        """
        item = self.items.get(item_id)
        if not item:
            return False
        
        # 生成新版本号
        new_version_num = len(item.versions) + 1
        version_id = f"v{new_version_num}"
        
        # 保存新版本
        self._save_version(item, version_id, content, author, note)
        self._save_index()
        
        # 自动回流到知识库
        if auto_backflow:
            self._backflow_to_knowledge_base(item, content)
        
        return True
    
    def _backflow_to_knowledge_base(self, item: ContentItem, content: str):
        """将内容回流到知识库"""
        try:
            # 构建文档
            doc_title = f"{item.title}（{item.content_type}）"
            doc_content = f"文档类型：{item.content_type}\n标题：{item.title}\n\n{content}"
            
            # 添加到知识库
            # 先检查是否已存在
            existing_docs = knowledge_store.list_documents(limit=100)
            existing_id = None
            for doc in existing_docs:
                if doc.get("title") == doc_title:
                    existing_id = doc.get("id")
                    break
            
            if existing_id:
                # 更新现有文档
                knowledge_store.delete_document(existing_id)
            
            # 添加新文档
            knowledge_store.add_document(
                title=doc_title,
                content=doc_content,
                source=f"generated_{item.content_type}",
                tags=item.tags + ["回流内容", item.content_type]
            )
            
            print(f"内容已回流到知识库: {doc_title}")
        except Exception as e:
            print(f"内容回流失败: {e}")
    
    def list_items(self, content_type: str = None, limit: int = 50, 
                   offset: int = 0) -> Dict[str, Any]:
        """列出内容项"""
        items = list(self.items.values())
        
        if content_type:
            items = [item for item in items if item.content_type == content_type]
        
        # 按更新时间排序
        items.sort(key=lambda x: x.updated_at, reverse=True)
        
        total = len(items)
        items = items[offset:offset + limit]
        
        return {
            "total": total,
            "items": [self.get_item(item.item_id) for item in items]
        }
    
    def get_version_history(self, item_id: str) -> List[Dict[str, Any]]:
        """获取版本历史"""
        item = self.items.get(item_id)
        if not item:
            return []
        
        history = []
        for version in item.versions:
            history.append({
                "version_id": version.version_id,
                "timestamp": version.timestamp,
                "author": version.author,
                "note": version.note,
                "is_current": version.version_id == item.current_version
            })
        
        return history
    
    def revert_to_version(self, item_id: str, version_id: str) -> bool:
        """回滚到指定版本"""
        item = self.items.get(item_id)
        if not item:
            return False
        
        # 检查版本是否存在
        version_file = self._get_version_file(item_id, version_id)
        if not version_file.exists():
            return False
        
        # 创建新版本（回滚操作也记录为一个新版本）
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                old_content = data.get("content", "")
            
            new_version_num = len(item.versions) + 1
            new_version_id = f"v{new_version_num}"
            self._save_version(
                item, new_version_id, old_content, "system", 
                f"回滚到版本 {version_id}"
            )
            self._save_index()
            
            # 回流到知识库
            self._backflow_to_knowledge_base(item, old_content)
            
            return True
        except Exception as e:
            print(f"回滚失败: {e}")
            return False
    
    def delete_item(self, item_id: str) -> bool:
        """删除内容项"""
        if item_id not in self.items:
            return False
        
        # 删除目录
        item_dir = self._get_item_dir(item_id)
        if item_dir.exists():
            shutil.rmtree(item_dir)
        
        del self.items[item_id]
        self._save_index()
        
        return True
    
    def export_content(self, item_id: str, version_id: str = None, 
                       format: str = "txt") -> Optional[Path]:
        """导出内容"""
        content = self.get_content(item_id, version_id)
        if not content:
            return None
        
        item = self.items.get(item_id)
        if not item:
            return None
        
        export_dir = self.version_dir / "exports"
        export_dir.mkdir(exist_ok=True)
        
        filename = f"{item.title}_{version_id or item.current_version}.{format}"
        # 清理文件名中的非法字符
        filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
        export_file = export_dir / filename
        
        with open(export_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        return export_file


# 全局实例
content_version_manager = ContentVersionManager()
