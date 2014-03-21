# -*- coding: utf-8 -*-
from django import forms

class NgFormBaseMixin(object):
    def add_prefix(self, field_name):
        """
        Rewrite the model keys to use dots instead of dashes, since thats the syntax
        used in Angular models.
        """
        return self.prefix and ('%s.%s' % (self.prefix, field_name)) or field_name

class BaseCrudForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request')
        super(BaseCrudForm, self).__init__(*args, **kwargs)
