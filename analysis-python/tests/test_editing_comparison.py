import unittest
from cinematicdx.editing_comparison import conditional_studio_reference,transient_return_flags,bounded_roundoff_copy
import numpy as np


class ConditionalStudioReferenceTests(unittest.TestCase):
    def test_epsilon_overshoot_can_be_repaired_without_changing_raw_arrays(self):
        raw=dict(roi_mean=np.array([0.,1.+np.finfo(float).eps]),roi_std=np.array([0.,.3]))
        fixed,record=bounded_roundoff_copy(raw)
        self.assertEqual(fixed['roi_mean'][1],1.)
        self.assertGreater(raw['roi_mean'][1],1.)
        self.assertEqual(len(record['changes']['roi_mean']),1)

    def test_substantive_range_error_and_nan_cannot_be_silently_repaired(self):
        for value in [1.0001,-.001,float('nan')]:
            with self.assertRaises(ValueError):bounded_roundoff_copy(dict(roi_mean=np.array([value]),roi_std=np.array([0.])))
    def test_transient_return_is_a_flag_but_sustained_cut_is_not(self):
        times=np.arange(20)/25;images=np.zeros((20,4,4),np.uint8);images[8]=255
        self.assertEqual(len(transient_return_flags(times,images,[8/25])),1)
        images[8:]=255
        self.assertEqual(transient_return_flags(times,images,[8/25]),[])

    def test_sparse_exact_width_cells_remain_blocked(self):
        films=[dict(measured=True,studios=[dict(studio_id='a' if i<10 else 'b')],year=1950,film_type='Feature',colour='B&W',
             source_width=300+i,film_key=str(i),primary_cut_candidates_per_minute=float(i)) for i in range(20)]
        self.assertEqual(conditional_studio_reference(films,include_width=True)['status'],'BLOCKED')
        self.assertEqual(conditional_studio_reference(films,permutations=19)['film_n'],20)

    def test_single_studio_year_cells_cannot_support_group_comparison(self):
        films=[dict(measured=True,studios=[dict(studio_id='a' if i<10 else 'b')],year=1950 if i<10 else 1951,
             film_type='Feature',colour='B&W',source_width=640,film_key=str(i),primary_cut_candidates_per_minute=float(i)) for i in range(20)]
        self.assertEqual(conditional_studio_reference(films)['status'],'BLOCKED')
