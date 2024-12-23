from django.db import models, transaction #Import Models and transaction atomic
from neomodel import db, StringProperty, DateTimeProperty, BooleanProperty, RelationshipTo, RelationshipFrom, StructuredNode, IntegerProperty, NodeSet
from datetime import datetime
import time, logging, re # Import time module to use sleep, Logging and re
from django_neomodel import DjangoNode
from collections import defaultdict
from typing import List
from uuid import uuid4

from collections import defaultdict
# from core.models import NeoTerm

logger = logging.getLogger(__name__)

GLOBAL_PROVIDER_OWNER_UID = "0xFFFFFFFF"
UID_PATTERN = r"^0x[0-9A-Fa-f]{8}$"
COLLISION_THRESHOLD = 5  # Number of attempts before adjusting the base counter

# Function to check Neo4j connection
def check_neo4j_connection():
    for attempt in range(5):  # Retry a few times
        try:
            db.cypher_query("RETURN 1")  # Simple query to test connection
            return True
        except Exception:
            time.sleep(1)  # Wait before retrying
    return False

# Alias class incase you create and alias with no context
# class Alias(StructuredNode):
#     alias = StringProperty(unique_index=True)  # The alias name
#     context = StringProperty(required=False, default=None)  # Optional context
#     points_to = RelationshipTo('NeoTerm', 'POINTS_TO')  # The relationship to NeoTerm
#     context_error = StringProperty(required=False)  # Optional field to store error message

#     def __str__(self):
#         return self.alias

#     def link_to_term(self, neo_term):
#         from core.models import NeoTerm, NeoAlias, NeoContext
#         """Link this alias to a NeoTerm."""
#         if isinstance(neo_term, NeoTerm):
#             self.points_to.connect(neo_term)

#     def save(self, *args, **kwargs):
#         """Override the save method to automatically link the alias to a NeoTerm if context is provided."""
#         context_error = None  # Initialize an error variable

#         # Call the parent class save method
#         super(Alias, self).save(*args, **kwargs)

#         if self.context:
#             from core.models import NeoTerm, NeoAlias, NeoContext
#             term, created = NeoTerm.get_or_create(uid=self.context) # Get or create the NeoTerm based on the context
#             if term:
#                 # Set relationships for the NeoTerm, including the alias
#                 term.set_relationships(definition_node, context_node, self)
#             else:
#                 context_error = f"No matching NeoTerm found for context: {self.context}"
#         else:
#             # If no context is provided, link to a default NeoTerm (first available NeoTerm)
#             term = NeoTerm.nodes.first()  # You can change this to a specific fallback logic
#             if term:
#                 self.link_to_term(term)
#             else:
#                 context_error = "No NeoTerm available to link."

#         # If an error was encountered, raise it so it can be caught in the view or returned to the form
#         if context_error:
#             self.context_error = context_error  # Store the error message in the instance
#             self.save()
        
#         return context_error  # Return the error message, if any

# Addition of the NeoAliasManager class to use NeoAlias in core/models
class NeoAliasManager:
    @staticmethod
    def link_alias_to_term_and_context(alias: str, context: str = None):
        from core.models import NeoTerm, NeoAlias, NeoContext
        """Manage the linking of NeoAlias to NeoTerm and NeoContext."""
        context_error = None

        # Get or create the NeoAlias (same as get_or_create in your Alias class)
        alias_node, created = NeoAlias.get_or_create(alias)

        if context:
            # If context is provided, attempt to get or create NeoContext
            context_node, context_created = NeoContext.get_or_create(context)
            if context_node:
                # Link the alias to the context
                alias_node.context.connect(context_node)
            else:
                context_error = f"No matching NeoContext found for context: {context}"

        if not alias_node.term:
            # If no term is linked, link the alias to the first available NeoTerm
            term = NeoTerm.nodes.first()  # Fallback logic to link to the first available NeoTerm
            if term:
                alias_node.term.connect(term)
            else:
                context_error = context_error or "No NeoTerm available to link."

        # Save the alias (optional)
        alias_node.save()

        # If any errors occurred, return the error message
        if context_error:
            alias_node.context_error = context_error  # Store error on the alias
            alias_node.save()  # Save the alias again with the error information

        return context_error  # Return the error message, if any

