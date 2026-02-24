"""openlxp_xss_project URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, re_path

urlpatterns = [
    re_path('admin/doc/', include('django.contrib.admindocs.urls')),
    # url('', include('openlxp_authentication.urls')),
    re_path('admin/', admin.site.urls),
    re_path('api/', include('api.urls')),
    re_path('api/auth/', include('users.urls')),
    re_path('health/', include('health_check.urls'),
            name='health_check')
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
