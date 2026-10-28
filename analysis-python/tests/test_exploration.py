import unittest
import numpy as np
from cinematicdx import exploration as ex


class ExplorationTests(unittest.TestCase):
    def test_actual_exposure_not_frame_average(self):
        b=ex.exposure_bins([0,.9],[.9,1],[0,1],start=0,end=1)
        self.assertAlmostEqual(b['values'][0],.1)
        self.assertAlmostEqual(b['valid_exposure'][0],1)

    def test_missing_exposure_not_zero(self):
        b=ex.exposure_bins([0,.5],[.5,1],[np.nan,2],start=0,end=1)
        self.assertEqual(b['values'][0],2)
        self.assertEqual(b['valid_exposure'][0],.5)
        self.assertTrue(np.isnan(ex.interval_mean(b,0,1)))

    def test_reject_overlap(self):
        with self.assertRaises(ValueError):ex.exposure_bins([0,.5],[.75,1],[1,2],start=0,end=1)

    def test_partial_bins_preserve_exposure(self):
        b=ex.exposure_bins([0,.4,1.1],[.4,1.1,1.6],[1,2,3],start=.2,end=1.4)
        self.assertAlmostEqual(b['total_exposure'].sum(),1.2)

    def test_gradual_gap_splits_complete_intervals(self):
        cuts=[dict(cut_id=str(t),playback_seconds=t) for t in [1,2,4,6,8]]
        gradual=[dict(transition_id='g',start_playback_seconds=3,end_playback_seconds=3.5)]
        r=ex.complete_hard_cut_runs(cuts,gradual,start=0,end=10)
        self.assertEqual([len(x) for x in r['runs']],[1,2])
        self.assertEqual(len(r['excluded_cross_gradual_intervals']),1)
        self.assertEqual([p['duration_seconds'] for p in r['intervals']],[1,2,2])

    def test_no_gap_crossing_adjacency(self):
        r=ex.sequence_statistics([[1,1],[10,10]])
        self.assertEqual(r['adjacent_pair_count'],2)
        self.assertEqual(r['mean_absolute_log_ratio'],0)

    def test_shuffle_deterministic(self):
        a=ex.shuffled_sequence_controls([[1,2,8],[4,8]],draws=12,seed=7)
        b=ex.shuffled_sequence_controls([[1,2,8],[4,8]],draws=12,seed=7)
        self.assertEqual(a,b)

    def test_central_spike_excluded(self):
        v=np.zeros(20);v[9:11]=99
        s=ex.exposure_bins(np.arange(20),np.arange(20)+1,v,start=0,end=20)
        r=ex.changes_at(s,[10],window=5)[0]
        self.assertEqual(r['absolute_change'],0)

    def test_true_level_change(self):
        v=np.r_[np.zeros(10),np.ones(10)]
        s=ex.exposure_bins(np.arange(20),np.arange(20)+1,v,start=0,end=20)
        self.assertEqual(ex.changes_at(s,[10],window=5)[0]['signed_change'],1)

    def test_circular_controls_never_wrap_measurement_windows(self):
        c,o=ex.circular_centers([20,45,75],start=0,end=100,window=5,min_shift=10)
        self.assertTrue(np.all(c>=5) and np.all(c<=95))
        self.assertTrue(np.allclose((c[:,1]-c[:,0])%100,25))
        self.assertEqual(len(c),len(o))

    def test_cut_matching_keeps_narrative_offset(self):
        cuts=[dict(cut_id=str(x),playback_seconds=x) for x in [3,16,24,31,42,52,66,78,86]]
        m=ex.cut_matched_centers([31.3,66.2],cuts,[],start=0,end=90,window=2,draws=10,seed=3)
        self.assertIsNotNone(m['centers'])
        self.assertTrue(np.allclose(m['centers'][:,0]%1,.3))
        self.assertTrue(np.allclose(m['centers'][:,1]%1,.2))

    def test_insufficient_cut_controls_explicit(self):
        cuts=[dict(cut_id='a',playback_seconds=5)]
        r=ex.cut_matched_centers([5],cuts,[],start=0,end=10,window=2,draws=2)
        self.assertEqual(r['status'],'BLOCKED')
        self.assertIsNone(r['centers'])

    def test_rank_ties_and_auc(self):
        self.assertTrue(np.allclose(ex.rankdata([3,1,1]),[2,.5,.5]))
        self.assertEqual(ex.auc([1,1],[1,1]),.5)
        self.assertEqual(ex.auc([2,3],[0,1]),1)
        self.assertIsNone(ex.auc([], [1]))

    def test_dct_offset_invariance_without_clipping(self):
        import cv2
        rng=np.random.default_rng(1);a=rng.integers(30,180,size=(48,64),dtype=np.uint8)
        da=ex.dct_descriptor(a,cv2=cv2);db=ex.dct_descriptor(a+20,cv2=cv2)
        self.assertAlmostEqual(float(da@db),1,places=5)

    def test_constant_dct_is_missing(self):
        import cv2
        self.assertTrue(np.isnan(ex.dct_descriptor(np.ones((48,64),np.uint8)*50,cv2=cv2)).all())

    def test_flow_identical_frames_and_exposure_confound(self):
        import cv2
        rng=np.random.default_rng(3);a=rng.integers(20,180,size=(48,64),dtype=np.uint8)
        same=ex.image_pair_features(a,a,.4,cv2=cv2)
        bright=ex.image_pair_features(a,a+10,.4,cv2=cv2)
        self.assertEqual(same['mad'],0)
        self.assertLess(same['flow_p90_diagonals_per_second'],.001)
        self.assertAlmostEqual(bright['mad'],10/255,places=5)
        self.assertLess(abs(bright['flicker_one_minus_correlation']),1e-10)

    def test_empty_null_is_not_zero_effect(self):
        r=ex.null_summary(1,[np.nan])
        self.assertIsNone(r['control_median'])
        self.assertEqual(r['valid_control_count'],0)


if __name__=='__main__':unittest.main()
