# -*- coding: utf-8 -*-
import json
from django.conf import settings
from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, HttpResponseBadRequest


def allowed_action(func):
    """
    All methods which shall be callable through a given Ajax 'action' must be
    decorated with @allowed_action. This is required for safety reasons. It
    inhibits the caller to invoke all available methods of a class.
    """
    setattr(func, 'is_allowed_action', None)
    return func


class JSONResponseMixin(object):
    """
    A mixin that dispatches POST requests containing the keyword 'action' onto
    the method with that name. It renders the returned context as JSON response.
    """
    content_type = 'application/json'

    def build_model_dict(self, obj, relations={}, fields=[]):
        """
        Builds a dictionary with fieldnames and corresponding values

        If relations is passed, it will fetch a larger json tree. e.g:
        relations={
            'owner': {'fields':('first_name', 'last_name', 'email')},
            'milestones': {},
            'posts': {},
            'members': {},
            'milestone_groups': {},
        }
        """
        if relations: relations = json.loads(relations)
        else: relations = {}

        if fields: fields = list(fields)
        else: fields = []

        serialized_data = serializers.serialize('json', [obj,], indent=4 if settings.DEBUG else 0,
            relations=relations, fields=fields, flatten=True)

        return json.loads(serialized_data)

    def dispatch(self, *args, **kwargs):
        return super(JSONResponseMixin, self).dispatch(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        action = kwargs.get('action')
        action = action and getattr(self, action, None)
        if not callable(action):
            return self._dispatch_super(request, *args, **kwargs)
        out_data = json.dumps(action(), cls=DjangoJSONEncoder)
        response = HttpResponse(out_data)
        response['Content-Type'] = 'application/json;charset=UTF-8'
        response['Cache-Control'] = 'no-cache'
        return response

    def post(self, request, *args, **kwargs):
        try:
            if not request.is_ajax():
                return self._dispatch_super(request, *args, **kwargs)
            in_data = json.loads(request.body)
            action = in_data.pop('action', kwargs.get('action'))
            handler = action and getattr(self, action, None)
            if not callable(handler):
                return self._dispatch_super(request, *args, **kwargs)
            if not hasattr(handler, 'is_allowed_action'):
                raise ValueError('Method "%s" is not decorated with @allowed_action' % action)
            out_data = json.dumps(handler(in_data), cls=DjangoJSONEncoder)
            return HttpResponse(out_data, content_type='application/json;charset=UTF-8')
        except ValueError as err:
            return HttpResponseBadRequest(err)

    def _dispatch_super(self, request, *args, **kwargs):
        base = super(JSONResponseMixin, self)
        handler = getattr(base, request.method.lower(), None)
        print handler
        if callable(handler):
            return handler(request, *args, **kwargs)
        raise ValueError('This view can not handle method %s' % request.method)
