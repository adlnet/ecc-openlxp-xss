from django.urls import path
from . import views
from .views import export_to_postman
from .views import generate_report
from .views import report_generated_uids, api_generate_uid

app_name = 'uid'

urlpatterns = [
    path('generate-uid/', views.generate_uid_node, name='generate_uid'),
    path('create-provider/', views.create_provider, name='create_provider'),
    # path('create-lcvterm/', views.create_lcvterm, name='create_lcvterm'),
    path('success/', views.success_view, name='success'),
    path('export/<str:uid>/', export_to_postman, name='export_to_postman'),
    path('report/<str:echelon_level>/', generate_report, name='generate_report'),

    path('api/log', report_generated_uids, name='uid-generated'),
    path('api/generate', api_generate_uid, name='uid-generated'),
    # path('create_alias/', views.create_alias, name='create_alias'),
    
    # path('api/uid-repo/', UIDRepoViewSet.as_view({'get': 'list'}), name='uid-repo'),
    # path('api/uid/all', UIDTermViewSet.as_view({'get': 'list'}), name='uid-all'),
]
