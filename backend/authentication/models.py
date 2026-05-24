"""
认证数据模型 — User 扩展 & 密码重置 Token

Django 内置了 User 模型（对应 auth_user 表），包含 username/password/email 等基础字段。
本项目通过添加关联表来扩展 User 功能，而非替换 User 模型。

SpringBoot 类比:
  - Model ≈ @Entity 注解的 JPA 实体类
  - models.Model ≈ 基类，自动提供 .save() / .objects.filter() 等 ORM 方法
  - OneToOneField ≈ @OneToOne 映射
  - ForeignKey ≈ @ManyToOne 映射
  - class Meta.db_table ≈ @Table(name="...") 指定表名
  - __str__() ≈ toString() 方法
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

# 获取当前项目的 User 模型（Django 推荐方式，而非直接 import）
User = get_user_model()


def avatar_upload_path(instance, filename):
    """生成头像文件的上传路径。

    示例: avatars/user_42.jpg

    参数:
        instance: UserProfile 实例
        filename: 原始文件名
    返回:
        相对于 MEDIA_ROOT 的路径字符串
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    return f"avatars/user_{instance.user_id}.{ext}"


class UserProfile(models.Model):
    """用户资料扩展表 — 与内置 User 一对一关联。

    存储头像等扩展信息，不修改 Django 内置 User 表。
    on_delete=models.CASCADE: 当 User 被删除时，关联的 Profile 也一同删除。
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,     # 关联的目标模型 = User
        on_delete=models.CASCADE,     # 级联删除
        related_name="profile",       # 反向查询名: user.profile
    )
    avatar = models.ImageField(
        upload_to=avatar_upload_path,  # 上传路径生成函数
        blank=True,                    # 允许为空
    )

    class Meta:
        db_table = "auth_user_profile"  # 自定义表名

    def __str__(self):
        return f"Profile({self.user.username})"


class PasswordResetToken(models.Model):
    """密码重置 Token 模型。

    用户请求重置密码时生成一条记录，Token 原文通过邮件等方式发给用户，
    数据库中只存 SHA256 HMAC 哈希，防止数据库泄露后被直接使用。
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",  # user.password_reset_tokens.all()
    )
    # 存 Token 的哈希值而非原文（安全考虑）
    token_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)  # 创建时自动设置
    expires_at = models.DateTimeField()  # 过期时间
    used = models.BooleanField(default=False)  # 是否已被使用

    class Meta:
        db_table = "auth_password_reset_token"

    def __str__(self):
        return f"PasswordResetToken(user={self.user_id}, used={self.used})"
