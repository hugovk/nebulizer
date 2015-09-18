#!/usr/bin/env python

import unittest
from nebulizer.tools import Tool
from nebulizer.tools import Repository
from nebulizer.tools import ToolPanelSection
from nebulizer.tools import normalise_toolshed_url

class TestTool(unittest.TestCase):
    """
    Tests for the 'Tool' class

    """
    def test_load_tool_data(self):
        tool_data = { u'panel_section_name': u'NGS: Mapping',
                      u'description': u'Reports on methylation status of reads mapped by Bismark', 
                      u'name': u'Bismark Meth. Extractor',
                      u'panel_section_id': u'solexa_tools',
                      u'version': u'0.10.2',
                      u'link': u'/galaxy_dev/tool_runner?tool_id=toolshed.g2.bx.psu.edu%2Frepos%2Fbgruening%2Fbismark%2Fbismark_methylation_extractor%2F0.10.2',
                      u'min_width': -1,
                      u'model_class': u'Tool',
                      u'id': u'toolshed.g2.bx.psu.edu/repos/bgruening/bismark/bismark_methylation_extractor/0.10.2',
                      u'target': u'galaxy_main'}
        tool = Tool(tool_data)
        self.assertEqual(tool.name,'Bismark Meth. Extractor')
        self.assertEqual(tool.description,
                         'Reports on methylation status of reads mapped by '
                         'Bismark')
        self.assertEqual(tool.version,'0.10.2')
        self.assertEqual(tool.panel_section,'NGS: Mapping')
        self.assertEqual(tool.id,
                         'toolshed.g2.bx.psu.edu/repos/bgruening/bismark/'
                         'bismark_methylation_extractor/0.10.2')
        self.assertEqual(tool.tool_repo,
                         'toolshed.g2.bx.psu.edu/bgruening/bismark')

class TestRepository(unittest.TestCase):
    """
    """
    def test_load_repo_data(self):
        repo_data = { u'tool_shed_status':
                      { u'latest_installable_revision': u'True',
                        u'revision_update': u'False',
                        u'revision_upgrade': u'False',
                        u'repository_deprecated': u'False' },
                      u'status': u'Installed',
                      u'name': u'trimmomatic',
                      u'deleted': False,
                      u'ctx_rev': u'2',
                      u'error_message': u'',
                      u'installed_changeset_revision': u'a60283899c6d',
                      u'tool_shed': u'toolshed.g2.bx.psu.edu',
                      u'dist_to_shed': False,
                      u'url': u'/galaxy_dev/api/tool_shed_repositories/68b273cb7d2d6cff',
                      u'id': u'68b273cb7d2d6cff',
                      u'owner': u'pjbriggs',
                      u'uninstalled': False,
                      u'changeset_revision': u'a60283899c6d',
                      u'includes_datatypes': False }
        repo = Repository(repo_data)
        self.assertEqual(repo.name,'trimmomatic')
        self.assertEqual(repo.owner,'pjbriggs')
        self.assertEqual(repo.tool_shed,'toolshed.g2.bx.psu.edu')
        self.assertEqual(repo.id,
                         'toolshed.g2.bx.psu.edu/pjbriggs/trimmomatic')
        revisions = repo.revisions()
        self.assertEqual(len(revisions),1)
        self.assertEqual(revisions[0].revision_number,'2')
        self.assertEqual(revisions[0].changeset_revision,'a60283899c6d')
        self.assertEqual(revisions[0].status,'Installed')
        self.assertFalse(revisions[0].deleted)
        self.assertFalse(revisions[0].revision_update)
        self.assertFalse(revisions[0].revision_upgrade)
        self.assertTrue(revisions[0].latest_revision)
        self.assertEqual(revisions[0].revision_id,'2:a60283899c6d')

    def test_multiple_revisions(self):
        repo_data1 = { u'tool_shed_status':
                       { u'latest_installable_revision': u'True',
                         u'revision_update': u'False',
                         u'revision_upgrade': u'False',
                         u'repository_deprecated': u'False' },
                       u'status': u'Installed',
                       u'name': u'trimmomatic',
                       u'deleted': False,
                       u'ctx_rev': u'2',
                       u'error_message': u'',
                       u'installed_changeset_revision': u'a60283899c6d',
                       u'tool_shed': u'toolshed.g2.bx.psu.edu',
                       u'dist_to_shed': False,
                       u'url': u'/galaxy_dev/api/tool_shed_repositories/68b273cb7d2d6cff',
                       u'id': u'68b273cb7d2d6cff',
                       u'owner': u'pjbriggs',
                       u'uninstalled': False,
                       u'changeset_revision': u'a60283899c6d',
                       u'includes_datatypes': False }
        repo_data2 = { u'tool_shed_status':
                       {u'latest_installable_revision': u'False',
                        u'revision_update': u'False',
                        u'revision_upgrade': u'True',
                        u'repository_deprecated': u'False' },
                       u'status': u'Installed',
                       u'name': u'trimmomatic',
                       u'deleted': False,
                       u'ctx_rev': u'1',
                       u'error_message': u'',
                       u'installed_changeset_revision': u'3358c3d30143',
                       u'tool_shed': u'toolshed.g2.bx.psu.edu',
                       u'dist_to_shed': False,
                       u'url': u'/galaxy_dev/api/tool_shed_repositories/d6f760c242aa425c',
                       u'id': u'd6f760c242aa425c',
                       u'owner': u'pjbriggs',
                       u'uninstalled': False,
                       u'changeset_revision': u'2bd7cdbb6228',
                       u'includes_datatypes': False}
        repo = Repository(repo_data2)
        repo.add_revision(repo_data1)
        self.assertEqual(repo.name,'trimmomatic')
        self.assertEqual(repo.owner,'pjbriggs')
        self.assertEqual(repo.tool_shed,'toolshed.g2.bx.psu.edu')
        self.assertEqual(repo.id,
                         'toolshed.g2.bx.psu.edu/pjbriggs/trimmomatic')
        revisions = repo.revisions()
        # Most recent revision
        self.assertEqual(len(revisions),2)
        self.assertEqual(revisions[0].revision_number,'2')
        self.assertEqual(revisions[0].changeset_revision,'a60283899c6d')
        self.assertEqual(revisions[0].status,'Installed')
        self.assertFalse(revisions[0].deleted)
        self.assertFalse(revisions[0].revision_update)
        self.assertFalse(revisions[0].revision_upgrade)
        self.assertTrue(revisions[0].latest_revision)
        self.assertEqual(revisions[0].revision_id,'2:a60283899c6d')
        # Previous revision
        self.assertEqual(revisions[1].revision_number,'1')
        self.assertEqual(revisions[1].changeset_revision,'2bd7cdbb6228')
        self.assertEqual(revisions[1].status,'Installed')
        self.assertFalse(revisions[1].deleted)
        self.assertFalse(revisions[1].revision_update)
        self.assertTrue(revisions[1].revision_upgrade)
        self.assertFalse(revisions[1].latest_revision)
        self.assertEqual(revisions[1].revision_id,'1:2bd7cdbb6228')

