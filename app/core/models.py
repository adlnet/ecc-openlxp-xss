import json
import logging
import os
import re
import secrets
import string
from uuid import uuid4

import clamd
import magic
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django_neomodel import DjangoNode
from neomodel import StringProperty, UniqueIdProperty
from model_utils.models import TimeStampedModel

from uid.models import UIDNode, Provider, ProviderDjangoModel

from core.management.utils.xss_helper import bleach_data_to_json
from neomodel import StringProperty, BooleanProperty, RelationshipTo, RelationshipFrom, UniqueIdProperty, ArrayProperty, exceptions, FloatProperty, Relationship
from django_neomodel import DjangoNode

from typing import Tuple

logger = logging.getLogger('dict_config_logger')

data_type_matching = {
    'str': 'schema:Text',
    'int': 'schema:Number',
    'bool': 'schema:Boolean',
    'datetime': 'schema:DateTime'
}
regex_check = (r'(?!(\A( \x09\x0A\x0D\x20-\x7E # ASCII '
               r'| \xC2-\xDF # non-overlong 2-byte '
               r'| \xE0\xA0-\xBF # excluding overlongs '
               r'| \xE1-\xEC\xEE\xEF{2} # straight 3-byte '
               r'| \xED\x80-\x9F # excluding surrogates '
               r'| \xF0\x90-\xBF{2} # planes 1-3 '
               r'| \xF1-\xF3{3} # planes 4-15 '
               r'| \xF4\x80-\x8F{2} # plane 16 )*\Z))')


def validate_version(value):
    check = re.fullmatch('[0-9]*[.][0-9]*[.][0-9]*', value)
    if check is None:
        raise ValidationError(
            '%(value)s does not match the format 0.0.0',
            params={'value': value},
        )


class TermSet(TimeStampedModel):
    """Model for Termsets"""
    STATUS_CHOICES = [('published', 'published'),
                      ('retired', 'retired')]
    iri = models.SlugField(max_length=255, unique=True,
                           allow_unicode=True, primary_key=True)
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True)
    name = models.SlugField(max_length=255, allow_unicode=True)
    version = models.CharField(max_length=255, validators=[validate_version])
    status = models.CharField(max_length=255, choices=STATUS_CHOICES)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def save(self, *args, **kwargs):
        """Generate iri for item"""
        self.iri = 'xss:' + self.version + '@' + self.name
        update_fields = kwargs.get('update_fields', None)
        if update_fields:
            kwargs['update_fields'] = set(update_fields).union({'iri'})

        super().save(*args, **kwargs)

    def export(self):
        children = {kid.name: kid.export() for kid in self.children.filter(status='published')}
        terms = {term.name: term.export() for term in self.terms.filter(status='published')}
        return {**children, **terms}

    def json_ld(self):
        """Generate python representation of JSON-LD"""
        # create graph and context dicts
        graph = {}
        context = {}
        # add elements to graph and context
        graph['@id'] = 'ldss:' + self.iri
        graph['@type'] = 'rdfs:Class'
        graph['rdfs:label'] = self.name
        context['rdfs'] = 'http://www.w3.org/2000/01/rdf-schema#'
        if hasattr(self, 'childtermset'):
            graph['schema:domainIncludes'] = {
                '@id': 'ldss:' + self.childtermset.parent_term_set.iri
            }
            context['schema'] = 'https://schema.org/'
        # iterate over child term sets and collect their graphs and contexts
        children = []
        for kid in self.children.filter(status='published'):
            kid_ld = kid.json_ld()
            children.extend(kid_ld['@graph'])
            # add children's context to current context, but current has
            # higher priority
            context = {**kid_ld['@context'], **context}
        # iterate over terms and collect their graphs and contexts
        terms = []
        for term in self.terms.filter(status='published'):
            term_ld = term.json_ld()
            terms.extend(term_ld['@graph'])
            # add terms' context to current context, but current has higher
            # priority
            context = {**term_ld['@context'], **context}
        # return the graph and context
        return {'@context': context, '@graph': [graph, *children, *terms]}

    def mapped_to(self, target_root):
        """Return dict of Terms mapped to anything in target_root string"""

        # filter out children with no mapped terms
        children = {kid.name: kid.mapped_to(target_root) for kid in self.children.filter(status='published')}
        filtered_children = dict(filter(lambda kid: len(kid[1]) != 0, children.items()))

        # filter out terms that do not have a mapping
        terms = {term.name: term.mapped_to(target_root)
                 for term in self.terms.filter(status='published')}
        filtered_terms = dict(
            filter(lambda term: term[1] is not None, terms.items()))
        return {**filtered_children, **filtered_terms}