# Generated Logs to track instance, time of generation, uid, provider and lcv terms
class GeneratedUIDLog(models.Model):
    uid = models.CharField(max_length=255, default="UNKNOWN")
    uid_full = models.CharField(max_length=255, default="UNKNOWN")
    generated_at = models.DateTimeField(auto_now_add=True)
    generator_id = models.CharField(max_length=255)
    provider = models.CharField(max_length=255, null=True)
    lcv_terms = models.CharField(max_length=255, null=True)

    class Meta:
        verbose_name = "Generated UID Log"
        verbose_name_plural = "Generated UID Logs"

class UIDCounter(StructuredNode):
    owner_uid = StringProperty(required=True)
    counter = IntegerProperty(default=0)
    
    # # _cached_instance = None #added for caching
    # _cache = {}

    @classmethod
    def _get_instance(cls, owner_uid: str) -> 'UIDCounter':
        # if owner_uid in cls._cache:
        #     return cls._cache[owner_uid]
    
        # try:
        # instances = cls.get_or_create(owner_uid=owner_uid)
        nodes = UIDCounter.nodes
        assert isinstance(nodes, NodeSet)
        result = nodes.get_or_none(owner_uid=owner_uid)

        if result is None:
            instance = UIDCounter(owner_uid=owner_uid)
            instance.save()
            # cls._cache[owner_uid] = instance
            return instance
        
        if isinstance(result, list):
            instance = result[0]
        else:
            instance = result
        
        assert isinstance(instance, UIDCounter)
        # cls._cache[owner_uid] = instance
        return instance 

    @classmethod
    def increment(cls, owner_uid: str):
        # with transaction.atomic():  # Ensure atomic operation
        instance = cls._get_instance(owner_uid)
        current_value = instance.counter
        instance.counter = current_value + 1
        instance.save()
        return instance.counter

# # Django model for admin management
# class UIDCounterDjangoModel(models.Model):
#     counter_value = models.IntegerField(default=0)

#     class Meta:
#         verbose_name = "UID Counter"
#         verbose_name_plural = "UID Counters"

#     @classmethod
#     def initialize(cls):
#         """Ensure a counter exists in the Django model."""
#         #cls.objects.get_or_create(id=1)  # Ensure a single instance
#         cls.objects.get_or_create(id=1, defaults={'counter_value': 0})
        
# # Initialize the UID Generator
# uid_generator = None

# def get_uid_generator():
#     global uid_generator
#     if uid_generator is None:
#         if not check_neo4j_connection():  # Check connection when first needed
#             raise RuntimeError("Neo4j service is not available.")
#         uid_generator = UIDGenerator()
#     return uid_generator

# UID Compliance check
def is_uid_compliant(uid):
    """Check if the UID complies with the specified pattern."""
    return bool(re.match(UID_PATTERN, uid))

def report_malformed_uids():
    """Generate a report of all malformed UIDs."""
    malformed_uids = []
    logs = GeneratedUIDLog.objects.all()
    
    for log in logs:
        if not is_uid_compliant(log.uid):
            malformed_uids.append(log.uid)
    
    return malformed_uids


# Neo4j UID Node
class UIDNode(DjangoNode):
    uid = StringProperty(required=True)
    # namespace = StringProperty(required=True)
    updated_at = DateTimeProperty(default_now=True)
    created_at = DateTimeProperty(default_now=True)

    # children = RelationshipTo('UIDNode', 'HAS_CHILD')
    # lcv_terms = RelationshipTo('LCVTerm', 'HAS_LCV_TERM')
    # provider = RelationshipTo('Provider', 'HAS_PROVIDER')

    @classmethod
    def get_node_by_uid(cls, uid: str):
        # return cls.nodes.get_or_none(uid=uid, namespace=namespace)
        return cls.nodes.get_or_none(uid=uid)
    
    @classmethod
    def create_node(cls, owner_uid: str) -> 'UIDNode':
        # # Find existing Node
        # existing_node = cls.get_node_by_uid(uid=None, namespace=namespace)  # Adjust the filter as needed
        # if existing_node:
        #     logger.info(f"Node already exists for namespace: {namespace}. Reusing existing UID: {existing_node.uid}.")
        #     return existing_node  # Return the existing node if found
        
        # uid_node = cls(uid=uid, namespace=namespace)
        uid_value = generate_uid(owner_uid)
        uid_node = cls(uid=uid_value)
        uid_node.save()
        return uid_node
    
    class Meta:
        app_label = 'uid'


