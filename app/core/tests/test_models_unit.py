import json
from unittest.mock import mock_open, patch
import unittest

from clamd import EICAR
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import tag

from core.models import (ChildTermSet, SchemaLedger, Term, TermSet,
                         TransformationLedger, validate_version, NeoTerm)

from neomodel import db

from .test_setup import TestSetUp


@tag('unit')
class ModelTests(TestSetUp):

    def test_schema_ledger(self):
        """Test that creating a SchemaLedger is successful"""

        schema_name = 'test_name'
        schema_iri = 'test_iri'
        metadata = {
            'test': 'test'
        }
        status = 'published'
        version = '1.0.1'
        major_version = 1
        minor_version = 0
        patch_version = 1

        schema = SchemaLedger(schema_name=schema_name,
                              schema_iri=schema_iri,
                              metadata=metadata,
                              status=status,
                              version=version,
                              major_version=major_version,
                              minor_version=minor_version,
                              patch_version=patch_version)

        self.assertEqual(schema.schema_name, schema_name)
        self.assertEqual(schema.schema_iri, schema_iri)
        self.assertEqual(schema.status, status)
        self.assertEqual(schema.metadata, metadata)
        self.assertEqual(schema.version, version)
        self.assertEqual(schema.major_version, major_version)
        self.assertEqual(schema.minor_version, minor_version)
        self.assertEqual(schema.patch_version, patch_version)

    def test_schema_ledger_virus(self):
        """Test that creating a SchemaLedger with a virus fails"""

        schema_name = 'test_name'
        schema_iri = 'test_iri'
        status = 'published'
        version = '1.0.1'
        major_version = 1
        minor_version = 0
        patch_version = 1
        file = ContentFile(EICAR, 'virus')

        schema = SchemaLedger(schema_name=schema_name,
                              schema_iri=schema_iri,
                              status=status,
                              major_version=major_version,
                              minor_version=minor_version,
                              patch_version=patch_version,
                              schema_file=file)

        with patch('core.models.logger') as log,\
                patch('core.models.clamd') as clam:
            clam.instream.return_value = {'stream': ('BAD', 'EICAR')}
            clam.ClamdUnixSocket.return_value = clam

            self.assertEqual(schema.version, '')
            self.assertEqual(schema.schema_file.size, len(EICAR))
            schema.clean()
            self.assertEqual(schema.version, version)
            self.assertEqual(schema.schema_file, None)
            self.assertGreater(log.error.call_count, 0)
            self.assertIn('EICAR', log.error.call_args[0][2])
            self.assertGreater(clam.instream.call_count, 0)
            self.assertEqual(file, clam.instream.call_args[0][0])
            self.assertIsNone(schema.metadata)

    def test_schema_ledger_non_json(self):
        """Test that creating a SchemaLedger with a non json file fails"""

        schema_name = 'test_name'
        schema_iri = 'test_iri'
        status = 'published'
        version = '1.0.1'
        major_version = 1
        minor_version = 0
        patch_version = 1
        file_contents = b'test string'
        file = ContentFile(file_contents, 'not json')

        schema = SchemaLedger(schema_name=schema_name,
                              schema_iri=schema_iri,
                              status=status,
                              major_version=major_version,
                              minor_version=minor_version,
                              patch_version=patch_version,
                              schema_file=file)

        with patch('core.models.logger') as log,\
                patch('core.models.clamd') as clam,\
                patch('builtins.open', mock_open()),\
                patch('core.models.magic') as magic,\
                patch('core.models.os'):
            magic.from_file.return_value = 'text/plain'
            clam.instream.return_value = {'stream': ('OK', 'OKAY')}
            clam.ClamdUnixSocket.return_value = clam

            self.assertEqual(schema.version, '')
            self.assertEqual(schema.schema_file.size, len(file_contents))
            schema.clean()
            self.assertEqual(schema.version, version)
            self.assertEqual(schema.schema_file, None)
            self.assertGreater(log.error.call_count, 0)
            self.assertIn('text/plain',
                          log.error.call_args[0][1])
            self.assertIsNone(schema.metadata)

    def test_schema_ledger_bleach(self):
        """Test that creating a SchemaLedger with a valid file passes"""

        schema_name = 'test_name'
        schema_iri = 'test_iri'
        status = 'published'
        version = '1.0.1'
        major_version = 1
        minor_version = 0
        patch_version = 1
        tagged_metadata = {'test': '<em>test</em>'}
        file_contents = json.dumps(tagged_metadata).encode('ascii')
        file = ContentFile(file_contents, 'with html tags')
        metadata = {'test': 'test'}

        schema = SchemaLedger(schema_name=schema_name,
                              schema_iri=schema_iri,
                              status=status,
                              major_version=major_version,
                              minor_version=minor_version,
                              patch_version=patch_version,
                              schema_file=file)

        with patch('core.models.logger') as log,\
                patch('core.models.clamd') as clam,\
                patch('builtins.open', mock_open()),\
                patch('core.models.magic') as magic,\
                patch('core.models.os'):
            magic.from_file.return_value = 'application/json'
            clam.instream.return_value = {'stream': ('OK', 'OKAY')}
            clam.ClamdUnixSocket.return_value = clam

            self.assertEqual(schema.version, '')
            self.assertEqual(schema.schema_file.size, len(file_contents))
            schema.clean()
            self.assertEqual(schema.version, version)
            self.assertEqual(schema.schema_file, None)
            self.assertEqual(log.error.call_count, 0)
            self.assertDictEqual(schema.metadata, metadata)

    def test_transformation_ledger(self):
        """Test that creating a transformationLedger is successful"""

        with patch('core.signals.termset_map'):
            self.termset.save()

            source_schema_name = self.termset
            target_schema_name = self.termset
            schema_mapping = {
                "test": "test"
            }
            status = "published"

            mapping = \
                TransformationLedger(source_schema=source_schema_name,
                                     target_schema=target_schema_name,
                                     schema_mapping=schema_mapping,
                                     status=status)

            mapping.save()

            self.assertEqual(mapping.source_schema, source_schema_name)
            self.assertEqual(mapping.target_schema, target_schema_name)
            self.assertEqual(mapping.schema_mapping, schema_mapping)
            self.assertEqual(mapping.status, status)

    def test_transformation_ledger_virus(self):
        """Test that creating a TransformationLedger with a virus fails"""
        self.termset.save()

        source_schema_name = self.termset
        target_schema_name = self.termset
        file = ContentFile(EICAR, 'virus')
        status = "published"

        mapping = \
            TransformationLedger(source_schema=source_schema_name,
                                 target_schema=target_schema_name,
                                 schema_mapping_file=file,
                                 status=status)

        with patch('core.models.logger') as log,\
                patch('core.models.clamd') as clam:
            clam.instream.return_value = {'stream': ('BAD', 'EICAR')}
            clam.ClamdUnixSocket.return_value = clam

            self.assertEqual(mapping.schema_mapping_file.size, len(EICAR))
            mapping.clean()
            self.assertEqual(mapping.schema_mapping_file, None)
            self.assertGreater(log.error.call_count, 0)
            self.assertIn('EICAR', log.error.call_args[0][2])
            self.assertGreater(clam.instream.call_count, 0)
            self.assertEqual(file, clam.instream.call_args[0][0])
            self.assertIsNone(mapping.schema_mapping)

    def test_transformation_ledger_non_json(self):
        """Test that creating a TransformationLedger with a non json file fails
        """
        self.termset.save()

        source_schema_name = self.termset
        target_schema_name = self.termset
        file_contents = b'test string'
        file = ContentFile(file_contents, 'not json')
        status = "published"

        mapping = \
            TransformationLedger(source_schema=source_schema_name,
                                 target_schema=target_schema_name,
                                 schema_mapping_file=file,
                                 status=status)

        with patch('core.models.logger') as log,\
                patch('core.models.clamd') as clam,\
                patch('builtins.open', mock_open()),\
                patch('core.models.magic') as magic,\
                patch('core.models.os'):
            magic.from_file.return_value = 'text/plain'
            clam.instream.return_value = {'stream': ('OK', 'OKAY')}
            clam.ClamdUnixSocket.return_value = clam

            self.assertEqual(mapping.schema_mapping_file.size,
                             len(file_contents))
            mapping.clean()
            self.assertEqual(mapping.schema_mapping_file, None)
            self.assertGreater(log.error.call_count, 0)
            self.assertIn('text/plain',
                          log.error.call_args[0][1])
            self.assertIsNone(mapping.schema_mapping)

    def test_transformation_ledger_bleach(self):
        """Test that creating a TransformationLedger with a valid file passes
        """
        self.termset.save()

        source_schema_name = self.termset
        target_schema_name = self.termset
        tagged_metadata = {'test': '<em>test</em>'}
        file_contents = json.dumps(tagged_metadata).encode('ascii')
        file = ContentFile(file_contents, 'with html tags')
        metadata = {'test': 'test'}
        status = "published"

        mapping = \
            TransformationLedger(source_schema=source_schema_name,
                                 target_schema=target_schema_name,
                                 schema_mapping_file=file,
                                 status=status)

        with patch('core.models.logger') as log,\
                patch('core.models.clamd') as clam,\
                patch('builtins.open', mock_open()),\
                patch('core.models.magic') as magic,\
                patch('core.models.os'):
            magic.from_file.return_value = 'application/json'
            clam.instream.return_value = {'stream': ('OK', 'OKAY')}
            clam.ClamdUnixSocket.return_value = clam

            self.assertEqual(mapping.schema_mapping_file.size,
                             len(file_contents))
            mapping.clean()
            self.assertEqual(mapping.schema_mapping_file, None)
            self.assertEqual(log.error.call_count, 0)
            self.assertDictEqual(mapping.schema_mapping, metadata)

    def test_term_set(self):
        """Test that creating a TermSet is successful"""
        ts_name = "test_name"
        ts_version = "0.0.1"
        ts_status = TermSet.STATUS_CHOICES[0][0]

        expected_iri = "xss:" + ts_version + "@" + ts_name

        ts = TermSet(name=ts_name, version=ts_version, status=ts_status)

        ts.save()

        self.assertEquals(ts.iri, expected_iri)
        self.assertEquals(ts.name, ts_name)
        self.assertEquals(ts.version, ts_version)
        self.assertEquals(ts.status, ts_status)

    def test_child_term_set(self):
        """Test that creating a ChildTermSet is successful"""
        cts_name = "test_name"
        cts_status = TermSet.STATUS_CHOICES[0][0]
        cts_parent = self.ts

        expected_iri = "xss:" + cts_parent.version + \
            "@" + cts_parent.name + "/" + cts_name

        cts = ChildTermSet(name=cts_name, status=cts_status,
                           parent_term_set=cts_parent)

        cts.save()

        self.assertEquals(cts.iri, expected_iri)
        self.assertEquals(cts.name, cts_name)
        self.assertEquals(cts.version, cts_parent.version)
        self.assertEquals(cts.status, cts_status)

    def test_term(self):
        """Test that creating a Term is successful"""
        t_name = "test_name"
        t_description = "test description"
        t_data_type = "string"
        t_use = Term.USE_CHOICES[0][0]
        t_source = "source"
        t_ts = self.ts
        t_status = "published"

        expected_iri = "xss:" + t_ts.version + "@" + t_ts.name + "?" + t_name
        expected_export = {'use': t_use, 'data_type': t_data_type,
                           'source': t_source, 'description': t_description}

        term = Term(name=t_name, description=t_description,
                    data_type=t_data_type, use=t_use,
                    source=t_source, term_set=t_ts, status=t_status)

        term.save()

        self.assertEquals(term.iri, expected_iri)
        self.assertEquals(term.name, t_name)
        self.assertEquals(term.data_type, t_data_type)
        self.assertEquals(term.use, t_use)
        self.assertEquals(term.source, t_source)
        self.assertEquals(term.term_set, t_ts)
        self.assertEquals(term.status, t_status)
        self.assertDictEqual(term.export(), expected_export,
                             "Incorrect Term export")

    def test_validate_version_pass(self):
        """Test that validate version passes correct formats"""
        validate_version("0.0.1")
        self.assertTrue(True)

    def test_validate_version_fail(self):
        """Test that validate version fails bad formats"""
        self.assertRaises(ValidationError, validate_version, "0.0..1")


