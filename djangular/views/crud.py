# -*- coding: utf-8 -*-
import json

from django import http
from django.core import serializers
from django.core.exceptions import ValidationError
from django.db.models.fields import FieldDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from django.forms.models import modelform_factory
from django.http import HttpResponse
from django.views.generic import FormView
from django.conf import settings
from django.db.models import ForeignKey, DateTimeField, DateField, BooleanField

import dateutil.parser as dateparser

class NgCRUDView(FormView):
	"""
	Basic view to support default angular $resource CRUD actions on server side
	Subclass and override model_class with your model

	Optional 'pk' GET parameter must be passed when object identification is required (save to update and delete)
	"""
	model_class = None
	model_obj = None
	content_type = 'application/json'
	model_pk = None
	model_slug = None
	create_form_class = None
	update_form_class = None
	relations = {}
	extras = []
	GET = None
	request = None

	def dispatch(self, request, *args, **kwargs):
		"""
		Override dispatch to call appropriate methods:
		* $query - ng_query
		* $get - ng_get
		* $save - ng_save
		* $delete and $remove - ng_delete
		"""
		self.request = request
		self.prepare_relations_and_extras(request)

		if 'pk' in kwargs:
			self.model_pk = kwargs['pk']
		if 'slug' in kwargs:
			self.model_slug = kwargs['slug']

		self.create_model_object()

		if request.method == 'GET':
			if self.model_pk or self.model_slug:
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

	def custom_permission_check(self):
		"""
		This method is called if the basic member permission check fails.
		This can effecgively be defined by each API view that inherits from this class
		so that custom permission checks can be executed if basic member permissions fail.
		"""
		return False

	def prepare_relations_and_extras(self, request):
		"""
		Example relations definition:
		relations={
			'owner': {'fields':('first_name', 'last_name', 'email')},
			'milestones': {},
			'posts': {},
			'members': {},
			'milestone_groups': {},
		}
		"""
		# Do we have relations and extras to parse from the request object?
		if not self.relations:
			self.relations = request.GET.get('relations', {})
			if self.relations:
				self.relations = json.loads(self.relations)

		if not self.extras:
			self.extras = request.GET.get('extras', [])
			if self.extras:
				self.extras = self.extras.split(',')

		# Strip out the relations / extras params from the GET for other methods to use
		self.GET = request.GET.copy()
		if 'relations' in self.GET:
			self.GET.pop('relations')
		if 'extras' in self.GET:
			self.GET.pop('extras')

	def create_model_object(self):
		"""
		Attempts to create the local model object
		"""
		try:
			print "----", self.model_pk, self.model_slug
			if self.model_pk:
				print "a"
				self.model_obj = self.model_class.objects.get(pk=self.model_pk)
			elif self.model_slug:
				print "b"
				self.model_obj = self.model_class.objects.get(slug=self.model_slug)
		except:
			self.model_obj = None
			raise ValueError("Attempted to get an object by 'pk', but no 'pk' is present. Missing GET parameter?")

	def get_form_class(self):
		"""
		Build ModelForm from model_class
		"""
		return modelform_factory(self.model_class)

	def build_model_dict(self):
		"""
		Builds a dictionary with fieldnames and corresponding values
		"""
		if self.model_obj:
			serialized_data = serializers.serialize('json', [self.model_obj,], indent=4 if settings.DEBUG else 0,
				relations=self.relations, extras=self.extras, flatten=True)

			return json.loads(serialized_data)
		else:
			return {}

	def build_json_response(self, data):
		response = HttpResponse(json.dumps(data, cls=DjangoJSONEncoder), self.content_type)
		response['Cache-Control'] = 'no-cache'
		return response

	def get_form_kwargs(self):
		kwargs = super(NgCRUDView, self).get_form_kwargs()
		# Since angular sends data in JSON rather than as POST parameters, the default data (request.POST)
		# is replaced with request.body that contains JSON encoded data
		if self.request.POST or self.request.FILES:
			pass
		else:
			kwargs['data'] = json.loads(self.request.body)

		kwargs['request'] = self.request

		if self.model_pk:
			kwargs['instance'] = self.model_obj
		return kwargs

	def get_query(self, **query_attrs):
		"""
		Get query to use in ng_query
		Allows for easier overriding
		"""
		return self.model_class.objects.filter(**query_attrs)

	def ng_query(self, request, *args, **kwargs):
		"""
		Used when angular's query() method is called
		Build an array of all objects, return json response
		"""
		objects = []

		query_attrs = dict([(param, val) for param, val in self.GET.iteritems() if val])
		for obj in self.get_query(**query_attrs):
			objects.append(self.build_model_dict(obj))
		return self.build_json_response(objects)

	def ng_get(self, request, *args, **kwargs):
		"""
		Used when angular's get() method is called
		Returns a JSON response of a single object dictionary
		"""
		data = self.build_model_dict()[0]
		return self.build_json_response(data)

	def ng_save(self, request, *args, **kwargs):
		"""
		Called on $save()
		Use modelform to save new object or modify an existing one
		"""
		if self.create_form_class:
			form = self.get_form(self.create_form_class)
		else:
			form = self.get_form(self.get_form_class())
		if form.is_valid():
			obj = form.save(commit=False)
			obj.save(request=request)
			return self.build_json_response(self.build_model_dict(obj))
		else:
			print form.errors
		raise ValidationError("Form not valid", form.errors)

	def ng_update(self, request, *args, **kwargs):
		"""
		Called on $patch() or $put()
		As patch only sends the fields that have changed, we can be more focused here and
		only update the fields being passed.
		Each post param should be the field name, followed by its new value. In the case of
		updating M2M relationships prefix the field name with either m2m-add- or m2m-remove-
		"""
		obj = self.model_obj

		# Handle the standard field updates on this model
		field_changed = False
		for key, value in self.GET.iteritems():
			if not key.startswith("m2m-"):
				try:
					field_object, model, direct, m2m = obj._meta.get_field_by_name(key)
					if isinstance(field_object, ForeignKey):
						key = "%s_id" % key
					elif isinstance(field_object, DateTimeField):
						if value == '0' or value == 0:
							value = None
						else:
							value = dateparser.parse(value, dayfirst=True)
					elif isinstance(field_object, DateField):
						if value == '0' or value == 0:
							value = None
						else:
							value = dateparser.parse(value, dayfirst=True).date()
					elif isinstance(field_object, BooleanField):
						value = value in ['true', '1', 't', 'y', 'yes']

					if hasattr(obj, key):
						setattr(obj, key, value)
						field_changed = True
				except FieldDoesNotExist:
					pass

		if field_changed:
			obj.save(request=request)

		# Now that we've saved the model, lets process any m2m updates
		for key, value in self.GET.iteritems():
			if key.startswith("m2m-add"):
				update_type = "m2m-add"
			elif key.startswith("m2m-delete"):
				update_type = "m2m-delete"
			else:
				update_type = None
			if update_type:
				field_name = key.replace("%s-"%update_type, '')
				m2m = getattr(obj, field_name)
				if m2m and update_type == "m2m-add":
					m2m.add(value)
				elif m2m and update_type == "m2m-delete":
					m2m.remove(value)

		return self.build_json_response(self.build_model_dict(obj)[0])

	def ng_delete(self, request, *args, **kwargs):
		"""
		Delete object and return it's data in JSON encoding
		"""
		obj = self.model_obj
		obj.delete()
		#return self.build_json_response(self.build_model_dict(obj))
		return self.build_json_response({})
