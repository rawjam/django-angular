from django.conf.urls import patterns, include, url
from django.contrib.auth.decorators import login_required, permission_required
from django.conf import settings
from django.views.generic import TemplateView

from views.auth import NgLoggedInUserView
urlpatterns = patterns('',
    url(r"^logged-in-user/$", NgLoggedInUserView.as_view(), {'action': 'get_data'}, name="ng_logged_in_user_view"),
)
