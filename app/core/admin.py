from django.contrib import admin, messages
from django.shortcuts import render, redirect

from deconfliction_service.node_utils import get_terms_with_multiple_definitions, is_any_node_present
from core.models import (ChildTermSet, SchemaLedger, Term, TermSet,
                         TransformationLedger)
from django import forms
from django.db import models
from django.urls import path, reverse
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse, HttpRequest
import xml.etree.ElementTree as ET

from core.exceptions import MissingColumnsError, MissingRowsError, TermCreationError
from core.models import (ChildTermSet, SchemaLedger, Term, TermSet, TransformationLedger)
from django_neomodel import admin as neomodel_admin
from core.models import NeoAlias, NeoContext, NeoDefinition, NeoTerm
from core.utils import run_node_creation
from deconfliction_service.views import run_deconfliction
from uuid import uuid4
import logging

from .views import export_terms_as_json, export_terms_as_xml, export_terms_as_csv, search

import pandas as pd

logger = logging.getLogger('dict_config_logger')


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField()


logger = logging.getLogger('dict_config_logger')

# Register your models here.
@admin.register(SchemaLedger)
class SchemaLedgerAdmin(admin.ModelAdmin):
    """Admin form for the SchemaLedger model"""
    list_display = ('schema_name', 'status', 'version',)
    fields = [('schema_name', 'schema_file', 'status',),
              ('major_version', 'minor_version', 'patch_version',)]

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('schema_name', 'schema_file',
                                           'major_version', 'minor_version',
                                           'patch_version')
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TransformationLedger)
class TransformationLedgerAdmin(admin.ModelAdmin):
    """Admin form for the TransformationLedger model"""
    list_display = ('id', 'source_schema', 'target_schema', 'status',)
    fields = [('source_schema', 'target_schema',),
              ('schema_mapping_file', 'status',)]

    # Override the foreign key fields to show the name and version in the
    # admin form instead of the ID
    def get_form(self, request, obj=None, **kwargs):
        form = super(TransformationLedgerAdmin, self).get_form(request,
                                                               obj,
                                                               **kwargs)
        form.base_fields['source_schema'].label_from_instance = \
            lambda obj: "{}".format(obj.iri)
        form.base_fields['target_schema'].label_from_instance = \
            lambda obj: "{}".format(obj.iri)
        return form


@admin.register(TermSet)
class TermSetAdmin(admin.ModelAdmin):
    """Admin form for the Term Set model"""
    list_display = ('iri', 'status', 'updated_by', 'modified',)
    fieldsets = (
        (None, {'fields': ('iri', 'name', 'version', 'uuid',)}),
        ('Availability', {'fields': ('status',)}),
    )
    readonly_fields = ('iri', 'updated_by', 'modified', 'uuid',)
    search_fields = ['iri', ]
    list_filter = ('status', 'name')

    def save_model(self, request, obj, form, change):
        """Overide save_model to pass along current user"""
        obj.updated_by = request.user
        return super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(childtermset=None)


@admin.register(ChildTermSet)
class ChildTermSetAdmin(TermSetAdmin):
    """Admin form for the Child Term Set model"""
    list_display = ('iri', 'status', 'parent_term_set', 'updated_by',
                    'modified',)
    fieldsets = (
        (None, {'fields': ('iri', 'name', 'uuid',)}),
        ('Availability', {'fields': ('status',)}),
        ('Parent', {'fields': ('parent_term_set',)}),
    )
    list_filter = ('status', ('parent_term_set',
                   admin.RelatedOnlyFieldListFilter))

    def get_queryset(self, request):
        return super(TermSetAdmin, self).get_queryset(request)


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    """Admin form for the Term model"""
    list_display = ('iri', 'status', 'term_set', 'updated_by',
                    'modified',)
    fieldsets = (
        (None, {'fields': ('iri', 'name', 'uuid', 'description', 'status',)}),
        ('Info', {'fields': ('data_type', 'use', 'source',)}),
        ('Connections', {'fields': ('term_set', 'mapping',)}),
        ('Updated', {'fields': ('updated_by',), })
    )
    readonly_fields = ('iri', 'updated_by', 'modified', 'uuid',)
    filter_horizontal = ('mapping',)
    search_fields = ['iri', ]
    list_filter = ('status', ('term_set', admin.RelatedOnlyFieldListFilter))

    def save_model(self, request, obj, form, change):
        """Overide save_model to pass along current user"""
        obj.updated_by = request.user
        return super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, **kwargs):
        form = super(TermAdmin, self).get_form(request, obj, **kwargs)
        if obj is not None:
            form.base_fields['mapping'].queryset = Term.objects.exclude(
                iri__startswith=obj.root_term_set())
        return form

