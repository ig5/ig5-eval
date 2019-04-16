from datetime import datetime, timedelta

from django.test import TestCase

from eval import models
from eval.tests.factories import ResultFactory, SiteFactory


class SiteTestCase(TestCase):
    def test_result_updates_after_site_change(self):
        """
        Test updates to site and/or site variant propagates to site results.
        """
        site = SiteFactory.create(
            task=models.TASK_EVAL_REPORTED_RESULT,
            time_limit=3,
            time_limit_diff_penalty=5,
            missed_penalty=45,
            time_limit_max=10,
            time_limit_max_penalty=35,
        )

        site_variant = models.SiteVariant.objects.create(
            name="-",
            reference_value=123,
            unit="m",
            precision=1,
            deviation_tolerance=3,
            deviation_tolerance_penalty=5,
            deviation_tolerance_max=10,
            deviation_tolerance_max_penalty=35,
            site=site,
        )

        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=5 * 60),
            value=125,
            site=site,
            variant=site_variant,
            result=ResultFactory.create(),
        )
        self.assertEqual(site_result.total_time, 600)

        # Update site.
        site.time_limit = 4
        site.save()

        site_result.refresh_from_db()
        self.assertEqual(site_result.total_time, 300)

        # Update site variant.
        site_variant.reference_value = 456
        site_variant.save()

        site_result.refresh_from_db()
        self.assertEqual(site_result.total_time, 2400)


class ResultBase:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.site1 = cls.create_site1()
        cls.site2 = cls.create_site2()
        cls.site3 = cls.create_site3()

    @classmethod
    def create_site1(cls):
        """
        Typical measurement like site; e.g. elevation diff, area, etc..
        """
        site1 = SiteFactory.create(
            task=models.TASK_EVAL_REPORTED_RESULT,
            time_limit=5,
            time_limit_diff_penalty=3,
            missed_penalty=55,
        )
        models.SiteVariant.objects.create(
            name="A",
            reference_value=123,
            unit="m",
            precision=1,
            deviation_tolerance=3,
            deviation_tolerance_penalty=5,
            deviation_tolerance_max=10,
            deviation_tolerance_max_penalty=35,
            site=site1,
        )
        return site1

    @classmethod
    def create_site2(cls):
        """
        Specific measurement site; e.g. C/Hz.
        """
        site2 = SiteFactory.create(
            task=models.TASK_EVAL_REPORTED_RESULT,
            time_limit=3,
            time_limit_diff_penalty=5,
            missed_penalty=45,
            time_limit_max=10,
            time_limit_max_penalty=35,
        )
        models.SiteVariant.objects.create(
            name="-",
            reference_value=0,
            unit="pen min",
            precision=1,
            deviation_tolerance=0,
            deviation_tolerance_penalty=1,
            deviation_tolerance_max=34,
            deviation_tolerance_max_penalty=35,
            site=site2,
        )
        return site2

    @classmethod
    def create_site3(cls):
        """
        Test site.
        """
        return SiteFactory.create(
            task=models.TASK_EVAL_CORRECT_ANSWERS,
            time_limit=8,
            time_limit_diff_penalty=5,
            missed_penalty=50,
        )

    def _get_stop_time(self, minutes):
        stop_time_start = datetime.now()
        stop_time_end = stop_time_start + timedelta(seconds=minutes * 60)

        return {
            "stop_time_start": stop_time_start.time(),
            "stop_time_end": stop_time_end.time(),
        }