class ChildTermSet(TermSet):
    """Model for Child Termsets"""
    parent_term_set = models.ForeignKey(
        TermSet, on_delete=models.CASCADE, related_name='children')

    def save(self, *args, **kwargs):
        """Generate iri for item"""
        self.iri = self.parent_term_set.iri + '/' + self.name
        self.version = self.parent_term_set.version
        update_fields = kwargs.get('update_fields', None)
        if update_fields:
            kwargs['update_fields'] = set(update_fields).union({'iri', 'version'})

        super(TermSet, self).save(*args, **kwargs)


class Term(TimeStampedModel):
    """Model for Terms"""
    STATUS_CHOICES = [('published', 'published'),
                      ('retired', 'retired')]
    USE_CHOICES = [('Required', 'Required'),
                   ('Optional', 'Optional'),
                   ('Recommended', 'Recommended'),
                   ]
    name = models.SlugField(max_length=255, allow_unicode=True)
    description = models.TextField(null=True, blank=True)
    iri = models.SlugField(max_length=255, unique=True,
                           allow_unicode=True, primary_key=True)
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True)
    data_type = models.CharField(max_length=255, null=True, blank=True)
    use = models.CharField(max_length=255, choices=USE_CHOICES)
    source = models.CharField(max_length=255, null=True, blank=True)
    term_set = models.ForeignKey(
        TermSet, on_delete=models.CASCADE, related_name='terms')
    mapping = models.ManyToManyField('self', blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=255, choices=STATUS_CHOICES)

    def root_term_set(self):
        """Get iri of the root Term Set for the current Term"""
        if "/" in self.iri:
            return self.iri[:self.iri.index('/')]
        else:
            return self.iri[:self.iri.index('?')]

    def save(self, *args, **kwargs):
        """Generate iri for item"""
        self.iri = self.term_set.iri + '?' + self.name
        update_fields = kwargs.get('update_fields', None)
        if update_fields:
            kwargs['update_fields'] = set(update_fields).union({'iri'})

        super().save(*args, **kwargs)

    def export(self):
        """convert key attributes of the Term to a dict"""
        attrs = {}
        attrs['use'] = self.use
        if self.data_type is not None and self.data_type != '':
            attrs['data_type'] = self.data_type
        if self.source is not None and self.source != '':
            attrs['source'] = self.source
        if self.description is not None and self.description != '':
            attrs['description'] = self.description
        return {**attrs}

    def json_ld(self):
        """Generate python representation of JSON-LD"""
        # create graph and context dicts
        graph = {}
        context = {}
        # add elements to graph and context
        graph['@id'] = 'ldss:' + self.iri
        graph['@type'] = 'rdf:Property'
        if self.description is not None and len(self.description.strip()) > 0:
            graph['rdfs:comment'] = self.description
        if self.data_type is not None and len(self.data_type.strip()) > 0 and\
                self.data_type in data_type_matching:
            graph['schema:rangeIncludes'] = {
                '@id': data_type_matching[self.data_type]}
        if self.mapping.exists():
            graph['owl:equivalentProperty'] = [
                {'@id': 'ldss:' + alt.iri} for alt in self.mapping.all()]
            context['owl'] = 'http://www.w3.org/2002/07/owl#'
        graph['rdfs:label'] = self.name
        graph['schema:domainIncludes'] = {'@id': 'ldss:' + self.term_set.iri}
        context['schema'] = 'https://schema.org/'
        context['rdfs'] = 'http://www.w3.org/2000/01/rdf-schema#'
        context['rdf'] = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        # return the graph and context
        return {'@context': context, '@graph': [graph, ]}

    def path(self):
        """Get the path of the Term"""
        path = self.name
        ts = self.term_set

        # traverse the Term Sets to the root
        try:
            while ts.childtermset:
                path = ts.name + '.' + path
                ts = ts.childtermset.parent_term_set
        except ChildTermSet.DoesNotExist:
            return path

    def mapped_to(self, target_root):
        """Return path if Term is mapped to anything in target_root string"""
        target_map = self.mapping.filter(iri__startswith=target_root)
        if target_map.exists():
            return target_map.first().path()
        return None


