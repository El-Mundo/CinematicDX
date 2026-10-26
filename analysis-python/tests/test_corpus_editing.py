import unittest
from fractions import Fraction
import numpy as np
from cinematicdx.corpus_editing import adaptive_candidates


class CorpusEditingTests(unittest.TestCase):
    def test_matches_library_for_v_only_including_irregular_pts(self):
        from scenedetect.detectors import AdaptiveDetector
        from scenedetect.common import FrameTimecode,Timecode
        import cv2
        rng=np.random.default_rng(912)
        images=[]
        base=rng.integers(20,70,(16,24,3),dtype=np.uint8)
        for i in range(80):
            if i in [11,12,35,56]:base=rng.integers(0,256,(16,24,3),dtype=np.uint8)
            images.append(np.clip(base.astype(int)+rng.integers(-1,2,base.shape),0,255).astype(np.uint8))
        pts=np.cumsum(rng.choice([20,40,60],len(images))).astype(np.int64);tb=Fraction(1,1000)
        scores=[0.]+[float(cv2.absdiff(x.max(axis=2),y.max(axis=2)).mean()) for x,y in zip(images[:-1],images[1:])]
        detector=AdaptiveDetector(adaptive_threshold=3,min_scene_len=0,window_width=2,min_content_val=15,luma_only=True)
        expected=[]
        for tick,image in zip(pts,images):
            expected.extend(int(t.pts) for t in detector.process_frame(FrameTimecode(Timecode(int(tick),tb),fps=Fraction(1)),image))
        from cinematicdx.shots import _filter_candidates
        expected,_=_filter_candidates(expected,pts.tolist(),int(pts[-1]+40),tb,Fraction(12,100))
        actual,_=adaptive_candidates(scores,pts,int(pts[-1]+40),tb)
        self.assertEqual(expected,actual.tolist())

    def test_zero_background_and_short_terminal_interval(self):
        scores=np.zeros(12);scores[4]=40;scores[9]=50
        pts=np.arange(12)*40
        cuts,suppressed=adaptive_candidates(scores,pts,480,Fraction(1,1000),minimum_seconds=.16)
        self.assertEqual(cuts.tolist(),[160])
        self.assertTrue(any(x['reason']=='terminal_interval_shorter_than_minimum' for x in suppressed))

    def test_invalid_timing_and_nonfinite_measurements_rejected(self):
        for scores,pts in [([0,0,float('nan'),1,0],[0,1,2,3,4]),([0]*5,[0,1,1,3,4])]:
            with self.assertRaises(ValueError):adaptive_candidates(scores,pts,6,Fraction(1,25))