class NeoTermAdminForm(forms.ModelForm):
    alias = forms.CharField(required=False, help_text="Enter alias")  # Custom field
    definition = forms.CharField(required=True, help_text="Enter definition")  # Custom field
    context = forms.CharField(required=False, help_text="Enter context")  # Custom field
    context_description = forms.CharField(required=False, help_text="Enter context description")  # Custom field

    class Meta:
        model = NeoTerm
        fields = ['lcvid', 'alias', 'definition', 'context', 'context_description']

class NeoTermAdmin(admin.ModelAdmin):
    form = NeoTermAdminForm
    list_display = ('lcvid', 'uid')
    exclude = ['django_id', 'uid']

    def __init__(self,*args, **kwargs):
        
        super().__init__(*args, **kwargs)
        self.model.verbose_name = 'NeoTerm'
        self.model.verbose_name_plural = 'NeoTerms'


    def save_model(self, request, obj, form, change):
        try:
            alias = form.cleaned_data['alias']
            definition = form.cleaned_data['definition']
            context = form.cleaned_data['context']
            context_description = form.cleaned_data['context_description']


            logger.info(f"Creating NeoTerm with alias: {alias}, definition: {definition}, context: {context}, context_description: {context_description}")
            if context == '' and context_description == '' and alias != '':
                definition_node = NeoDefinition.nodes.get_or_none(definition=definition)
                if definition_node:
                    messages.warning(request, 'Adding an alias without a context is not recommended.')
                    run_node_creation(alias=alias, definition=definition, context=context, context_description=context_description)
                    return
                messages.error(request, 'Adding a definition without a context is not allowed.')
                return
            run_node_creation(alias=alias, definition=definition, context=context, context_description=context_description)

            messages.success(request, 'NeoTerm saved successfully.')
            
        except Exception as e:
            logger.error('Error saving NeoTerm: {}'.format(e))
            messages.error(request, 'Error saving NeoTerm: {}'.format(e))
            return

    def delete_model(self, request, obj) -> None:
        messages.error(request, 'Deleting terms is not allowed')

    def delete_queryset(self, request, queryset):
        """Prevent bulk deletion of NeoTerm objects and show a message."""
        messages.error(request, "You cannot delete terms.")



    change_list_template = 'admin/neoterm_change_list.html'
    actions = ['export_as_json', 'export_as_xml', 'upload_csv']

    # REQUIRED_COLUMNS = [
    #     field.name.replace("_", " ").title() for field in NeoTerm._meta.get_fields()
    #     if hasattr(field, 'required') and field.required
    # ]

    REQUIRED_COLUMNS = ['Definition', 'Context', 'Context Description']
    
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('upload-csv/', self.upload_csv),
            path('admin/export-terms-json/', export_terms_as_json, name='export_terms_as_json'),
            path('admin/export-terms-xml/', export_terms_as_xml, name='export_terms_as_xml'),
            path('admin/export-terms-csv/', export_terms_as_csv, name='export_terms_as_csv')
        ]
        return my_urls + urls
    

    def upload_csv(self, request):
        logger.info('Uploading CSV file...')
        if request.method == 'POST':
            form = CSVUploadForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = form.cleaned_data['csv_file']
                try:
                    data = self.validate_csv_file(csv_file)
                    df = data['data_frame']
                    self.create_terms_from_csv(df)
                    messages.success(request, 'CSV file uploaded successfully.')
                    return HttpResponseRedirect(reverse('admin:core_neoterm_changelist'))

                except MissingColumnsError as e:
                    messages.error(request, f"Missing required columns: {', '.join(e.missing_columns)}")
                except MissingRowsError as e:
                    for row in e.missing_rows:
                        indices_message = ', '.join(map(str, row['row_indices'][:5])) + (' and more' if len(row['row_indices']) > 5 else '')
                        messages.error(request, f"Missing data in column '{row['column']}' for row {indices_message}")
                except TermCreationError as e:
                    messages.error(request, "Error creating terms from CSV file.")
                except Exception as e:
                    messages.error(request, str(e))

        else:
            form = CSVUploadForm()
        return render(request, 'upload_csv.html', {'form': form})

    def validate_csv_file(self, csv_file):
        if not csv_file.name.endswith('.csv'):
            raise ValueError('The file extension is not .csv')
        try:
            logger.info('Validating CSV file...')
            df = pd.read_csv(csv_file)
            logger.info(f'{len(df)} rows found in CSV file.')
        except pd.errors.EmptyDataError:
            raise ValueError('The CSV file is empty.')
        except pd.errors.ParserError:
            raise ValueError('The CSV file is malformed or not valid.')

        missing_columns = self.check_missing_columns(df)
        if missing_columns:
            raise MissingColumnsError(missing_columns)

        missing_rows = self.check_missing_rows(df)
        if missing_rows:
            raise MissingRowsError(missing_rows)

        return {'data_frame': df}
    
    def check_missing_columns(self, df):
        missing_columns = [col for col in NeoTermAdmin.REQUIRED_COLUMNS if col not in df.columns]
        return missing_columns

    def check_missing_rows(self, df):
        missing_rows = {}

        for index, row in df.iterrows():
            for column in NeoTermAdmin.REQUIRED_COLUMNS:
                if pd.isna(row[column]) or row[column].strip() == '':
                    if column not in missing_rows:
                        missing_rows[column] = []
                    missing_rows[column].append(index + 1)

        return [{'column': column, 'row_indices': indices} for column, indices in missing_rows.items()]

    def create_terms_from_csv(self, df):
        logger.info('Creating terms from CSV file...')
        logger.info(f'{len(df)} rows found in data frame file.')

        for index, row in df.iterrows():
            try:
                alias_value = row['Alias'] if pd.notna(row['Alias']) and row['Alias'] else None
                run_node_creation(alias=alias_value, definition=row['Definition'], context=row['Context'], context_description=row['Context Description'])
            except Exception as e:
                logger.error(f'Error creating term for index {index}: {str(e)}')
                raise TermCreationError(f'Failed to create term for row {index + 1}: {str(e)}')

        logger.info(f'{len(df)} terms created from CSV file.')

neomodel_admin.register(NeoTerm, NeoTermAdmin)

class NeoAliasAdmin(admin.ModelAdmin):
    list_display = ('alias', 'term')


neomodel_admin.register(NeoAlias, NeoAliasAdmin)

class NeoContextAdmin(admin.ModelAdmin):
    list_display = ('context', 'context_description')
    readonly_fields = ('context', 'context_description')

neomodel_admin.register(NeoContext, NeoContextAdmin)

class NeoDefinitionAdmin(admin.ModelAdmin):
    list_display = ('definition',)
    readonly_fields = ('definition',)

neomodel_admin.register(NeoDefinition, NeoDefinitionAdmin)


class Search(models.Model):
    class Meta:
        verbose_name_plural = "Search"
        managed = False 
class SearchAdmin(admin.ModelAdmin):
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('', self.admin_site.admin_view(search), name='search_view'),
        ]
        return custom_urls + urls

    def has_view_permission(self, request, obj=None):
        return True

admin.site.register(Search, SearchAdmin)