class SchemaLedger(TimeStampedModel):
    """Model for Uploaded Schemas"""
    SCHEMA_STATUS_CHOICES = [('published', 'published'),
                             ('retired', 'retired')]

    schema_name = models.CharField(max_length=255)
    schema_iri = models.SlugField(max_length=255, unique=True,
                                  allow_unicode=True)
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True)
    schema_file = models.FileField(upload_to='schemas/',
                                   null=True,
                                   blank=True)
    term_set = models.OneToOneField(
        TermSet, on_delete=models.CASCADE, related_name='schema', null=True,
        blank=True)
    status = models.CharField(max_length=255,
                              choices=SCHEMA_STATUS_CHOICES)
    metadata = models.JSONField(blank=True, null=True,
                                help_text="auto populated from uploaded file",
                                validators=[RegexValidator(regex=regex_check,
                                                           message="Wrong "
                                                           "Format Entered")])
    version = models.CharField(max_length=255,
                               help_text="auto populated from other version "
                                         "fields")
    major_version = models.SmallIntegerField(default=0)
    minor_version = models.SmallIntegerField(default=0)
    patch_version = models.SmallIntegerField(default=0)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        # can't save 2 schemas with the same name for the same version
        constraints = [
            models.UniqueConstraint(fields=['schema_name', 'version'],
                                    name='unique_schema')
        ]

    def filename(self):
        return os.path.basename(self.schema_file.name)

    def clean(self):
        # combine the versions
        version = \
            str(self.major_version) + '.' + str(self.minor_version) \
            + '.' + str(self.patch_version)
        self.version = version

        if self.schema_file:
            # scan file for malicious payloads
            cd = clamd.ClamdUnixSocket()
            json_file = self.schema_file
            scan_results = cd.instream(json_file)['stream']
            if 'OK' not in scan_results:
                for issue_type, issue in [scan_results, ]:
                    logger.error(
                        '%s %s in xss:%s@%s',
                        issue_type, issue, self.version, self.schema_name
                    )
            # only load json if no issues found
            else:
                # rewind buffer
                json_file.seek(0)

                # generate random file name
                alphabet = string.ascii_letters + string.digits
                tmp_dir = settings.TMP_SCHEMA_DIR
                random_name = ''.join(secrets.choice(alphabet)
                                      for _ in range(8))
                full_path = tmp_dir + random_name

                json_file.open('rb')

                # write to file and use magic to check file type
                with open(full_path, 'wb') as local_file:
                    local_file.write(json_file.read())
                    local_file.flush()
                    mime_type = magic.from_file(full_path, mime=True)

                # delete file
                os.remove(full_path)
                # log issue if file isn't JSON
                if 'json' not in mime_type.lower():
                    logger.error('Invalid file type detected. Expected JSON, found %s', mime_type)  # noqa: E501
                else:
                    # rewind buffer
                    json_file.open('rt')
                    json_file.seek(0)
                    json_obj = json.load(json_file)  # deserializes it

                    # bleaching/cleaning HTML tags from request data
                    json_bleach = bleach_data_to_json(json_obj)

                    self.metadata = json_bleach
            json_file.close()
            self.schema_file = None

    def __str__(self):
        return str(self.schema_iri)

    def save(self, *args, **kwargs):
        """Generate iri for item"""
        self.schema_iri = 'xss:' + self.version + '@' + self.schema_name
        update_fields = kwargs.get('update_fields', None)
        if update_fields:
            kwargs['update_fields'] = set(update_fields).union({'iri'})

        # super().save(*args, **kwargs)
        if self.pk is None:
            super(SchemaLedger, self).save(*args, **kwargs)
        else:
            super(SchemaLedger, self).save(update_fields=['status',
                                                          'updated_by'],
                                           *args, **kwargs)


