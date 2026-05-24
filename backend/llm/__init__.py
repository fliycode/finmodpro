# llm 应用包（类比 SpringBoot 中的一个 Maven 模块）
# 该 __init__.py 文件用于将 llm 目录标识为一个 Python 包，方便其他模块通过 import llm 引用其中的模型、服务、控制器等组件。
# Django 框架在启动时会自动加载每个已注册 app 的 models，因此该文件也保证了 Django 能发现此 app 的数据模型。
