import unittest
from unittest.mock import Mock, patch

from src.modules.email_parser import EmailParser
from src.modules.linkedin_scraper import LinkedInScraper
from src.modules.matcher import JobMatcher
from src.modules.sheets_manager import SheetsManager
from src.modules.telegram_notifier import TelegramNotifier
from src.modules.telegram_source import TelegramJobSource
from main import JobAutomation


class FakeSheets:
    def __init__(self):
        self.saved = []

    def check_already_applied(self, _url):
        return False

    def log_candidate(self, job, status):
        self.saved.append((job, status))
        return True


class SafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matcher = JobMatcher('config/config.json')

    def test_tracking_parameters_do_not_defeat_deduplication(self):
        a = 'https://www.linkedin.com/jobs/view/data-analyst-123?trackingId=one'
        b = 'https://www.linkedin.com/jobs/view/data-analyst-123?trackingId=two'
        self.assertEqual(SheetsManager.canonical_url(a), SheetsManager.canonical_url(b))
        self.assertEqual(SheetsManager.canonical_url(a), 'https://www.linkedin.com/jobs/view/123')
        self.assertEqual(LinkedInScraper._canonical_url(a), LinkedInScraper._canonical_url(b))

    def test_one_character_r_is_not_found_inside_reporting(self):
        self.assertNotIn('r', self.matcher._extract_skills('Reporting analyst creates dashboards'))

    def test_explicit_r_skill_is_detected(self):
        self.assertIn('r', self.matcher._extract_skills('Analysis using R and ggplot2'))

    def test_senior_title_is_excluded(self):
        score, _, recommendation, reason = self.matcher.calculate_score('Senior Data Analyst', 'SQL Power BI')
        self.assertEqual(score, 0)
        self.assertEqual(recommendation, 'exclude')
        self.assertIn('senior', reason.lower())

    def test_support_role_is_excluded(self):
        score, _, recommendation, _ = self.matcher.calculate_score('Customer Support Analyst', 'voice process')
        self.assertEqual(score, 0)
        self.assertEqual(recommendation, 'exclude')

    def test_title_only_job_is_discovered_not_reviewed(self):
        score, skills, recommendation, _ = self.matcher.calculate_score('Data Analyst', '')
        self.assertGreaterEqual(score, 40)
        self.assertEqual(skills, [])
        self.assertEqual(recommendation, 'discovered')

    def test_email_url_is_canonical(self):
        url = EmailParser._canonical_url('https://www.naukri.com/job-listings-data-analyst-123?src=alert')
        self.assertEqual(url, 'https://www.naukri.com/job-listings-data-analyst-123')

    def test_identity_query_is_kept_but_tracking_is_removed(self):
        url = 'https://www.bain.com/careers/find-a-role/position/?jobid=111075&utm_source=telegram'
        expected = 'https://www.bain.com/careers/find-a-role/position?jobid=111075'
        self.assertEqual(SheetsManager.canonical_url(url), expected)
        self.assertEqual(TelegramJobSource.canonical_url(url), expected)

    def test_oracle_preview_url_becomes_stable_job_url(self):
        url = 'https://careers.americanexpress.com/en/sites/CX_1/jobs/preview/26016680/?keyword=analyst'
        self.assertEqual(
            TelegramJobSource.canonical_url(url),
            'https://careers.americanexpress.com/en/sites/CX_1/job/26016680'
        )

    def test_telegram_post_splits_jobs_and_excludes_social_links(self):
        text = '''American Express
Position: Analyst - Data Analytics
Location: Gurugram
Apply Now:
https://careers.example.com/job/101
Quest Global
Position: Data Analyst - Tableau Developer
Location: Hyderabad
Apply Now:
https://careers.example.com/job/102
Join WhatsApp: https://whatsapp.com/channel/example'''
        jobs = TelegramJobSource.candidates_from_text(
            text,
            ['https://careers.example.com/job/101?utm_source=tg',
             'https://careers.example.com/job/102',
             'https://whatsapp.com/channel/example'],
            'Telegram: test', 'https://t.me/test/1', '2026-11-19T10:00:00+00:00'
        )
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]['company'], 'American Express')
        self.assertEqual(jobs[1]['company'], 'Quest Global')
        self.assertTrue(all('whatsapp' not in job['url'] for job in jobs))

    def test_telegram_support_role_is_rejected_before_fetch(self):
        jobs = TelegramJobSource.candidates_from_text(
            'Company Example\nRole: Customer Support Analyst\nhttps://jobs.example.com/1',
            ['https://jobs.example.com/1'], 'Telegram: test', '', '2026-11-19T10:00:00+00:00'
        )
        self.assertEqual(jobs, [])

    def test_telegram_summary_never_claims_application_submission(self):
        notifier = TelegramNotifier()
        notifier.token = 'test-token'
        notifier.chat_id = '123'
        notifier.expected_username = 'SoumyadipSAMCareerBot'
        notifier.base = 'https://api.telegram.org/bottest-token'
        get_response = Mock()
        get_response.json.return_value = {'ok': True, 'result': {'username': 'SoumyadipSAMCareerBot'}}
        get_response.raise_for_status.return_value = None
        post_response = Mock()
        post_response.json.return_value = {'ok': True, 'result': {}}
        post_response.raise_for_status.return_value = None
        with patch('src.modules.telegram_notifier.requests.get', return_value=get_response), \
             patch('src.modules.telegram_notifier.requests.post', return_value=post_response) as post:
            notifier.send_summary({'scanned': 5, 'saved': 1, 'review': 1, 'duplicates': 0, 'skipped': 4, 'errors': 0}, [{
                'title': 'Data Analyst', 'company': 'Example', 'location': 'Kolkata', 'url': 'https://example.com/job/1'
            }])
        message = post.call_args.kwargs['json']['text']
        self.assertNotIn('Application Submitted', message)
        self.assertIn('No applications were submitted automatically', message)

    def test_excluded_job_is_never_saved(self):
        automation = JobAutomation.__new__(JobAutomation)
        automation.sheets = FakeSheets()
        automation.matcher = self.matcher
        automation.stats = {'scanned': 0, 'saved': 0, 'review': 0, 'skipped': 0, 'duplicates': 0, 'errors': 0}
        automation.failures = []
        import logging
        automation.logger = logging.getLogger('safety-test')
        automation.process_job({
            'title': 'Senior Customer Support Analyst',
            'description': 'Voice process',
            'url': 'https://example.com/job/1',
            'company': 'Example',
        })
        self.assertEqual(automation.sheets.saved, [])
        self.assertEqual(automation.stats['skipped'], 1)


if __name__ == '__main__':
    unittest.main()
