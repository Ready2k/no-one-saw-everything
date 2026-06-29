"""frontend_server URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
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
from django.urls import path, re_path as url, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static

from translator import views as translator_views

urlpatterns = [
    url(r'^$', translator_views.landing, name='landing'),
    url(r'^launcher$', translator_views.launcher, name='launcher'),
    url(r'^launcher/launch$', translator_views.launch_simulation, name='launch_simulation'),
    url(r'^launcher/run/(?P<sim_code>[\w\s-]+)/$', translator_views.run_review, name='run_review'),
    url(r'^launcher/open/(?P<sim_code>[\w\s-]+)/$', translator_views.open_run_map, name='open_run_map'),
    url(r'^launcher/console/(?P<sim_code>[\w\s-]+)/$', translator_views.run_console, name='run_console'),
    url(r'^launcher/delete/(?P<sim_code>[\w\s-]+)/$', translator_views.delete_run, name='delete_run'),
    url(r'^launcher/status/(?P<sim_code>[\w\s-]+)/$', translator_views.run_status, name='run_status'),
    url(r'^launcher/stop/(?P<sim_code>[\w\s-]+)/$', translator_views.stop_run, name='stop_run'),
    url(r'^launcher/personas/(?P<sim_code>[\w\s-]+)/$', translator_views.get_personas, name='get_personas'),
    url(r'^launcher/personas/(?P<sim_code>[\w\s-]+)/(?P<persona_name>[\w\s-]+)/save/$', translator_views.save_persona, name='save_persona'),
    url(r'^simulator_home$', translator_views.home, name='home'),
    url(r'^demo/(?P<sim_code>[\w\s-]+)/(?P<step>[\w-]+)/(?P<play_speed>[\w-]+)/$', translator_views.demo, name='demo'),
    url(r'^replay/(?P<sim_code>[\w\s-]+)/(?P<step>[\w-]+)/$', translator_views.replay, name='replay'),
    url(r'^replay_persona_state/(?P<sim_code>[\w\s-]+)/(?P<step>[\w-]+)/(?P<persona_name>[\w-]+)/$', translator_views.replay_persona_state, name='replay_persona_state'),
    url(r'^persona_current_state/(?P<sim_code>[\w\s-]+)/(?P<persona_name>[\w-]+)/$', translator_views.persona_current_state, name='persona_current_state'),
    url(r'^save_home_step/$', translator_views.save_home_step, name='save_home_step'),
    url(r'^process_environment/$', translator_views.process_environment, name='process_environment'),
    url(r'^update_environment/$', translator_views.update_environment, name='update_environment'),
    url(r'^path_tester/$', translator_views.path_tester, name='path_tester'),
    url(r'^path_tester_update/$', translator_views.path_tester_update, name='path_tester_update'),
    path('admin/', admin.site.urls),
]