# Refactored UID Generator that manages both Neo4j and DjangoNode and confirms Neo4j is available
def generate_uid(owner_uid) -> str:

    uid_value = UIDCounter.increment(owner_uid=owner_uid)
    attempts = 0 # Initialize attempts here change as needed
    
    while True:
        new_uid = f"0x{uid_value:08x}"
        
        # # Collision check
        # while len(UIDNode.nodes.filter(uid=new_uid, owner_uid=owner_uid)) > 0:
        #     logger.warning(f"UID collision detected for {new_uid}. Regenerating UID.")
        #     attempts += 1

        #     # Adjust the UID by incrementing the base value directly to resolve the collision until a unique UID is found
        #     uid_value += 1
        #     new_uid = f"0x{uid_value:08x}"
        #     logger.info(f"Adjusted UID to {new_uid} to resolve collision.")
        
        # Collision threshold, if too many attempts, break, reset attempts and increment base counter
        if attempts >= COLLISION_THRESHOLD:
            logger.error(f"Too many collisions for base UID {uid_value}. Incrementing counter.")
            # counter.increment()
            attempts = 0
            break
        
        logger.info(f"Adjusted UID to {new_uid} to resolve collision.")
    
        # Compliance check
        if not is_uid_compliant(new_uid):
            logger.error(f"Generated UID {new_uid} is not compliant with the expected pattern.")
            continue
        
        # # Sequential order check, if not sequential force increment and regenerate UID
        # if hasattr (self, 'last_uid'):
        #     if self.last_uid is not None and int(new_uid, 16) <= int(self.last_uid, 16):
        #         logger.warning(f"UID {new_uid} is not sequential. Regenerating UID.")
        #         self.counter.increment()
        #         continue
        
        # Update and save the last issued UID
        #
        # uid = models.CharField(max_length=255, unique=True)
        # uid_full = models.CharField(max_length=255, unique=True)
        # generated_at = models.DateTimeField(auto_now_add=True)
        # generator_id = models.CharField(max_length=255)
        # provider = models.CharField(max_length=255, null=True)
        # lcv_terms = models.CharField(max_length=255, null=True)
        uid_full = f"{owner_uid}-{new_uid}"
        GeneratedUIDLog.objects.create(uid=new_uid, uid_full=uid_full)

        # # Log the generated UID
        # GeneratedUIDLog.objects.update_or_create(uid=new_uid, defaults={'generator_id': self.generator_id})

        return new_uid
    
    # # Retrieve Last Generated UID
    # def get_last_generated_uid():
    #     last_uid_record = LastGeneratedUID.objects.first()
    #     return last_uid_record.uid if last_uid_record else None
    
# uid_singleton = UIDGenerator()

# Provider and LCVTerms now Nodes
class Provider(DjangoNode):
    # uid = StringProperty(unique_index=True)
    name = StringProperty(required=True, unique=True)
    default_uid = StringProperty(required=True)

    uid = RelationshipTo('UIDNode', 'HAS_UID')
    uid_counter = RelationshipTo('UIDCounter', 'HAS_UID_COUNTER')
    # lcv_terms = RelationshipTo('LCVTerm', 'HAS_LCV_TERM')

    class Meta:
        app_label = 'uid'

    @classmethod
    def create_provider(cls, name) -> 'Provider':
        
        uid_node = UIDNode.create_node(owner_uid=GLOBAL_PROVIDER_OWNER_UID)
        counter_node = UIDCounter._get_instance(owner_uid=uid_node.uid)

        provider = Provider(name=name, default_uid=uid_node.uid)
        provider.save()
        provider.uid.connect(uid_node)
        provider.uid_counter.connect(counter_node)
        provider.save()

        return provider
    
    @classmethod
    def does_provider_exist(cls, name):
        provider_nodes = Provider.nodes
        assert isinstance(provider_nodes, NodeSet)
        result = provider_nodes.get_or_none(name=name)

        return result is not None
    
    @classmethod
    def get_provider_by_name(cls, name):
        provider_nodes = Provider.nodes
        assert isinstance(provider_nodes, NodeSet)
        result = provider_nodes.get_or_none(name=name)

        if result is None:
            raise Exception(f"CANNOT FIND REQUESTED PROVIDER: {name}")

        provider = result
        if isinstance(provider, list):
            provider = result[0]

        assert isinstance(provider, Provider)
        return provider
    
    def get_current_uid(self):
        current_uid = self.default_uid

        current_uid_node = self.uid.end_node()
        if current_uid_node is not None:
            assert isinstance(current_uid_node, UIDNode)
            current_uid = current_uid_node.uid

        return current_uid

