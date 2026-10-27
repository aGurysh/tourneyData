import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scrape import _build_export, _parse_timestamp, _utc_timestamp, scrape_tournament, scrape_tourneyx

URL = 'https://tourneyx.com/leaderboard/standings/example'


def snapshot():
    return {
        'source_url': URL, 'scraped_at': '2026-10-26T12:00:00+00:00',
        'capture_version': 2, 'collection_complete': True,
        'metadata': {'id': '26096', 'slug': 'example', 'tournament_title': 'Example',
                     'start_date': '2026-07-18 05:45:00', 'end_date': '2026-07-18 14:30:00',
                     'timezone': 'Eastern', 'measurement_type': 'length',
                     'measurement_name': 'inch', 'total_fish': '5'},
        'standings': {'tournamentId': '26096', 'measurement_type': 'length', 'results': [[
            {'user_id': '10', 'angler_name': 'Test Angler', 'fish_caught': '1',
             'total_fish_length': '18.25', 'culled_fish_records': '3',
             'submissions': [{'fish_length': '18.25', 'fish_type': 'Bass', 'status': '1',
                              'date_taken': '2026-07-18 07:14:23', 'catch_timezone': 'Eastern',
                              'formatted_date_taken': 'Jul 18th, 2026 7:14 am Eastern',
                              'submission_id': '123', 'tournament_id': '26096'}]},
            {'user_id': '11', 'angler_name': 'Zero Fish'}]]},
    }


def first_fish(raw):
    return raw['standings']['results'][0][0]['submissions'][0]


