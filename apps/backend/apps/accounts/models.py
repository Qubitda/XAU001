from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from apps.common.models import TimestampedModel


class UserManager(BaseUserManager["User"]):
    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError("E-posta adresi zorunludur.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email=email, password=password, **extra_fields)


class User(TimestampedModel, AbstractBaseUser, PermissionsMixin):
    """
    Platform authentication identity — strictly decoupled from Customer and Organization.
    A single User may hold memberships across multiple Organizations with distinct roles.
    """

    email = models.EmailField(unique=True, db_index=True)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=32, blank=True, default="")
    email_verified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "accounts_user"
        ordering = ["email"]

    def __str__(self) -> str:
        return f"{self.full_name} <{self.email}>"
