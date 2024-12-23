from django.test import TestCase
from unittest.mock import patch, MagicMock
from .models import Provider, LCVTerm, LanguageSet, UIDCounterDjangoModel, uid_generator # Import the UID generator from Models removed UIDCounter
from .models import UIDCounter, UIDNode, UIDGenerator
from .utils import send_notification
from django.urls import reverse
from rest_framework.test import APITestCase
from neomodel import db
from .models import report_uids_by_echelon

#updated Classes and Test Cases
class TestCounterNode(TestCase):
    @patch('app.uid.models.UIDCounter.save')
    @patch('app.uid.models.UIDCounter.nodes.first_or_none')
    def test_get_creates_counter_node_if_none(self, mock_first_or_none, mock_save):
        mock_first_or_none.return_value = None
        counter_node = UIDCounter._get_instance()
        mock_first_or_none.assert_called_once()
        mock_save.assert_called_once()
        self.assertEqual(counter_node.counter, 0)

    @patch('app.uid.models.UIDCounter.increment')
    @patch('app.uid.models.UIDCounter.nodes.first_or_none')
    def test_get_returns_counter_node(self, mock_first_or_none, mock_increment):
        mock_counter_node = MagicMock()
        mock_counter_node.counter = 1
        mock_first_or_none.return_value = mock_counter_node

        counter_node = UIDCounter._get_instance()

        mock_first_or_none.assert_called_once()
        mock_increment.assert_not_called()
        self.assertEqual(counter_node.counter, 1)

    @patch('app.uid.models.UIDCounter.save')
    def test_increment(self, mock_save):
        counter = UIDCounter._get_instance()
        initial_value = counter.counter
        counter.increment()
        self.assertEqual(counter.counter, initial_value + 1)

class UIDGenerationTestCase(TestCase):
    def setUp(self):
        UIDCounter.nodes.delete()  # Ensure a clean state before each test

    def test_uid_generation_for_providers(self):
        provider = Provider(name="Test Provider")
        provider.uid = UIDGenerator().generate_uid()  # Ensure UID is generated
        self.assertIsNotNone(provider.uid)
        self.assertTrue(provider.uid.startswith("0x"))
        self.assertEqual(len(provider.uid), 10)

    def test_uid_generation_for_lcv_terms(self):
        lcv_term = LCVTerm(term="Test LCV Term")
        lcv_term.uid = UIDGenerator().generate_uid()  # Ensure UID is generated
        self.assertIsNotNone(lcv_term.uid)
        self.assertTrue(lcv_term.uid.startswith("0x"))
        self.assertEqual(len(lcv_term.uid), 10)
        self.assertNotIn(lcv_term.uid, [l.uid for l in LCVTerm.nodes.all() if l.uid])    
        
    def test_uid_generation_for_language_sets(self): #Changes to reflect LanguageSet now DjangoNode
        with db.transaction:
            language_set = LanguageSet(name="Test Language Set").save()
            self.assertIsNotNone(language_set.uid)
            self.assertTrue(language_set.uid.startswith("0x"))
            self.assertEqual(len(language_set.uid), 10)  # Assuming UID length is 10 (0x + 8 hex digits)
            self.assertNotIn(language_set.uid, [ls.uid for ls in LanguageSet.objects.all() if ls.uid])

    def test_issuing_uid_to_providers(self):
        provider = Provider(name="Test Provider").save()
        self.assertIsNotNone(provider.uid)
        self.assertTrue(provider.uid.startswith("0x"))
        self.assertEqual(provider.uid, uid_generator.generate_uid())

    def test_issuing_uid_to_lcv_terms(self):
        lcv_term = LCVTerm(term="Test LCV Term").save()
        self.assertIsNotNone(lcv_term.uid)
        self.assertTrue(lcv_term.uid.startswith("0x"))
        self.assertEqual(lcv_term.uid, uid_generator.generate_uid())

    def test_verification_of_uid_assignment(self):
        provider = Provider(name="Test Provider").save()
        lcv_term = LCVTerm(term="Test LCV Term").save()
        self.assertEqual(provider.uid, uid_generator.generate_uid())
        self.assertEqual(lcv_term.uid, uid_generator.generate_uid())

    def test_notification_on_successful_uid_issuance(self):
        provider = Provider(name="Test Provider").save()
        lcv_term = LCVTerm(term="Test LCV Term").save()
        provider_uid = provider.uid
        lcv_term_uid = lcv_term.uid
        self.assertTrue(send_notification(provider, provider_uid))
        self.assertTrue(send_notification(lcv_term, lcv_term_uid))

    # Adding terms to languageSets
    def test_add_term_to_language_set(self):
        with db.transaction:
            language_set = LanguageSet(name="Test Language Set").save()
            lcv_term = LCVTerm(term="Test LCV Term").save()
            language_set.add_term(lcv_term)
            self.assertIn(lcv_term, language_set.get_terms())

    # Echelon Reporting Test
    def test_report_uids_by_echelon():
    # Setup: Create some UIDNodes with known echelon levels
        UIDNode.create_node(uid="0x00000001", namespace="test", echelon_level="level_1")
        UIDNode.create_node(uid="0x00000002", namespace="test", echelon_level="level_1")
        UIDNode.create_node(uid="0x00000003", namespace="test", echelon_level="level_2")

    # Execute the report function
    result = report_uids_by_echelon("level_1")

    # Assert that the correct UIDs are returned
    assert result == ["0x00000001", "0x00000002"]

# Potnetial code for upstream/downstream testing for Providers/LCVterms
    #def test_upstream_providers(self):
     #   with db.transaction:
      #      provider = Provider(name="Test Provider").save()
       #     lcv_term = LCVTerm(term="Test LCV Term").save()
        #    provider.lcv_terms.connect(lcv_term)
         #   upstream_providers = lcv_term.get_upstream()
          #  self.assertIn(provider, upstream_providers)

    #def test_downstream_lcv_terms(self):
     #   with db.transaction:
      #      provider = Provider(name="Test Provider").save()
       #     lcv_term = LCVTerm(term="Test LCV Term").save()
        #    provider.lcv_terms.connect(lcv_term)
         #   downstream_lcv_terms = provider.get_downstream()
          #  self.assertIn(lcv_term, downstream_lcv_terms)

class ExportToPostmanTestCase(APITestCase):

    def test_export_provider(self):
        provider = Provider.objects.create(name="Test Provider", uid="P-1234567890")
        url = reverse('export_to_postman', args=[provider.uid])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['uid'], provider.uid)

    def test_export_lcv_term(self):
        lcv_term = LCVTerm.objects.create(name="Test LCV Term", uid="L-1234567890")
        url = reverse('export_to_postman', args=[lcv_term.uid])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['uid'], lcv_term.uid)

    def test_export_invalid_uid(self):
        url = reverse('export_to_postman', args=["invalid-uid"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