# Django Provider Model for Admin
class ProviderDjangoModel(models.Model):
    # uid = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255, unique=True)
    # default_uid = StringProperty(required=True)
    
    @classmethod
    def does_django_provider_exist(cls, provider_name: str):
        result = ProviderDjangoModel.objects.filter(name=provider_name).first()
        return result is not None
    
    @classmethod
    def ensure_provider_exists(cls, provider_name: str) -> 'Provider':
        """
        Ensure that this Provider exists as both a Django Model (for the admin view)
        and as a graph node.  The graph node portion is handled by the save() override,
        which gives that node as an extended return value.
        """
        if not Provider.does_provider_exist(provider_name):
            django_model_exists = ProviderDjangoModel.does_django_provider_exist(provider_name)
            if django_model_exists:
                provider = ProviderDjangoModel.get_by_name(provider_name).save()
            else:
                provider = ProviderDjangoModel(name=provider_name).save()
        else:
            return Provider.get_provider_by_name(provider_name)

        assert isinstance(provider, Provider)
        return provider

    @classmethod
    def get_by_name(cls, provider_name: str):
        return ProviderDjangoModel.objects.get(name=provider_name)

    def save(self, *args, **kwargs) -> 'Provider':
        # Create or update the Neo4j Provider node
        provider = Provider.create_provider(self.name)
        super().save(*args, **kwargs)

        return provider

    class Meta:
        verbose_name = "Provider"
        verbose_name_plural = "Providers"

class UIDRequestToken(models.Model):
    token = models.CharField(max_length=255, unique=True)
    provider_name = models.CharField(max_length=255)
    echelon = models.CharField(max_length=255)
    termset = models.CharField(max_length=255)
    uid = models.CharField(max_length=255)
    uid_chain = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        
        given_provider = self.provider_name
        
        requested_node = UIDRequestNode.create_requested_uid(given_provider)
        requested_node.save()

        self.token = requested_node.token
        self.uid = requested_node.default_uid
        self.uid_chain = requested_node.default_uid_chain

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "UIDRequestToken"
        verbose_name_plural = "UIDRequestTokens"

class UIDRequestNode(DjangoNode):
    token = StringProperty(required=True)
    default_uid = StringProperty(required=True)
    default_uid_chain = StringProperty(default="")

    provider = RelationshipTo('Provider', 'HAS_PROVIDER')
    uid = RelationshipTo('UIDNode', 'HAS_UID')

    @classmethod
    def create_requested_uid(cls, provider_name: str):
        
        provider = ProviderDjangoModel.ensure_provider_exists(provider_name)
        assert isinstance(provider, Provider)
                
        uid_node = UIDNode.create_node(owner_uid=provider.default_uid)

        requested_node = UIDRequestNode()
        requested_node.token = uuid4()
        requested_node.default_uid = uid_node.uid
        requested_node.default_uid_chain = f"{provider.default_uid}-{uid_node.uid}" 
        requested_node.save()
        requested_node.uid.connect(uid_node)
        requested_node.provider.connect(provider)
        requested_node.save()
        
        return requested_node
    
