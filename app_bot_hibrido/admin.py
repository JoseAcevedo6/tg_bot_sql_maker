from django.contrib import admin

from .models import *


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Client._meta.fields]
    pass


@admin.register(Context)
class ContextAdmin(admin.ModelAdmin):
    pass


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Course._meta.fields]
    list_filter = ['is_active']
    pass


@admin.register(DatabaseDriver)
class DatabaseDriverAdmin(admin.ModelAdmin):
    pass


@admin.register(ExternalDatabase)
class ExternalDatabaseAdmin(admin.ModelAdmin):
    pass


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = [field.name for field in User._meta.fields]
    list_filter = ['is_teacher']
    pass
