"""
URL configuration for webtools project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.contrib import admin
from django.urls import path, re_path
from sumtool import views as sum_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', sum_views.index_static, name='index'),
    path('api/fs/list', sum_views.api_fs_list, name='api_fs_list'),
    path('api/sum/prepare', sum_views.api_sum_prepare, name='api_sum_prepare'),
    path('api/sum/clear', sum_views.api_sum_clear, name='api_sum_clear'),
    path('api/sum/run', sum_views.api_sum_run, name='api_sum_run'),
    path('api/sum/upload-run', sum_views.api_sum_upload_run, name='api_sum_upload_run'),
    re_path(r'^api/sum/download/(?P<filename>[^/]+)$', sum_views.api_sum_download, name='api_sum_download'),
]
