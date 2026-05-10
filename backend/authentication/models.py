from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models


User = get_user_model()


def avatar_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    return f"avatars/user_{instance.user_id}.{ext}"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True)

    class Meta:
        db_table = "auth_user_profile"

    def __str__(self):
        return f"Profile({self.user.username})"