@tag('unit')
class NeoTermTests(unittest.TestCase):

    @patch('core.models.NeoTerm.save')
    def test_create_neoterm(self, mock_save):
        term = NeoTerm(term='test', 
                       definition='This is the definition of the test term',
                       context='testContext1', 
                       context_description='This is the description of the context')
        
        term.save()

        self.assertIsNotNone(term.uid)
        self.assertEqual(term.term, 'test')
        self.assertEqual(term.definition, 'This is the definition of the test term')
        self.assertEqual(term.context, 'testContext1')
        self.assertEqual(term.context_description, 'This is the description of the context')
        self.assertTrue(mock_save.called)
        mock_save.assert_called_once()
    
    @patch('core.models.NeoTerm.save')
    def test_required_fields_neoterm(self, mock_save):
        mock_save.side_effect = ValueError

        with self.assertRaises(ValueError):
            term = NeoTerm(term=None, definition="This is the definition of the test term", context="testContext1", context_description="This is the description of the context")
            term.save()
        with self.assertRaises(ValueError):
            term = NeoTerm(term="test", definition=None, context="testContext1", context_description="This is the description of the context")
            term.save()
        with self.assertRaises(ValueError):
            term = NeoTerm(term="test", definition="This is the definition of the test term", context=None, context_description="This is the description of the context")
            term.save()
        with self.assertRaises(ValueError):
            term = NeoTerm(term="test", definition="This is the definition of the test term", context="testContext1", context_description=None)
            term.save()
        self.assertTrue(mock_save.called)  