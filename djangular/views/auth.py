# -*- coding: utf-8 -*-
import json

from django.core import serializers
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import modelform_factory
from django.http import HttpResponse
from django.views.generic import FormView, View
from django.conf import settings
from django.db.models import ForeignKey, DateTimeField

import dateutil.parser as dateparser

from mixins import JSONResponseMixin, allowed_action

class NgLoggedInUserView(JSONResponseMixin, View):

    @allowed_action
    def get_data(self):
        # Returns the logged in user
        user = self.request.user if self.request.user.is_authenticated() else None
        if user:
            # Define the relations / fields you want returned, in your AngularJS app
            relations = self.request.GET.get('relations', None)
            fields = self.request.GET.getlist('fields', [])
            data = self.build_model_dict(user, relations, fields)[0]
            return data
        else:
            return {}
