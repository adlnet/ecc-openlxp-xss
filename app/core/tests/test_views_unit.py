import unittest
from unittest.mock import patch, MagicMock
import json
from core.models import NeoTerm
from core.views import export_terms_as_json, export_terms_as_xml
import xml.etree.ElementTree as ET

class ExportNeoTermsViewsTests(unittest.TestCase):

    def setUp(self):
        self.neoterm1 = MagicMock()
        self.neoterm1.term = 'test_term'
        self.neoterm1.definition = 'test_definition'
        self.neoterm1.context = 'test_context'
        self.neoterm1.context_description = 'test_context_description'

        self.neoterm2 = MagicMock()
        self.neoterm2.term = 'test_term2'
        self.neoterm2.definition = 'test_definition2'
        self.neoterm2.context = 'test_context2'
        self.neoterm2.context_description = 'test_context_description2'

    
    @patch('core.models.NeoTerm.nodes', autoSpec=True)
    def test_export_terms_as_json(self, mock_nodes):
        
        mock_nodes.all.return_value = [self.neoterm1, self.neoterm2]

        request = MagicMock()
        response = export_terms_as_json(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="terms.json"')

        expected_json = [
            {'term': 'test_term', 'definition': 'test_definition', 'context': 'test_context', 'context_description': 'test_context_description'},
            {'term': 'test_term2', 'definition': 'test_definition2', 'context': 'test_context2', 'context_description': 'test_context_description2'},
        ]
        self.assertEqual(json.loads(response.content), expected_json)
    
    @patch('core.models.NeoTerm.nodes', autoSpec=True)
    def test_export_terms_as_xml(self, mock_nodes):

        mock_nodes.all.return_value = [self.neoterm1, self.neoterm2]
        
        request = MagicMock()
        response = export_terms_as_xml(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="terms.xml"')
        self.assertEqual(response['Content-Type'], 'application/xml')

        xml_string = "<NeoTerms><NeoTerm><term>test_term</term><definition>test_definition</definition><context>test_context</context><context_description>test_context_description</context_description></NeoTerm><NeoTerm><term>test_term2</term><definition>test_definition2</definition><context>test_context2</context><context_description>test_context_description2</context_description></NeoTerm></NeoTerms>"
        

        actual_xml = ET.fromstring(response.content)
        expected_xml = ET.fromstring(xml_string)

        ## TODO:     
        ##      Potentially weak assertion if the XML structure changes,
        ##      as this is a string literal comparison.
        ##
        ##      Would prefer if this sort of thing were compared with properties
        ##      down the road.
        ##    
        self.assertEqual(ET.tostring(actual_xml), ET.tostring(expected_xml))