class SiteResultTestCase(ResultBase, TestCase):
    # ======================================================================= #
    # Site1 tests.                                                            #
    # ======================================================================= #
    def test_site1_fast_and_precise(self):
        """
        Test negative time penalty is awarded when time is under `time_limit`
        and the measurement is within `deviation_tolerance`.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=4 * 60),
            value=125,
            site=self.site1,
            variant=self.site1.sitevariant_set.first(),
            result=ResultFactory.create(),
            **self._get_stop_time(2),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, -120)
        self.assertEqual(site_result.time_penalty, -180)
        self.assertEqual(site_result.precision_penalty, 0)
        self.assertTrue(site_result.precision_within_tolerance)
        self.assertTrue(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, 0)
        self.assertEqual(site_result.total_penalty, -180)
        self.assertEqual(site_result.total_time, -300)

    def test_site1_fast_and_imprecise(self):
        """
        Test negative time penalty is not awarded when time is under
        `time_limit` but the measurement is over `deviation_tolerance`.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=4 * 60),
            value=130,
            site=self.site1,
            variant=self.site1.sitevariant_set.first(),
            result=ResultFactory.create(),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, 0)
        self.assertEqual(site_result.time_penalty, -180)
        self.assertEqual(site_result.precision_penalty, 1200)
        self.assertFalse(site_result.precision_within_tolerance)
        self.assertTrue(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, 180)
        self.assertEqual(site_result.total_penalty, 1200)
        self.assertEqual(site_result.total_time, 1200)

    def test_site1_fast_and_very_imprecise(self):
        """
        Test negative time penalty is not awarded when time is under
        `time_limit` but the measurement is over `deviation_tolerance_max`.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=4 * 60),
            value=140,
            site=self.site1,
            variant=self.site1.sitevariant_set.first(),
            result=ResultFactory.create(),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, 0)
        self.assertEqual(site_result.time_penalty, -180)
        self.assertEqual(site_result.precision_penalty, 2100)
        self.assertFalse(site_result.precision_within_tolerance)
        self.assertFalse(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, 180)
        self.assertEqual(site_result.total_penalty, 2100)
        self.assertEqual(site_result.total_time, 2100)

    def test_site1_slow_and_precise(self):
        """
        Test time penalty is awarded when time is over `time_limit` and the
        measurement is within `deviation_tolerance`.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=5.5 * 60),
            value=124,
            site=self.site1,
            variant=self.site1.sitevariant_set.first(),
            result=ResultFactory.create(),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, 0)
        self.assertEqual(site_result.time_penalty, 90)
        self.assertEqual(site_result.precision_penalty, 0)
        self.assertTrue(site_result.precision_within_tolerance)
        self.assertTrue(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, 0)
        self.assertEqual(site_result.total_penalty, 90)
        self.assertEqual(site_result.total_time, 90)

    def test_site1_slow_and_imprecise(self):
        """
        Test precision and time penalty are awarded when time is over
        `time_limit` and the measurement is over `deviation_tolerance`.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=5.5 * 60),
            value=129,
            **self._get_stop_time(5),
            site=self.site1,
            variant=self.site1.sitevariant_set.first(),
            result=ResultFactory.create(),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, -300)
        self.assertEqual(site_result.time_penalty, 90)
        self.assertEqual(site_result.precision_penalty, 900)
        self.assertFalse(site_result.precision_within_tolerance)
        self.assertTrue(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, 0)
        self.assertEqual(site_result.total_penalty, 990)
        self.assertEqual(site_result.total_time, 690)

    def test_site1_slow_and_imprecise_2(self):
        """
        Test precision and time penalty are awarded when time is over
        `time_limit` and the measurement is over `deviation_tolerance` BUT
        `total_penalty` is max up to `deviation_tolerance_max_penalty`.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=8.5 * 60),
            value=131,
            site=self.site1,
            variant=self.site1.sitevariant_set.first(),
            result=ResultFactory.create(),
            **self._get_stop_time(5),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, -300)
        self.assertEqual(site_result.time_penalty, 630)
        self.assertEqual(site_result.precision_penalty, 1500)
        self.assertFalse(site_result.precision_within_tolerance)
        self.assertTrue(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, -30)
        self.assertEqual(site_result.total_penalty, 2100)
        self.assertEqual(site_result.total_time, 1800)

    def test_site1_very_slow_and_very_imprecise(self):
        """
        Test precision and time penalty are awarded when time is over
        `time_limit` and the measurement is over `deviation_tolerance_max`.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=10 * 60),
            value=135,
            site=self.site1,
            variant=self.site1.sitevariant_set.first(),
            result=ResultFactory.create(),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, 0)
        self.assertEqual(site_result.time_penalty, 900)
        self.assertEqual(site_result.precision_penalty, 2100)
        self.assertFalse(site_result.precision_within_tolerance)
        self.assertFalse(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, 0)
        self.assertEqual(site_result.total_penalty, 3000)
        self.assertEqual(site_result.total_time, 3000)

    def test_site1_very_slow_and_very_imprecise_2(self):
        """
        Test precision and time penalty are awarded when time is over
        `time_limit` and the measurement is over `deviation_tolerance_max` BUT
        `total_penalty` is max up to `missed_penalty`.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=12.5 * 60),
            value=135,
            site=self.site1,
            variant=self.site1.sitevariant_set.first(),
            result=ResultFactory.create(),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, 0)
        self.assertEqual(site_result.time_penalty, 1350)
        self.assertEqual(site_result.precision_penalty, 2100)
        self.assertFalse(site_result.precision_within_tolerance)
        self.assertFalse(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, -150)
        self.assertEqual(site_result.total_penalty, 3300)
        self.assertEqual(site_result.total_time, 3300)

    def test_site1_missed(self):
        """
        Test `missed_penalty` is awarded when the site was missed.
        """
        site_result = models.SiteResult.objects.create(
            missed=True,
            site=self.site1,
            variant=self.site1.sitevariant_set.first(),
            result=ResultFactory.create(),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, 0)
        self.assertEqual(site_result.time_penalty, 0)
        self.assertEqual(site_result.precision_penalty, 0)
        self.assertTrue(site_result.precision_within_tolerance)
        self.assertTrue(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, 0)
        self.assertEqual(site_result.total_penalty, 3300)
        self.assertEqual(site_result.total_time, 3300)

    # ======================================================================= #
    # Site2 tests.                                                            #
    # ======================================================================= #
    def test_site2_fast_and_precise(self):
        """
        Test only time penalty is awarded when time is under `time_limit`
        and the measurement was evaluated as precise.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=2 * 60),
            value=0,
            site=self.site2,
            variant=self.site2.sitevariant_set.first(),
            result=ResultFactory.create(),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, 0)
        self.assertEqual(site_result.time_penalty, -300)
        self.assertEqual(site_result.precision_penalty, 0)
        self.assertTrue(site_result.precision_within_tolerance)
        self.assertTrue(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, 0)
        self.assertEqual(site_result.total_penalty, -300)
        self.assertEqual(site_result.total_time, -300)

    def test_site2_fast_and_imprecise(self):
        """
        Test precison and time penalty are awarded when time is under
        `time_limit` and the measurement was evaluated as imprecise.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=2 * 60),
            value=10,
            site=self.site2,
            variant=self.site2.sitevariant_set.first(),
            result=ResultFactory.create(),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, 0)
        self.assertEqual(site_result.time_penalty, -300)
        self.assertEqual(site_result.precision_penalty, 600)
        self.assertTrue(site_result.precision_within_tolerance)
        self.assertTrue(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, 0)
        self.assertEqual(site_result.total_penalty, 300)
        self.assertEqual(site_result.total_time, 300)

    def test_site2_fast_and_very_imprecise(self):
        """
        Test precison and time penalty are awarded when time is under
        `time_limit` and the measurement was evaluated as over
        `deviation_tolerance_max`.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=2 * 60),
            value=35,
            site=self.site2,
            variant=self.site2.sitevariant_set.first(),
            result=ResultFactory.create(),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, 0)
        self.assertEqual(site_result.time_penalty, -300)
        self.assertEqual(site_result.precision_penalty, 2100)
        self.assertTrue(site_result.precision_within_tolerance)
        self.assertFalse(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, 0)
        self.assertEqual(site_result.total_penalty, 1800)
        self.assertEqual(site_result.total_time, 1800)

    def test_site2_slow_and_precise(self):
        """
        Test only time penalty is awarded when time is over `time_limit`
        and the measurement was evaluated as precise.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=3.5 * 60),
            value=0,
            site=self.site2,
            variant=self.site2.sitevariant_set.first(),
            result=ResultFactory.create(),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, 0)
        self.assertEqual(site_result.time_penalty, 150)
        self.assertEqual(site_result.precision_penalty, 0)
        self.assertTrue(site_result.precision_within_tolerance)
        self.assertTrue(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, 0)
        self.assertEqual(site_result.total_penalty, 150)
        self.assertEqual(site_result.total_time, 150)

    def test_site2_slow_and_imprecise(self):
        """
        Test precison and time penalty are awarded when time is over
        `time_limit` and the measurement was evaluated as imprecise.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=3.5 * 60),
            value=10,
            site=self.site2,
            variant=self.site2.sitevariant_set.first(),
            result=ResultFactory.create(),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, 0)
        self.assertEqual(site_result.time_penalty, 150)
        self.assertEqual(site_result.precision_penalty, 600)
        self.assertTrue(site_result.precision_within_tolerance)
        self.assertTrue(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, 0)
        self.assertEqual(site_result.total_penalty, 750)
        self.assertEqual(site_result.total_time, 750)

    def test_site2_slow_and_very_imprecise(self):
        """
        Test precision and time penalty are awarded when time is over
        `time_limit` and the measurement was evaluated as over
        `deviation_tolerance_max` BUT `total_penalty` is max up to
        `missed_penalty`.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=7.5 * 60),
            value=35,
            site=self.site2,
            variant=self.site2.sitevariant_set.first(),
            result=ResultFactory.create(),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, 0)
        self.assertEqual(site_result.time_penalty, 1350)
        self.assertEqual(site_result.precision_penalty, 2100)
        self.assertTrue(site_result.precision_within_tolerance)
        self.assertFalse(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, -750)
        self.assertEqual(site_result.total_penalty, 2700)
        self.assertEqual(site_result.total_time, 2700)

    def test_site2_not_within_timebox(self):
        """
        Test only `time_limit_max_penalty` is awarded when
        `task_within_timebox` is False.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=10.5 * 60),
            value=20,
            site=self.site2,
            variant=self.site2.sitevariant_set.first(),
            result=ResultFactory.create(),
        )

        self.assertFalse(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, 0)
        self.assertEqual(site_result.time_penalty, 2100)
        self.assertEqual(site_result.precision_penalty, 0)
        self.assertTrue(site_result.precision_within_tolerance)
        self.assertTrue(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, 0)
        self.assertEqual(site_result.total_penalty, 2100)
        self.assertEqual(site_result.total_time, 2100)

    # ======================================================================= #
    # Site3 tests.                                                            #
    # ======================================================================= #
    def test_site3(self):
        """
        Test only `time_limit_max_penalty` is awarded when
        `task_within_timebox` is False.
        """
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=7.5 * 60),
            value=15,
            site=self.site3,
            result=ResultFactory.create(),
        )

        self.assertTrue(site_result.task_within_timebox)
        self.assertEqual(site_result.stop_time, 0)
        self.assertEqual(site_result.time_penalty, -150)
        self.assertEqual(site_result.precision_penalty, -1350)
        self.assertTrue(site_result.precision_within_tolerance)
        self.assertTrue(site_result.precision_within_max_tolerance)
        self.assertEqual(site_result.total_penalty_correction, 0)
        self.assertEqual(site_result.total_penalty, -1500)
        self.assertEqual(site_result.total_time, -1500)


class SummaryTestCase(ResultBase, TestCase):
    def test_result_summary(self):
        """
        Test result summary produces values based on site result summary.
        """
        result = ResultFactory.create(route_shortening_penalty=20)
        # Site1.
        models.SiteResult.objects.create(
            time=timedelta(seconds=4 * 60),
            value=125,
            site=self.site1,
            variant=self.site1.sitevariant_set.first(),
            result=result,
            **self._get_stop_time(2),
        )
        # Site2.
        models.SiteResult.objects.create(
            time=timedelta(seconds=7.5 * 60),
            value=35,
            site=self.site2,
            variant=self.site2.sitevariant_set.first(),
            result=result,
        )
        # Site3.
        models.SiteResult.objects.create(
            time=timedelta(seconds=7 * 60),
            value=12,
            site=self.site3,
            result=result,
        )

        self.assertEqual(result.summary.stop_time, -120)
        # -180 + 1350 - 300
        self.assertEqual(result.summary.time_penalty, 870)
        # 0 + 2100 - 1080
        self.assertEqual(result.summary.precision_penalty, 1020)
        # 870 + 1020 - 750 (750 is time correction for Site3)
        self.assertEqual(result.summary.total_penalty, 1140)
        # 10800 + 1200 (route, shortening penalty)
        self.assertEqual(result.route_time.seconds, 12000)
        # 12000 - 120 + 1140 (route, stop, penalty)
        self.assertEqual(result.summary.total_time, 13020)

    # ======================================================================= #
    # __str__ tests.                                                          #
    # ======================================================================= #
    def test_result_str(self):
        result = ResultFactory.create()
        self.assertEqual(str(result), result.team)

    def test_result_summary_str(self):
        result = ResultFactory.create()
        self.assertEqual(str(result.summary), result.team)

    def test_site_str(self):
        self.assertEqual(
            str(self.site1),
            f"Stanovisko {self.site1.number}: {self.site1.name}",
        )

    def test_site_variant_str(self):
        self.assertEqual(str(self.site1.sitevariant_set.first()), "Varianta A")

    def test_site_result_str(self):
        site_result = models.SiteResult.objects.create(
            time=timedelta(seconds=7.5 * 60),
            value=15,
            site=self.site3,
            result=ResultFactory.create(team="team_x"),
        )
        self.assertEqual(str(site_result), f"team_x - {site_result.site.name}")
