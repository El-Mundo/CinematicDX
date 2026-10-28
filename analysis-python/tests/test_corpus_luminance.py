import unittest
import numpy as np
from cinematicdx import corpus_luminance as c


class CorpusLuminanceTests(unittest.TestCase):
    def test_studio_identity_does_not_merge_regions(self):
        r=c.studio_memberships([dict(name='Studio A',category='Region'),dict(name='Studio B',category='Region')])
        self.assertEqual(len(r),2);self.assertNotEqual(r[0]['studio_id'],r[1]['studio_id'])
        self.assertEqual(sum(x['fractional_weight'] for x in r),1)

    def test_duplicate_production_not_double_weighted(self):
        r=c.studio_memberships([dict(name='Studio A'),dict(name='Studio A'),dict(name='Studio B')])
        self.assertEqual(len(r),2);self.assertEqual(r[0]['fractional_weight'],.5)

    def test_missing_studio_explicit(self):
        self.assertEqual(c.studio_memberships([])[0]['studio_id'],'studio:unknown')

    def test_voronoi_regular_covers_duration(self):
        a,b=c.representation_intervals(np.arange(0,10),10)
        self.assertAlmostEqual((b-a).sum(),10)
        self.assertEqual(a[0],0);self.assertEqual(b[-1],10)

    def test_large_gap_not_filled(self):
        a,b=c.representation_intervals([0,1,20,21],22)
        self.assertLess((b-a).sum(),12)
        self.assertTrue(b[1]<a[2])

    def test_duplicate_pts_rejected(self):
        with self.assertRaises(ValueError):c.representation_intervals([0,0,1],2)

    def test_bins_time_weighted_not_observation_count(self):
        values,coverage=c.bin_samples([0,9],[9,10],[0,1],[0,10])
        self.assertAlmostEqual(values[0],.1);self.assertEqual(coverage[0],1)

    def test_nan_has_no_valid_coverage(self):
        v,coverage=c.bin_samples([0,5],[5,10],[np.nan,1],[0,10])
        self.assertEqual(v[0],1);self.assertEqual(coverage[0],.5)

    def test_change_does_not_bridge_missing_bin(self):
        self.assertEqual(c.finite_change([0,np.nan,10,11]),1)
        self.assertIsNone(c.finite_change([0,np.nan,10]))

    def test_fixed_roi_ignores_border_in_mean(self):
        a=np.zeros((100,100),np.uint8);a[10:90,5:95]=255
        m=c.measurement(a);self.assertEqual(m['roi_mean'],1);self.assertLess(m['full_mean'],1)

    def test_constant_temporal_series_is_flagged(self):
        t=np.arange(120);a=dict(playback_seconds=t,roi_mean=np.ones(120)*.4,full_mean=np.ones(120)*.4,
               roi_spatial_std=np.ones(120)*.2,roi_near_black_fraction=np.zeros(120),roi_near_white_fraction=np.zeros(120))
        result,profiles=c.summarize_samples(a,120)
        self.assertIn('near_constant_temporal_gray',result['quality_flags']);self.assertTrue(np.isnan(profiles['roi_z']).all())

    def test_level_sequence_normalization(self):
        t=np.arange(120);v=np.r_[np.ones(60)*.2,np.ones(60)*.8]
        a=dict(playback_seconds=t,roi_mean=v,full_mean=v,roi_spatial_std=np.ones(120)*.2,
               roi_near_black_fraction=np.zeros(120),roi_near_white_fraction=np.zeros(120))
        result,p=c.summarize_samples(a,120)
        self.assertGreater(result['mean_abs_change_30s_z'],0);self.assertTrue(result['eligible_for_group_comparison'])

    def test_fallback_uses_cadence_not_result_value(self):
        s=dict(temporal_representation_coverage=1,median_sample_gap_seconds=1,p95_sample_gap_seconds=1,valid_position_bin_count=100)
        self.assertFalse(c.needs_dense_fallback(s));s['p95_sample_gap_seconds']=3;self.assertTrue(c.needs_dense_fallback(s))


if __name__=='__main__':unittest.main()
