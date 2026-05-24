"""
RBAC 服务包 — 业务逻辑层模块。

此文件标记 `rbac.services` 为一个 Python 包，使其子模块（如 rbac_service、
authz_service、profile_stats_service）可以被正常 import。

类比 Spring Boot: 相当于 `@Service` 类所在的包目录，此 __init__.py 是包声明文件，
    本身不包含业务代码（Service 的具体实现位于同目录下的各个子模块中）。
"""
