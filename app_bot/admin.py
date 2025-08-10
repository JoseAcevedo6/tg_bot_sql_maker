from django.apps import apps
from django.contrib import admin
from django.contrib.admin.exceptions import AlreadyRegistered

from .models import Course, User


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin[Course]):
    list_display = [field.name for field in Course._meta.fields]
    list_filter = ["is_active"]


@admin.register(User)
class UserAdmin(admin.ModelAdmin[User]):
    list_display = [field.name for field in User._meta.fields]
    list_filter = ["is_teacher"]


for model in apps.get_app_config(__package__).get_models():
    try:
        attrs = {"list_display": [field.name for field in model._meta.fields]}
        admin_class = type(f"{model.__name__}Admin", (admin.ModelAdmin,), attrs)
        admin.site.register(model, admin_class)
    except AlreadyRegistered:
        pass


# Solo para visualizar migraciones en el admin
# from django.db import models

# class MigrationRecord(models.Model):
#     app = models.CharField(max_length=255)
#     name = models.CharField(max_length=255)
#     applied = models.DateTimeField()

#     class Meta:
#         managed = False
#         db_table = "django_migrations"
#         verbose_name = "Migration"
#         verbose_name_plural = "Migrations"

# @admin.register(MigrationRecord)
# class MigrationRecordAdmin(admin.ModelAdmin):
#     list_display = ("app", "name", "applied")
#     search_fields = ("app", "name")
#     ordering = ("-applied",)