class TransformationLedger(TimeStampedModel):
    """Model for Uploaded schema transformation mappings"""
    SCHEMA_STATUS_CHOICES = [('published', 'published'),
                             ('retired', 'retired')]

    source_schema = models.ForeignKey(TermSet,
                                      on_delete=models.CASCADE,
                                      related_name='source_mapping')
    target_schema = models.ForeignKey(TermSet,
                                      on_delete=models.CASCADE,
                                      related_name='target_mapping')
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True)
    schema_mapping_file = models.FileField(upload_to='schemas/',
                                           null=True,
                                           blank=True)
    schema_mapping = \
        models.JSONField(blank=True, null=True,
                         help_text="auto populated from uploaded file",
                         validators=[RegexValidator(regex=regex_check,
                                                    message="Wrong "
                                                    "Format Entered")])
    status = models.CharField(max_length=255,
                              choices=SCHEMA_STATUS_CHOICES)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def clean(self):
        # store the contents of the file in the schema_mapping field
        if self.schema_mapping_file:
            json_file = self.schema_mapping_file
            # scan file for malicious payloads
            cd = clamd.ClamdUnixSocket()
            scan_results = cd.instream(json_file)['stream']
            if 'OK' not in scan_results:
                for issue_type, issue in [scan_results, ]:
                    logger.error(
                        '%s %s in transform %s to %s',
                        issue_type, issue, self.source_schema.iri, self.target_schema.iri  # noqa: E501
                    )
            # only load json if no issues found
            else:
                # rewind buffer
                json_file.seek(0)

                # generate random file name
                alphabet = string.ascii_letters + string.digits
                tmp_dir = settings.TMP_SCHEMA_DIR
                random_name = ''.join(secrets.choice(alphabet)
                                      for _ in range(8))
                full_path = tmp_dir + random_name

                json_file.open('rb')

                # write to file and use magic to check file type
                with open(full_path, 'wb') as local_file:
                    local_file.write(json_file.read())
                    local_file.flush()
                    mime_type = magic.from_file(full_path, mime=True)

                # delete file
                os.remove(full_path)
                # log issue if file isn't JSON
                if 'json' not in mime_type.lower():
                    logger.error('Invalid file type detected. Expected JSON, found %s', mime_type)  # noqa: E501
                else:
                    # rewind buffer
                    json_file.open('rt')
                    json_file.seek(0)
                    json_obj = json.load(json_file)  # deserializes it

                    # bleaching/cleaning HTML tags from request data
                    json_bleach = bleach_data_to_json(json_obj)

                    self.schema_mapping = json_bleach
            json_file.close()
            self.schema_mapping_file = None

