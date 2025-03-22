from django.contrib import admin

from .models import *


@admin.register(Client)
class QuoteCompanyQuoteAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Client._meta.fields]
    pass

@admin.register(Context)
class QuoteCompanyQuoteAdmin(admin.ModelAdmin):
    pass

@admin.register(Course)
class QuoteCompanyQuoteAdmin(admin.ModelAdmin):
    list_display = [field.name for field in Course._meta.fields]
    list_filter = ['is_active']
    pass

@admin.register(User)
class QuoteCompanyQuoteAdmin(admin.ModelAdmin):
    list_display = [field.name for field in User._meta.fields]
    list_filter = ['is_teacher']
    pass
