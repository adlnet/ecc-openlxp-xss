from .models import NeoAlias, NeoDefinition, NeoContext, NeoContextDescription, NeoTerm
from deconfliction_service.views import run_deconfliction
import logging
from uuid import uuid4

from uid.models import UIDNode

logger = logging.getLogger('dict_config_logger')

def run_node_creation(definition: str, context: str, context_description: str, alias: str=None):
    try:
        logger.info('Running Deconfliction')
        definition_vector_embedding, deconfliction_status, most_similar_text, highest_score = run_deconfliction(alias, definition, context, context_description)

        if deconfliction_status == 'unique':
            run_unique_definition_creation(definition=definition, context=context, context_description=context_description, definition_embedding=definition_vector_embedding, alias=alias)
        elif deconfliction_status == 'duplicate':
            run_duplicate_definition_creation(alias=alias, definition=most_similar_text, context=context, context_description=context_description)
        elif deconfliction_status == 'collision':
            run_collision_definition_creation(alias, most_similar_text, definition, context, context_description, definition_vector_embedding, highest_score)
            

    except Exception as e: 
        logger.error(f"Error in run_node_creation: {e}")
        raise e


def run_unique_definition_creation(definition, context, context_description, definition_embedding, alias):
    try:
        term_node = NeoTerm.create_new_term()
        alias_node, _ = NeoAlias.get_or_create(alias=alias) if alias else (None, None)
        definition_node, _ = NeoDefinition.get_or_create(definition=definition, definition_embedding=definition_embedding)
        context_node, _ = NeoContext.get_or_create(context=context)
        context_description_node, _ = NeoContextDescription.get_or_create(context_description=context_description, context_node=context_node)

        term_node.set_relationships(alias_node=alias_node, definition_node=definition_node, context_node=context_node)
        context_node.set_relationships(term_node=term_node, alias_node=alias_node, definition_node=definition_node, context_description_node=context_description_node)
        definition_node.set_relationships(term_node=term_node, context_node=context_node, context_description_node=context_description_node)
        context_description_node.set_relationships(definition_node=definition_node, context_node=context_node)

        if alias_node:
            alias_node.set_relationships(term_node=term_node, context_node=context_node)

    except Exception as e:
        logger.error(f"Error in run_unique_definition_creation: {e}")
        raise

def run_duplicate_definition_creation(alias, definition, context, context_description):
    try:
        alias_node, _ = NeoAlias.get_or_create(alias=alias) if alias else (None, None)
        context_node, _ = NeoContext.get_or_create(context=context) if context else (None, None)
        context_description_node, _ = NeoContextDescription.get_or_create(context_description=context_description, context_node=context_node) if context_description else (None, None)
        definition_node, _ = NeoDefinition.get_or_create(definition=definition)

        term_node = definition_node.get_term_node()
        logger.info(term_node)
        if not term_node: # Duplicate collision scenario
            if alias_node:
                alias_node.set_relationships(collided_definition=definition_node, context_node=context_node)
            if context_node:
                context_node.set_relationships(alias_node=alias_node, definition_node=definition_node, context_description_node=context_description_node)
            definition_node.set_relationships(context_node=context_node, context_description_node=context_description_node)
            context_description_node.set_relationships(definition_node=definition_node, context_node=context_node)
            return

        # Duplicate scenario with a term node (acts like unique scenario)
        term_node.set_relationships(alias_node=alias_node, definition_node=definition_node)
        if context_node:
            context_node.set_relationships(term_node=term_node, alias_node=alias_node, definition_node=definition_node, context_description_node=context_description_node)
            
        definition_node.set_relationships(term_node=term_node, context_node=context_node, context_description_node=context_description_node)
        if context_description_node:
            context_description_node.set_relationships(definition_node=definition_node, context_node=context_node)
        
        if alias_node:
            if not context_node:
                alias_node.set_relationships(term_node=term_node)
            alias_node.set_relationships(term_node=term_node, context_node=context_node)

    except Exception as e:
        logger.error(f"Error in run_duplicate_definition_creation: {e}")
        raise e

def run_collision_definition_creation(alias, most_similar_definition, definition, context, context_description, definition_vector_embedding, highest_score):
    try:
        alias_node = None
        if alias:
            alias_node, _ = NeoAlias.get_or_create(alias=alias)
        existing_definition_node, _ = NeoDefinition.get_or_create(definition=most_similar_definition)
        if not existing_definition_node:
            logger.error('Existing definition node not found')
            raise Exception('Existing definition node not found')
        colliding_definition_node, _ = NeoDefinition.get_or_create(definition=definition, definition_embedding=definition_vector_embedding)
        logger.info(f"Colliding Definition Node: {colliding_definition_node}")
        if not colliding_definition_node:
            logger.error('Colliding definition node not found')
            raise Exception('Colliding definition node not found')
        context_node, _ = NeoContext.get_or_create(context=context)
        context_description_node, _ = NeoContextDescription.get_or_create(context_description=context_description, context_node=context_node)

        alias_node.set_relationships(context_node=context_node, collided_definition=colliding_definition_node)
        context_node.set_relationships(context_description_node=context_description_node, definition_node=colliding_definition_node)
        context_description_node.set_relationships(definition_node=colliding_definition_node)
        colliding_definition_node.set_relationships(context_node=context_node, context_description_node=context_description_node, collision_alias=alias_node, collision=existing_definition_node)

    except Exception as e: 
        logger.error(f"Error in run_collision_definition_creation: {e}")
        raise e