# LCV Terms model for DjangoNode
class LCVTerm(DjangoNode):
    default_uid = StringProperty(required=True)
    default_uid_chain = StringProperty(default="")

    term = StringProperty(required=True)
    ld_lcv_structure = StringProperty()
    echelon_level = StringProperty(required=True)  # Required for echelon check

    uid = RelationshipTo('UIDNode', 'HAS_UID')
    provider = RelationshipFrom('Provider', 'HAS_LCV_TERM')

    class Meta:
        app_label = 'uid'

    @classmethod
    def create_term(cls, provider_name: str, term: str, structure: str, echelon_level: str):
        
        provider = Provider.get_provider_by_name(provider_name)
        assert isinstance(provider, Provider)
                
        uid_node = UIDNode.create_node(
            owner_uid=provider.default_uid
        )

        lcv_term = LCVTerm(term=term, echelon_level=echelon_level, ld_lcv_structure=structure)
        lcv_term.default_uid = uid_node.uid
        lcv_term.default_uid_chain = f"{provider.default_uid}-{uid_node.uid}" 
        lcv_term.save()
        lcv_term.uid.connect(uid_node)
        lcv_term.provider.connect(provider)
        lcv_term.save()
        
        return lcv_term
    
    def get_current_local_uid_chain(self):

        current_uid = self.default_uid
        current_uid_node = self.uid.end_node()
        if self.uid.end_node() is not None:
            current_uid = current_uid_node.uid
        
        current_provider_uid = ""
        current_provider_node = self.provider.start_node()
        if current_provider_node is None:
            assert isinstance(current_provider_node, Provider)
            current_provider_uid = current_provider_node.get_current_uid()
        
        return f"{current_provider_uid}-{current_uid}"

# Django LCVTerm Model for Admin
class LCVTermDjangoModel(models.Model):
    # uid = models.CharField(max_length=255, unique=True)
    provider_name = models.CharField(max_length=255)
    term = models.CharField(max_length=255)
    echelon = models.CharField(max_length=255)
    structure = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        # Create or update the Neo4j LCVTerm node
        lcv_term = LCVTerm.create_term(provider_name=self.provider_name, term=self.term, echelon_level=self.echelon, structure=self.structure)
        lcv_term.save()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "LCV Term"
        verbose_name_plural = "LCV Terms"

# # LanguageSet now a Node
# class LanguageSet(StructuredNode):
#     uid = StringProperty(default=lambda: uid_singleton.generate_uid(), unique_index=True)
#     name = StringProperty(required=True)
#     terms = RelationshipTo(LCVTerm, 'HAS_TERM')

#     def add_term(self, term):
#         self.terms.connect(term)

#     def get_terms(self):
#         return self.terms.all()

# Adding reporting by echelon level
def report_uids_by_echelon(echelon_level):
    """Retrieve UIDs issued at a specific echelon level."""
    nodes = UIDNode.nodes
    assert isinstance(nodes, NodeSet)
    nodes = nodes.filter(echelon_level=echelon_level)
    return [node.uid for node in nodes]

def report_all_uids():
    """Retrieve all UIDs issued in the enterprise."""
    nodes = UIDNode.nodes.all()
    return [node.uid for node in nodes]

# Reporting function for all generated UIDs
def report_all_generated_uids():
    """Retrieve all generated UIDs from the log."""
    logs = GeneratedUIDLog.objects.all()
    return [
        {
            "uid": log.uid, 
            "uid_full": log.uid_full, 
            "generated_at": str(log.generated_at)
        } for log in logs
    ]

def report_all_term_uids():
    """
    Query and return all UID chains from every known Term.
    """
    term_nodes = LCVTerm.nodes.all()
    return [term.get_current_local_uid_chain() for term in term_nodes]

# # Reporting all UID collision
# def report_uid_collisions():
#     """Generate a report of potential UID collisions across all UID microservices."""
#     # Retrieve all UID logs
#     logs = GeneratedUIDLog.objects.all()

#     # Dictionary to track UIDs by (parent_id, uid)
#     uid_dict = defaultdict(list)

#     for log in logs:
#         # Store the combination of parent_id and uid
#         uid_dict[(log.parent_id, log.uid)].append(log)

#         # Collect UIDs for Providers
#         providers = ProviderDjangoModel.objects.all()
#         for provider in providers:
#             uid_dict[(provider.uid, provider.uid)].append(provider)

#         # Collect UIDs for LCVTerms
#         lcv_terms = LCVTermDjangoModel.objects.all()
#         for lcv_term in lcv_terms:
#             uid_dict[(lcv_term.uid, lcv_term.uid)].append(lcv_term)

#     # Find collisions (where length > 1)
#     collisions = {key: value for key, value in uid_dict.items() if len(value) > 1}
#     return collisions
