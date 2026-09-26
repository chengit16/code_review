"""加密持久化 webhook 与飞书凭据，数据库只保存密文。"""

from __future__ import annotations

from cryptography.fernet import Fernet


class SecretBox:
    """封装应用主密钥，避免加解密逻辑分散到路由与 Worker。"""

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode("ascii"))

    def encrypt(self, value: str) -> str:
        """加密非空的项目凭据。"""

        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        """只在调用外部服务或验证 webhook 时解密。"""

        return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
