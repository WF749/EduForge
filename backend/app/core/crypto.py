"""加密工具类

说明：
- API Key 需要加密落库（SQLite），并且容器/服务重启后仍能解密。
- 这里优先读取环境变量的密钥；若未提供，则在项目数据目录生成并持久化一个密钥文件。
"""

import os
from base64 import b64decode, b64encode
from pathlib import Path
from typing import Optional

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

class CryptoUtils:
    """加密工具类"""
    
    def __init__(self):
        """初始化加密工具"""
        # 生成或获取密钥
        self.key = self._get_or_generate_key()
    
    def _get_or_generate_key(self):
        """获取或生成密钥"""
        # 1) 优先从环境变量获取
        # - ENCRYPTION_KEY_HEX：64位hex字符串（推荐）
        # - ENCRYPTION_KEY：任意字符串（将按UTF-8取前32字节/补齐）
        key_hex = os.getenv("ENCRYPTION_KEY_HEX")
        if key_hex:
            try:
                raw = bytes.fromhex(key_hex.strip())
                if len(raw) == 32:
                    return raw
            except Exception:
                pass

        key = os.getenv("ENCRYPTION_KEY")
        if key:
            raw = key.encode("utf-8")
            return raw.ljust(32, b"\0")[:32]

        # 2) 从持久化文件读取（确保重启不丢）
        # 数据目录放在 backend/ 下面，docker-compose 挂载时也更直观
        base_dir = Path(__file__).resolve().parent.parent.parent  # backend/
        data_dir = base_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        key_file = data_dir / "encryption_key.hex"

        if key_file.exists():
            try:
                raw = bytes.fromhex(key_file.read_text(encoding="utf-8").strip())
                if len(raw) == 32:
                    return raw
            except Exception:
                # 文件损坏则继续生成新密钥
                pass

        # 3) 生成新密钥并写入文件
        raw = os.urandom(32)
        key_file.write_text(raw.hex(), encoding="utf-8")
        return raw
    
    def encrypt(self, plaintext: Optional[str]):
        """加密文本"""
        if not plaintext:
            return None
        
        # 生成随机IV
        iv = os.urandom(16)
        
        # 创建加密器
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        
        # 填充数据（PKCS#7）
        # 注意：padding 必须按【字节】计算。原实现用 len(plaintext)（字符数）算，
        # 再对结果 .encode()，中文等非 ASCII 字符会导致字节长度与字符数不一致，
        # 解密时报 "not a multiple of the block length" 直接崩溃。
        data = plaintext.encode("utf-8")
        padding_length = 16 - (len(data) % 16)
        padded_plaintext = data + (bytes([padding_length]) * padding_length)

        # 加密
        ciphertext = encryptor.update(padded_plaintext) + encryptor.finalize()
        
        # 返回IV和密文的Base64编码
        return b64encode(iv + ciphertext).decode()
    
    def decrypt(self, ciphertext: Optional[str]):
        """解密文本"""
        # 空值返回空串而非 None：保证 encrypt/decrypt 往返一致，
        # 且下游可直接 .strip()，避免 "NoneType has no attribute strip" 崩溃
        if not ciphertext:
            return ""

        try:
            # 解码Base64
            data = b64decode(ciphertext.encode())
            
            # 提取IV和密文
            iv = data[:16]
            ciphertext = data[16:]
            
            # 创建解密器
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.CBC(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # 解密
            padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            # 移除填充
            padding_length = padded_plaintext[-1]
            if padding_length < 1 or padding_length > 16:
                return None
            plaintext = padded_plaintext[:-padding_length].decode("utf-8", errors="strict")
            
            return plaintext
        except Exception:
            # 如果解密失败，返回None
            return None
    
    def mask_api_key(self, api_key):
        """掩码API Key"""
        if not api_key:
            return ""
        
        # 保留前2位和后4位
        if len(api_key) <= 6:
            return api_key
        
        return api_key[:2] + "****" + api_key[-4:]

# 实例化加密工具
crypto_utils = CryptoUtils()
