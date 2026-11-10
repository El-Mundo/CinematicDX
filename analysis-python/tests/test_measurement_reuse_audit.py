import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / 'research/quantitative_exploration/scripts/audit_corpus_editing.py'
SPEC = importlib.util.spec_from_file_location('audit_corpus_editing', SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class MeasurementReuseAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name) / 'parent'
        self.current = Path(self.temporary.name) / 'current'
        self.job = {'job_id': 'film-a', 'video_version_id': 'sha256:original-video'}
        directory = self.parent / 'films' / self.job['job_id']
        directory.mkdir(parents=True)
        (self.current / 'films').mkdir(parents=True)
        self.parent_config = {'scope': 'old corpus', 'job_count': 1, 'grouping': 'old description',
                              'primary_ratio': 3, 'source_hashes': {'extractor.py': 'unchanged'}}
        self.write(self.parent / 'config.json', self.parent_config)
        parent_config_sha = AUDIT.sha(self.parent / 'config.json')
        self.receipt = {'config_sha256': parent_config_sha, 'source_sha256': 'original-video'}
        self.write(directory / 'run.json', self.receipt)
        (self.current / 'films' / self.job['job_id']).symlink_to(directory, target_is_directory=True)
        self.config = dict(self.parent_config, scope='updated corpus', job_count=2,
                           grouping='new description', refresh_parent_run=str(self.parent))
        self.write(self.current / 'config.json', self.config)
        self.config_sha = AUDIT.sha(self.current / 'config.json')
        self.reuse = {'schema_version': 1, 'new_job_ids': ['film-b'], 'inherited_jobs': [{
            'job_id': self.job['job_id'], 'parent_run': str(self.parent),
            'receipt_sha256': AUDIT.sha(directory / 'run.json'),
            'config_sha256': parent_config_sha, 'video_version_id': self.job['video_version_id']}]}

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def verify(self, reuse=None):
        return AUDIT.verify_configuration_binding(self.current, self.job, self.receipt,
                                                  self.config, self.config_sha, reuse)

    def test_preserved_parent_receipt_accepts_descriptive_changes(self):
        self.assertTrue(self.verify(self.reuse))

    def test_current_config_receipt_keeps_existing_path(self):
        self.receipt['config_sha256'] = self.config_sha
        self.assertFalse(self.verify())

    def test_missing_or_duplicate_inheritance_record_is_rejected(self):
        for manifest in (None, dict(self.reuse, inherited_jobs=[]),
                         dict(self.reuse, inherited_jobs=self.reuse['inherited_jobs'] * 2)):
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                self.verify(manifest)

    def test_parameter_change_is_rejected(self):
        self.config['primary_ratio'] = 3.5
        with self.assertRaises(ValueError):
            self.verify(self.reuse)

    def test_parent_config_tampering_is_rejected(self):
        self.write(self.parent / 'config.json', dict(self.parent_config, primary_ratio=4))
        with self.assertRaises(ValueError):
            self.verify(self.reuse)

    def test_preserved_receipt_tampering_is_rejected(self):
        self.write(self.current / 'films' / self.job['job_id'] / 'run.json', {'changed': True})
        with self.assertRaises(ValueError):
            self.verify(self.reuse)

    def test_changed_video_and_ambiguous_new_job_are_rejected(self):
        version_changed = copy.deepcopy(self.reuse)
        version_changed['inherited_jobs'][0]['video_version_id'] = 'sha256:other-video'
        new_job_conflict = dict(self.reuse, new_job_ids=[self.job['job_id']])
        for manifest in (version_changed, new_job_conflict):
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                self.verify(manifest)
