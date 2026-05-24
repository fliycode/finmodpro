"""
Chat 服务层（Service Layer）包初始化。

类比 SpringBoot：
  - services/ 目录相当于 SpringBoot 中的 service 包，存放 @Service 类。
  - 本文件显式导出了服务层的公开接口函数，便于其他模块引用。

导出的服务函数：
  - ask_question: 同步问答服务（来自 ask_service）。
  - create_chat_session: 创建会话服务（来自 session_service）。
"""

from chat.services.ask_service import ask_question
from chat.services.session_service import create_chat_session

__all__ = ["ask_question", "create_chat_session"]