class NeoTerm(DjangoNode):
    django_id = UniqueIdProperty()
    uid = StringProperty(unique_index=True)
    uid_chain = StringProperty(unique_index=True)
    lcvid = StringProperty(default="DOD-OSD-P_R-DHRA-DSSC")
    status = StringProperty(choices={'accepted':'accepted', 'rejected':'rejected', 'pending':'pending'}, default='pending')
    term = StringProperty(default="UNASSIGNED")
    deprecated = BooleanProperty(default=False)
    uid_node = RelationshipTo('UIDNode', 'HAS_UID')
    definition = RelationshipTo('NeoDefinition', 'POINTS_TO')
    context = RelationshipFrom('NeoContext', 'IS_A')
    alias = RelationshipFrom('NeoAlias', 'POINTS_TO')

    class Meta:
        app_label = 'core'
    

    @classmethod
    def create_new_term(cls, lcvid: str = None) -> 'NeoTerm':

        term_node = NeoTerm() if lcvid is None else NeoTerm(lcvid=lcvid)
        term_uid_node = UIDNode.create_node(term_node.lcvid)
        term_node.uid = term_uid_node.uid
        term_node.save()

        term_node.uid_node.connect(term_uid_node)
        term_node.save()

        default_provider_name = term_node.lcvid
        provider = ProviderDjangoModel.ensure_provider_exists(default_provider_name)
        
        provider.uid.connect(term_uid_node)
        provider.save()

        term_node.uid_chain = f"{provider.default_uid}-{term_node.uid}"
        term_node.save()

        return term_node
        
    def set_relationships(self, definition_node=None, context_node=None, alias_node=None):
        try:
            if alias_node:
                self.alias.connect(alias_node)
            if context_node:    
                self.context.connect(context_node)
            if definition_node:
                self.definition.connect(definition_node)
        except exceptions.NeomodelException as e:
            logger.error(f"NeoModel-related error while connecting relationships for term '{self.uid}': {e}")
            raise e
class NeoAlias(DjangoNode):
    django_id = UniqueIdProperty()
    alias = StringProperty(unique_index=True,required=True)
    term = RelationshipTo('NeoTerm', 'POINTS_TO')
    context = RelationshipTo('NeoContext', 'USED_IN')
    collided_definition = Relationship('NeoDefinition', 'WAS_ADDED_WITH')
    class Meta:
        app_label = 'core'
    
    @classmethod
    def get_or_create(cls, alias: str) -> Tuple['NeoAlias', bool]:
        """Retrieve an existing NeoAlias or create a new one if not found, with error handling."""
        try:
            alias_node = cls.nodes.get_or_none(alias=alias)
            
            if alias_node:
                return alias_node, False

            alias_node = NeoAlias(alias=alias)
            alias_node.save()
            return alias_node, True

        except exceptions.NeomodelException as e:
            logger.error(f"NeoModel-related error while getting or creating alias '{alias}': {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in get_or_create for alias '{alias}': {e}")
            raise e
        
    def set_relationships(self, term_node=None, context_node=None, collided_definition=None):
        try:
            if term_node:
                self.term.connect(term_node)
            if context_node:
                self.context.connect(context_node)
            if collided_definition:
                self.collided_definition.connect(collided_definition)
        except exceptions.NeomodelException as e:
            logger.error(f"NeoModel-related error while connecting relationships for alias '{self.alias}': {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error while connecting relationships for alias '{self.alias}': {e}")
            raise e
    
    def handle_collision(self, definition_node, context_node=None):
        if context_node:
            self.context.connect(context_node)
        self.collided_definition.connect(definition_node)

