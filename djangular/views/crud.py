# -*- coding: utf-8 -*-
import json

from django.core import serializers
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import modelform_factory
from django.http import HttpResponse
from django.views.generic import FormView
from django.conf import settings


class NgCRUDView(FormView):
	"""
	Basic view to support default angular $resource CRUD actions on server side
	Subclass and override model_class with your model

	Optional 'pk' GET parameter must be passed when object identification is required (save to update and delete)
	"""
	model_class = None
	content_type = 'application/json'
	model_pk = None

	def dispatch(self, request, *args, **kwargs):
		"""
		Override dispatch to call appropriate methods:
		* $query - ng_query
		* $get - ng_get
		* $save - ng_save
		* $delete and $remove - ng_delete
		"""
		if 'pk' in kwargs:
			self.model_pk = kwargs['pk']
		if request.method == 'GET':
			if self.model_pk:
				return self.ng_get(request, *args, **kwargs)
			return self.ng_query(request, *args, **kwargs)
		elif request.method == 'POST':
			return self.ng_save(request, *args, **kwargs)
		elif request.method == 'PUT':
			return self.ng_update(request, *args, **kwargs)
		elif request.method == 'PATCH':
			return self.ng_update(request, *args, **kwargs)
		elif request.method == 'DELETE':
			return self.ng_delete(request, *args, **kwargs)
		raise ValueError('This view can not handle method %s' % request.method)

	def get_form_class(self):
		"""
		Build ModelForm from model_class
		"""
		return modelform_factory(self.model_class)

	def build_model_dict(self, obj, relations={}):
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
		if relations:
			relations = json.loads(relations)
		else:
			relations = {}

		serialized_data = serializers.serialize('json', [obj,], indent=4 if settings.DEBUG else 0,
			relations=relations, flatten=True)

		return json.loads(serialized_data)

	def build_json_response(self, data):
		response = HttpResponse(json.dumps(data, cls=DjangoJSONEncoder), self.content_type)
		response['Cache-Control'] = 'no-cache'
		return response

	def get_form_kwargs(self):
		kwargs = super(NgCRUDView, self).get_form_kwargs()
		# Since angular sends data in JSON rather than as POST parameters, the default data (request.POST)
		# is replaced with request.body that contains JSON encoded data
		kwargs['data'] = json.loads(self.request.body)
		if self.model_pk:
			kwargs['instance'] = self.get_object()
		return kwargs

	def get_object(self):
		if self.model_pk:
			return self.model_class.objects.get(pk=self.model_pk)
		raise ValueError("Attempted to get an object by 'pk', but no 'pk' is present. Missing GET parameter?")

	def get_query(self):
		"""
		Get query to use in ng_query
		Allows for easier overriding
		"""
		return self.model_class.objects.all()

	def ng_query(self, request, *args, **kwargs):
		"""
		Used when angular's query() method is called
		Build an array of all objects, return json response
		"""
		objects = []
		for obj in self.get_query():
			objects.append(self.build_model_dict(obj))
		return self.build_json_response(objects)

	def ng_get(self, request, *args, **kwargs):
		"""
		Used when angular's get() method is called
		Returns a JSON response of a single object dictionary
		"""
		relations = request.GET.get('relations', None)
		data = self.build_model_dict(self.get_object(), relations)[0]
		return self.build_json_response(data)

	def ng_save(self, request, *args, **kwargs):
		"""
		Called on $save()
		Use modelform to save new object or modify an existing one
		"""
		form = self.get_form(self.get_form_class())
		if form.is_valid():
			obj = form.save()
			return self.build_json_response(self.build_model_dict(obj))
		else:
			print form.errors
		raise ValidationError("Form not valid", form.errors)

	def ng_update(self, request, *args, **kwargs):
		"""
		Called on $patch() or $put()
		As patch only sends the fields that have changed, we can be more focused here and
		only update the fields being passed
		"""
		obj = self.get_object()

		for key, value in request.GET.iteritems():
			if hasattr(obj, key) and value != '':
				setattr(obj, key, value)

		obj.save(request=request)
		return self.build_json_response(self.build_model_dict(obj))

	def ng_delete(self, request, *args, **kwargs):
		"""
		Delete object and return it's data in JSON encoding
		"""
		obj = self.get_object()
		obj.delete()
		return self.build_json_response(self.build_model_dict(obj))