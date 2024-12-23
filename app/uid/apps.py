from django.apps import AppConfig
#from .models import LastGeneratedUID  # Import LastGeneratedUID here


class UidConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'uid'

    #def ready(self):
        #from .models import LastGeneratedUID  # Import the LastGeneratedUID model
     #   self.initialize_last_generated_uid()

    #def initialize_last_generated_uid(self):
     #   """Ensure the LastGeneratedUID node exists in Neo4j."""
      #  if not LastGeneratedUID.nodes.first_or_none():
       #     LastGeneratedUID().save()
        

    