class ExportTests(unittest.TestCase):
    def test_weather_coordinates_and_missing_or_invalid_values(self):
        for value in ('41.09588,-79.68106', None, '', 'bad', '91,0', '0,-181', 'NaN,0', '1,2,3'):
            with self.subTest(value=value):
                raw = snapshot()
                raw['metadata']['lat_lng'] = value
                result = _build_export(raw, {})
                if value == '41.09588,-79.68106':
                    self.assertEqual(result['tournament']['weather_latitude'], '41.09588')
                    self.assertEqual(result['tournament']['weather_longitude'], '-79.68106')
                else:
                    self.assertIsNone(result['tournament']['weather_latitude'])
                    self.assertIsNone(result['tournament']['weather_longitude'])
                    self.assertTrue(any('weather location unavailable' in issue['message'] for issue in result['issues']))
                self.assertTrue(result['summary']['ready_for_review'])

    def test_reversed_tournament_duration_rejected(self):
        raw = snapshot()
        raw['metadata']['end_date'] = '2026-07-18 05:00:00'
        with self.assertRaisesRegex(ValueError, 'end must be after'):
            _build_export(raw, {})

    def test_tournament_lengths_use_full_field_and_nearest_finishing_place(self):
        raw = snapshot()
        first = raw['standings']['results'][0][0]
        first['total_fish_length'] = '20.00'
        first['submissions'][0]['fish_length'] = '20.00'
        other = copy.deepcopy(first)
        other.update(user_id='12', total_fish_length='20.25')
        other['submissions'][0].update(fish_length='20.25', submission_id='124')
        # Unsorted scores and nine zero-fish entrants: nearest place to 1.1 is 1.
        raw['standings']['results'][0] = [first, other] + [
            {'user_id': str(100 + index), 'angler_name': 'Zero Fish'} for index in range(9)]
        for limit in (None, 1):
            result = _build_export(raw, {}, max_anglers=limit)
            self.assertEqual(result['tournament']['winning_length_inches'], '20.25')
            self.assertEqual(result['tournament']['top_10_percent_length_inches'], '20.25')
        self.assertTrue(_build_export(raw, {})['summary']['ready_for_review'])

    def test_top_decile_place_for_exact_fractional_and_small_fields(self):
        for count, place in ((100, 10), (48, 5), (73, 7), (15, 2), (4, 1)):
            with self.subTest(count=count):
                raw = snapshot()
                raw['standings']['results'][0] = [
                    {'user_id': str(index + 1), 'total_fish_length': str(index + 1)}
                    for index in range(count)]
                result = _build_export(raw, {})
                self.assertEqual(result['tournament']['winning_length_inches'], f'{count}.00')
                self.assertEqual(result['tournament']['top_10_percent_length_inches'],
                                 f'{count - place + 1}.00')
                self.assertNotIn('total_length_inches', result['tournament'])

    def test_invalid_standings_scores_do_not_produce_tournament_lengths(self):
        for score in ('NaN', 'Infinity', '-1', '18.251', 'invalid', None):
            with self.subTest(score=score):
                raw = snapshot()
                raw['standings']['results'][0][0]['total_fish_length'] = score
                result = _build_export(raw, {})
                self.assertIsNone(result['tournament']['winning_length_inches'])
                self.assertIsNone(result['tournament']['top_10_percent_length_inches'])
                self.assertFalse(result['summary']['ready_for_review'])

    def test_small_and_empty_field_lengths(self):
        result = _build_export(snapshot(), {})
        self.assertEqual(result['tournament']['winning_length_inches'], '18.25')
        self.assertEqual(result['tournament']['top_10_percent_length_inches'], '18.25')
        raw = snapshot()
        raw['standings']['results'] = [[]]
        result = _build_export(raw, {})
        self.assertIsNone(result['tournament']['winning_length_inches'])
        self.assertIsNone(result['tournament']['top_10_percent_length_inches'])

    def test_export_date_precise_utc_decimal_species_and_source_ids(self):
        result = _build_export(snapshot(), {'locations': [{'name': 'French Creek', 'state': 'PA'}]})
        self.assertEqual(result['tournament']['date'], '2026-07-18')
        self.assertEqual(result['tournament']['starts_at'], '2026-07-18T09:45:00+00:00')
        self.assertEqual(result['tournament']['ends_at'], '2026-07-18T18:30:00+00:00')
        self.assertEqual(result['tournament']['timezone'], 'America/New_York')
        self.assertEqual(result['catches'][0], {
            'angler_name': 'Test Angler', 'catch_time': '2026-07-18T11:14:23+00:00',
            'species': 'Largemouth Bass', 'length_inches': '18.25', 'external_id': '123'})
        self.assertTrue(result['summary']['ready_for_review'])
        self.assertEqual(result['summary']['source_anglers'], 2)
        self.assertEqual(result['summary']['anglers_with_fish'], 1)
        self.assertEqual(result['summary']['reported_culled_fish'], 3)
        self.assertEqual(result['summary']['fish_exported'], 1)

    def test_bad_fish_retained_in_raw_and_reported(self):
        for field, value in [('date_taken', 'invalid'), ('fish_length', 'NaN'),
                             ('fish_length', '0'), ('fish_length', '18.251'), ('status', '0')]:
            with self.subTest(field=field, value=value):
                raw = snapshot()
                first_fish(raw)[field] = value
                original = copy.deepcopy(raw)
                result = _build_export(raw, {})
                self.assertFalse(result['summary']['ready_for_review'])
                self.assertEqual(result['summary']['fish_skipped'], 1)
                self.assertEqual(raw, original)
                self.assertTrue(any(issue.get('fish_index') == 0 for issue in result['issues']))

    def test_unknown_species_and_missing_id_allowed_with_warning(self):
        raw = snapshot()
        first_fish(raw).update(fish_type=None, submission_id=None)
        result = _build_export(raw, {})
        self.assertIsNone(result['catches'][0]['species'])
        self.assertIsNone(result['catches'][0]['external_id'])
        self.assertTrue(result['summary']['ready_for_review'])
        self.assertFalse(result['summary']['locations_assigned'])

    def test_missing_response_and_multiple_groups_rejected(self):
        raw = snapshot()
        raw['standings'] = None
        with self.assertRaisesRegex(ValueError, 'No standings JSON'):
            _build_export(raw, {})
        raw = snapshot()
        raw['standings']['results'].append([])
        with self.assertRaisesRegex(ValueError, 'multiple result groups'):
            _build_export(raw, {})

    def test_missing_fish_and_incorrect_scores_block_review(self):
        for change in ('fish', 'score'):
            raw = snapshot()
            row = raw['standings']['results'][0][0]
            if change == 'fish':
                row['submissions'] = []
            else:
                row['total_fish_length'] = '99.00'
            self.assertFalse(_build_export(raw, {})['summary']['ready_for_review'])

    def test_partial_run_flagged_and_limits_export_only(self):
        raw = snapshot()
        result = _build_export(raw, {}, max_anglers=1)
        self.assertFalse(result['summary']['ready_for_review'])
        self.assertEqual(result['summary']['anglers_processed'], 1)
        self.assertEqual(len(raw['standings']['results'][0]), 2)
        with patch('scrape.scrape_tournament', return_value=result):
            self.assertEqual(len(scrape_tourneyx(URL, max_anglers=1)), 1)

    def test_missing_cached_response_requires_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'example.json'
            raw = snapshot()
            raw.pop('standings')
            output.with_suffix('.raw.json').write_text(json.dumps(raw))
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, '--refresh'):
                scrape_tournament(URL, output_path=output)

    def test_wrong_date_and_conflicting_photo_times_rejected(self):
        for value in ('2026-07-19 07:14:23', '2026-07-18 08:14:23'):
            raw = snapshot()
            first_fish(raw)['date_taken'] = value
            self.assertEqual(_build_export(raw, {})['summary']['fish_skipped'], 1)

    def test_fallback_to_formatted_photo_time(self):
        raw = snapshot()
        first_fish(raw).pop('date_taken')
        result = _build_export(raw, {})
        self.assertEqual(result['catches'][0]['catch_time'], '2026-07-18T11:14:00+00:00')

    def test_duplicate_source_id_blocks_import(self):
        raw = snapshot()
        row = raw['standings']['results'][0][0]
        row['submissions'].append(copy.deepcopy(first_fish(raw)))
        result = _build_export(raw, {})
        self.assertFalse(result['summary']['ready_for_review'])
        self.assertTrue(any('Duplicate source catch ID' in issue['message'] for issue in result['issues']))

    def test_wrong_config_tournament_multiday_and_units_fail(self):
        with self.assertRaisesRegex(ValueError, 'different tournament'):
            _build_export(snapshot(), {'source_url': URL + '-other'})
        raw = snapshot()
        raw['standings']['tournamentId'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'different tournament'):
            _build_export(raw, {})
        for field, value in [('end_date', '2026-07-19 14:30:00'), ('measurement_name', 'cm')]:
            raw = snapshot()
            raw['metadata'][field] = value
            with self.assertRaises(ValueError):
                _build_export(raw, {})

    def test_extra_submissions_preserved_and_flagged_for_coverage_review(self):
        raw = snapshot()
        raw['metadata']['total_fish'] = '1'
        row = raw['standings']['results'][0][0]
        other = copy.deepcopy(first_fish(raw))
        other['submission_id'] = '124'
        row['submissions'].append(other)
        result = _build_export(raw, {})
        self.assertEqual(len(result['catches']), 2)
        self.assertTrue(any('coverage' in issue['message'] for issue in result['issues']))

    def test_dst_and_other_timezone_parsing(self):
        winter = _parse_timestamp('Jan 2nd, 2026 7:14am Central')
        self.assertEqual(_utc_timestamp(winter, ZoneInfo('America/Chicago')).hour, 13)
        for text in ('2026-11-01T01:30:00', '2026-03-08T02:30:00'):
            with self.assertRaisesRegex(ValueError, 'daylight saving'):
                _utc_timestamp(datetime.fromisoformat(text), ZoneInfo('America/New_York'))

    def test_reprocess_old_html_snapshot_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'example.json'
            raw = snapshot()
            raw.update(collection_complete=False, max_anglers=1, fish=[{'bad': 'old DOM data'}])
            output.with_suffix('.raw.json').write_text(json.dumps(raw))
            config = {'locations': [{'name': 'French Creek', 'state': 'PA'}]}
            with patch('scrape._fetch_snapshot') as fetch, redirect_stdout(io.StringIO()):
                result = scrape_tournament(URL, output_path=output, config=config)
            fetch.assert_not_called()
            self.assertEqual(json.loads(output.read_text()), result)
            self.assertTrue(result['summary']['ready_for_review'])
            raw['source_url'] = URL + '-other'
            output.with_suffix('.raw.json').write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, 'Snapshot URL'):
                scrape_tournament(URL, output_path=output)

    def test_plot_adapter_preserves_local_naive_tuples(self):
        result = _build_export(snapshot(), {})
        with patch('scrape.scrape_tournament', return_value=result):
            fish = scrape_tourneyx(URL)[0]
        self.assertEqual(fish[1], datetime(2026, 7, 18, 7, 14, 23))
        self.assertIsNone(fish[1].tzinfo)
        self.assertEqual(fish[2], 18.25)


if __name__ == '__main__':
    unittest.main()
