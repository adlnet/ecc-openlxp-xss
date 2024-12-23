from elasticsearch import Elasticsearch, exceptions
from sentence_transformers import SentenceTransformer
import logging
import numpy as np

logger = logging.getLogger('dict_config_logger')




def handle_unique_case(self, obj, alias, definition, context, context_description, deconfliction_response, es_client):
    # Ensure the term has a unique identifier
    if obj.uid is None:
        obj.uid = str(uuid4())

    # Index the definition in Elasticsearch
    es_client.index_document(
        index_name='xss_index',
        uid=obj.uid,
        definition_embedding=deconfliction_response['definition_embedding']
    )

    # Create or retrieve nodes
    alias_node = self.create_alias_node(alias)
    definition_node = self.create_definition_node(definition)
    context_node = self.create_context_node(context)
    context_description_node = self.create_context_description_node(context_description)
    obj.save()

    # Connect the nodes
    self.connect_nodes_unique_case(obj, alias_node, definition_node, context_node, context_description_node)

def handle_duplication_case(self, request, alias, context, deconfliction_response):
    existing_term = self.get_existing_term(deconfliction_response)
    messages.error(request, 'Duplicate definition detected. Creating alias if applicable.')

    alias_node, alias_created = NeoAlias.get_or_create(alias=alias)
    context_node, context_created = NeoContext.get_or_create(context=context)

    # Connect the nodes
    self.connect_nodes_duplication_case(existing_term, alias_node, context_node, alias_created, context_created)

    messages.info(request, 'Alias created for term: {}'.format(existing_term))

def handle_collision_case(self, request, obj):
    messages.error(request, 'Collision detected. Logging the collision and not saving the term.')
    logger.error('Collision detected for term: {}'.format(obj))

def create_alias_node(self, alias):
    alias_node, _ = NeoAlias.get_or_create(alias=alias)
    return alias_node

def create_definition_node(self, definition):
    definition_node = NeoDefinition(definition=definition)
    definition_node.save()
    return definition_node

def create_context_node(self, context):
    context_node, _ = NeoContext.get_or_create(context=context)
    return context_node

def create_context_description_node(self, context_description):
    context_description_node, _ = NeoContextDescription.get_or_create(context_description=context_description)
    return context_description_node

def connect_nodes_unique_case(self, obj, alias_node, definition_node, context_node, context_description_node):
    # Connect alias node
    alias_node.term.connect(obj)
    alias_node.context.connect(context_node)

    # Connect context node
    context_node.context_description.connect(context_description_node)
    context_node.definition.connect(definition_node)
    context_node.term.connect(obj)

    # Connect context description node
    context_description_node.context.connect(context_node)
    context_description_node.definition.connect(definition_node)

    # Connect definition node
    definition_node.context.connect(context_node)
    definition_node.context_description.connect(context_description_node)
    definition_node.term.connect(obj)

    # Connect object relationships
    obj.alias.connect(alias_node)
    obj.definition.connect(definition_node)
    obj.context.connect(context_node)

def get_existing_term(self, deconfliction_response):
    existing_term_data = deconfliction_response['existingTerm']
    existing_term_uid = existing_term_data['uid']
    existing_term = NeoTerm.nodes.get(uid=existing_term_uid)
    logger.info(f'Existing term retrieved: {existing_term}')
    return existing_term

def connect_nodes_duplication_case(self, existing_term, alias_node, context_node, alias_created, context_created):
    if alias_created:
        # Add new alias to existing term
        existing_term.alias.connect(alias_node)
        alias_node.term.connect(existing_term)
        alias_node.context.connect(context_node)
        context_node.alias.connect(alias_node)

    if context_created:
        # Add context to existing term
        existing_term.context.connect(context_node)
        context_node.term.connect(existing_term)
        logger.info('New context node connected to existing term.')

        # Connect definition and context description
        definition_node = existing_term.definition.all()[0]
        context_node.definition.connect(definition_node)

        context_description_node = existing_term.context.all()[0].context_description.all()[0]
        context_node.context_description.connect(context_description_node)
        logger.info('Definition and context description connected to new context node.')