from django.contrib import admin
from django.forms import ModelForm
from django.http import HttpRequest
from .models import Provider, UIDNode, UIDRequestNode
# from .models import Provider, LCVTerm
from .models import ProviderDjangoModel, LCVTermDjangoModel, UIDRequestToken
# from .models import UIDCounterDjangoModel  # Import the Django model
#from .models import LastGeneratedUID
from uuid import uuid4

#@admin.register(LastGeneratedUID)
#class LastGeneratedUIDAdmin(admin.ModelAdmin):
#    list_display = ('uid')

# # Admin registration for UIDCounterDjangoModel
# @admin.register(UIDCounterDjangoModel)
# class UIDCounterAdmin(admin.ModelAdmin):
#     list_display = ('id', 'counter_value')
#     search_fields = ('id',)

class ProviderAdmin(admin.ModelAdmin):
    list_display = ('name', )
    search_fields = ('name', )

class LCVTermAdmin(admin.ModelAdmin):
    list_display = ('provider_name', 'term', 'echelon', 'structure')
    search_fields = ('provider_name', 'term', 'echelon', 'structure')

class UIDRequestAdmin(admin.ModelAdmin):
    list_display = ('provider_name', 'token', 'uid', 'uid_chain', )
    search_fields = ('provider_name', 'token', 'uid', 'uid_chain', )
    exclude = ('token', 'echelon', 'termset', 'uid', 'uid_chain' )

admin.site.register(ProviderDjangoModel, ProviderAdmin)
admin.site.register(LCVTermDjangoModel, LCVTermAdmin)
admin.site.register(UIDRequestToken, UIDRequestAdmin)