class NeoContext(DjangoNode):
    django_id = UniqueIdProperty()
    context = StringProperty(unique_index = True)
    context_description = RelationshipFrom('NeoContextDescription', 'RATIONALE')
    term = RelationshipTo('NeoTerm', 'IS_A')
    alias = RelationshipFrom('NeoAlias', 'USED_IN')
    definition = RelationshipFrom('NeoDefinition', 'VALID_IN' )

    class Meta:
        app_label = 'core'
    
    @classmethod
    def get_or_create(cls, context: str) -> Tuple['NeoContext', bool]: 
        try:
            context_node = cls.nodes.get_or_none(context=context)
            if context_node:
                return context_node, False
            if not context == '':
                context_node = NeoContext(context=context)
                context_node.save()
                return context_node, True
        except exceptions.NeomodelException as e:
            logger.error(f"NeoModel-related error while getting or creating context '{context}': {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in get_or_create for context '{context}': {e}")
            raise e
             
    def set_relationships(self, term_node=None, alias_node=None, definition_node=None, context_description_node=None,):
        try:
            if term_node:
                self.term.connect(term_node)
            if alias_node:
                self.alias.connect(alias_node)
            if definition_node:
                self.definition.connect(definition_node)
            if context_description_node:
                self.context_description.connect(context_description_node)
        except exceptions.NeomodelException as e:
            logger.error(f"NeoModel-related error while connecting relationships for context '{self.context}': {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error while connecting relationships for context '{self.context}': {e}")
            raise e


class NeoContextDescription(DjangoNode):
    context_description = StringProperty(required=True)
    definition = RelationshipTo('NeoDefinition', 'BASED_ON')
    context = RelationshipTo('NeoContext', 'RATIONALE')

    class Meta:
        app_label = 'core'

    @classmethod
    def get_or_create(cls, context_description: str, context_node: 'NeoContext'):
        try:
            existing = context_node.context_description.all() if context_node else []
            if existing:
                return existing[0], False
            context_description_node = cls(context_description=context_description)
            context_description_node.save()
            return context_description_node, True
        except exceptions.NeomodelException as e:
            logger.error(f"NeoModel-related error while getting or creating context_description '{context_description}': {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in get_or_create for context_description '{context_description}': {e}")
            raise e
    
    def set_relationships(self, definition_node=None, context_node=None):
        try:
            if definition_node:
                self.definition.connect(definition_node)
            if context_node:
                self.context.connect(context_node)
        except exceptions.NeomodelException as e:
            logger.error(f"NeoModel-related error while connecting relationships for context_description '{self.context_description}': {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error while connecting relationships for context_description '{self.context_description}': {e}")
            raise e

class NeoDefinition(DjangoNode):
    django_id = UniqueIdProperty()
    definition = StringProperty(required=True)
    embedding = ArrayProperty(FloatProperty(), required=False)
    rejected = BooleanProperty(default=False)
    context = RelationshipTo('NeoContext', 'VALID_IN')
    context_description = RelationshipFrom('NeoContextDescription', 'BASED_ON')
    term = Relationship('NeoTerm', 'POINTS_TO')
    collision = Relationship('NeoDefinition', 'IS_COLLIDING_WITH')
    collision_alias = Relationship('NeoAlias', 'WAS_ADDED_WITH')
    
    class Meta:
        app_label = 'core'

    @classmethod
    def get_or_create(cls, definition:str, definition_embedding=None):
        try:
            definition_node = cls.nodes.get_or_none(definition=definition)
            if definition_node:
                return definition_node, False
            definition_node = NeoDefinition(definition=definition, embedding=definition_embedding)
            definition_node.save()
            return definition_node, True
        
        except Exception as e:
            logger.error(f"Error in get for NeoDefinition '{definition}': {e}")
            raise e
    
    def get_term_node(self)-> 'NeoTerm':
        if self.term:
            logger.info(f'The data is: {self.term.single()}')
            return self.term.single()
        return None
    
    def set_relationships(self, term_node=None, context_node=None, context_description_node=None, collision=None, collision_alias=None):
        try:
            if term_node:
                self.term.connect(term_node)
            if context_node:
                self.context.connect(context_node)
            if context_description_node:
                self.context_description.connect(context_description_node)
            if collision:
                self.collision.connect(collision)
            if collision_alias:
                self.collision_alias.connect(collision_alias)
        except exceptions.NeomodelException as e:
            logger.error(f"NeoModel-related error while connecting relationships for definition '{self.definition}': {e}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error while connecting relationships for definition '{self.definition}': {e}")
            raise e