class TestToolPanelSection(unittest.TestCase):
    """
    """
    def test_load_tool_panel_data(self):
        tool_panel_data = { u'model_class': u'ToolSection',
                            u'version': u'',
                            u'elems':
                            [{u'panel_section_name': u'NGS: SAM Tools',
                              u'description': u'call variants',
                              u'name': u'MPileup',
                              u'panel_section_id': u'ngs:_sam_tools',
                              u'version': u'2.0',
                              u'link': u'/galaxy_dev/tool_runner?tool_id=toolshed.g2.bx.psu.edu%2Frepos%2Fdevteam%2Fsamtools_mpileup%2Fsamtools_mpileup%2F2.0',
                              u'min_width': -1,
                              u'model_class': u'Tool',
                              u'id': u'toolshed.g2.bx.psu.edu/repos/devteam/samtools_mpileup/samtools_mpileup/2.0',
                              u'target': u'galaxy_main'}],
                            u'name': u'NGS: SAM Tools',
                            u'id': u'ngs:_sam_tools' }
        section = ToolPanelSection(tool_panel_data)
        self.assertEqual(section.name,'NGS: SAM Tools')
        self.assertEqual(section.id,'ngs:_sam_tools')

class TestNormaliseToolshedUrl(unittest.TestCase):
    """
    Tests for the 'normalise_toolshed_url' function

    """
    def test_full_https_url(self):
        self.assertEqual(
            normalise_toolshed_url('https://toolshed.g2.bx.psu.edu'),
            'https://toolshed.g2.bx.psu.edu')
    def test_full_http_url(self):
        self.assertEqual(
            normalise_toolshed_url('http://127.0.0.1:9009'),
            'http://127.0.0.1:9009')
    def test_no_protocol(self):
        self.assertEqual(
            normalise_toolshed_url('127.0.0.1:9009'),
            'https://127.0.0.1:9009')