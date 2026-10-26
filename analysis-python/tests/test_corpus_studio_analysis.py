import unittest
from cinematicdx.corpus_studio_analysis import weighted_quantiles,weighted_mean,group_statistics,year_cell_residuals,resolve_job_film_keys

def film(key,value,studio='a',joint=False):
    studios=[dict(studio_id=studio,fractional_weight=.5 if joint else 1)]
    if joint:studios.append(dict(studio_id='b',fractional_weight=.5))
    return dict(film_key=key,year=1955,colour='B&W',film_type='Feature',studios=studios,video_available=True,
                measured=True,eligible=True,mean_abs_change_30s_z=value)

class CorpusStudioTests(unittest.TestCase):
    def test_hash_bound_alias_keeps_original_claim(self):
        jobs=[dict(job_id='x',film_key='wrong',linkage_status='filename')];docs={'x':dict(video_version_id='sha256:actual')}
        overrides={'bindings':[dict(job_id='x',original_film_key='wrong',film_key='right',expected_video_version_id='sha256:actual',validation_status='assistant_review')]}
        resolved=resolve_job_film_keys(jobs,docs,overrides,{'right','wrong'})
        self.assertEqual(resolved[0]['film_key'],'right');self.assertEqual(resolved[0]['original_film_key'],'wrong');self.assertEqual(jobs[0]['film_key'],'wrong')

    def test_identity_override_rejects_changed_bytes(self):
        job=dict(job_id='x',film_key='wrong');b=dict(job_id='x',original_film_key='wrong',film_key='right',expected_video_version_id='expected',validation_status='review')
        with self.assertRaises(ValueError):resolve_job_film_keys([job],{'x':dict(video_version_id='different')},{'bindings':[b]},{'right'})

    def test_identity_override_does_not_invent_key(self):
        b=dict(job_id='x',original_film_key='wrong',film_key='invented',expected_video_version_id='same',validation_status='review')
        with self.assertRaises(ValueError):resolve_job_film_keys([dict(job_id='x',film_key='wrong')],{'x':dict(video_version_id='same')},{'bindings':[b]},{'wrong'})

    def test_equal_films_not_duration_or_frames(self):
        a,b=film('a',1),film('b',3);a['duration_seconds']=20;b['duration_seconds']=20000
        r=group_statistics([a,b],'a');self.assertEqual(r['mean_abs_change_30s_z__mean'],2)

    def test_joint_films_fractionally_weighted(self):
        r=group_statistics([film('one',0),film('joint',3,joint=True)],'a')
        self.assertEqual(r['eligible_member_films'],2);self.assertEqual(r['eligible_fractional_films'],1.5)
        self.assertEqual(r['mean_abs_change_30s_z__mean'],1)

    def test_missing_videos_in_coverage_not_metrics(self):
        a,b=film('a',1),film('b',999);b.update(video_available=False,measured=False,eligible=False)
        r=group_statistics([a,b],'a');self.assertEqual(r['metadata_member_films'],2);self.assertEqual(r['missing_video_member_films'],1)
        self.assertEqual(r['mean_abs_change_30s_z__mean'],1)

    def test_single_studio_sensitivity_excludes_joint(self):
        r=group_statistics([film('a',1),film('joint',99,joint=True)],'a',single_studio=True)
        self.assertEqual(r['eligible_member_films'],1);self.assertEqual(r['mean_abs_change_30s_z__mean'],1)

    def test_empty_statistics_not_zero_effect(self):
        self.assertIsNone(weighted_mean([],[]));self.assertEqual(weighted_quantiles([],[]),[None]*3)

    def test_year_cells_need_several_films_and_multiple_studios(self):
        a=[film(str(i),i) for i in range(5)];r,d=year_cell_residuals(a)
        self.assertIsNone(r['0']['residual'])
        a[-1]['studios']=[dict(studio_id='b',fractional_weight=1)];r,d=year_cell_residuals(a)
        self.assertEqual(r['0']['residual'],-2);self.assertEqual(r['4']['residual'],2)

if __name__=='__main__':unittest.main()
