from datetime import datetime, date, timedelta

from django.db import models
from django.utils.translation import gettext as _

from eval import constants


TASK_EVAL_REPORTED_RESULT = "reported_result"
TASK_EVAL_REPORTED_RESULT_HUMAN = _("Výsledok merania")
TASK_EVAL_CORRECT_ANSWERS = "correct_answsers"
TASK_EVAL_CORRECT_ANSWERS_HUMAN = _("Počet správnych odpovedí")
TASK_CHOICES = (
    (TASK_EVAL_REPORTED_RESULT, TASK_EVAL_REPORTED_RESULT_HUMAN),
    (TASK_EVAL_CORRECT_ANSWERS, TASK_EVAL_CORRECT_ANSWERS_HUMAN),
)


def get_time_delta(start, end):
    today = date.today()
    start = datetime.combine(today, start)
    stop = datetime.combine(today, end)
    return stop - start


def calculate_precision_penalty(
    reference_value,
    actual_value,
    deviation_tolerance,
    deviation_tolerance_penalty,
    deviation_tolerance_max,
    deviation_tolerance_max_penalty,
    precision,
):
    """
    Returns penalty in seconds!
    """
    within_tolerance = True
    within_max_tolerance = True
    deviation = abs(reference_value - actual_value)

    if deviation <= deviation_tolerance_max:
        if deviation <= deviation_tolerance:
            penalty = 0
        else:
            # Add penalty for each unit over tolerance.
            penalty = (
                abs(deviation - deviation_tolerance)
                * deviation_tolerance_penalty
                / precision
            )
            within_tolerance = False
    else:
        penalty = deviation_tolerance_max_penalty
        within_tolerance = False
        within_max_tolerance = False

    return round(penalty) * 60, within_tolerance, within_max_tolerance


def calculate_time_penalty(reference_time, actual_time, per_second_penalty):
    """
    Returns penalty in seconds!
    """
    # NOTE: These lines are needed for testing with input strings.
    # reference_time = datetime.strptime(reference_time, time_format)
    # actual_time = datetime.strptime(actual_time, time_format)
    delta = reference_time - actual_time
    penalty = delta.seconds
    if delta.days < 0:
        penalty = delta.seconds - 60 * 60 * 24

    return penalty * -1 * per_second_penalty


class ResultSummaryBase(models.Model):
    stop_time = models.IntegerField()
    time_penalty = models.IntegerField()
    precision_penalty = models.IntegerField()
    total_penalty = models.IntegerField()
    total_time = models.IntegerField()

    class Meta:
        abstract = True

    def take_fields_from_result(self):
        fields = (
            "stop_time",
            "time_penalty",
            "precision_penalty",
            "total_penalty",
            "total_time",
        )
        for field in fields:
            setattr(self, field, getattr(self.result, field))
        self.save()


class Result(models.Model):
    team = models.CharField(
        verbose_name=constants.TEAM_SK, max_length=50, unique=True
    )
    start = models.TimeField(verbose_name=constants.START_SK)
    finish = models.TimeField(verbose_name=constants.FINISH_SK)
    route_shortening_penalty = models.IntegerField(
        verbose_name=_("Trest za skracovanie trasy [min]"),
        blank=True,
        default=0,
    )
    route_time = models.DurationField(default=timedelta())

    class Meta:
        verbose_name = constants.RESULT_SK.lower()
        verbose_name_plural = constants.RESULT_PLURAL_SK

    def __str__(self):
        return self.team

    def save(self, *args, **kwargs):
        self.route_time = get_time_delta(self.start, self.finish) + timedelta(
            seconds=self.route_shortening_penalty * 60
        )

        super().save(*args, **kwargs)

    def _get_total(self, field):
        values = []

        for siteresult in self.siteresult_set.all():
            values.append(getattr(siteresult.summary, field))

        return sum(values)

    @property
    def stop_time(self):
        return self._get_total("stop_time")

    @property
    def time_penalty(self):
        return self._get_total("time_penalty")

    @property
    def precision_penalty(self):
        return self._get_total("precision_penalty")

    @property
    def total_penalty(self):
        return self._get_total("total_penalty")

    @property
    def total_time(self):
        return self._get_total("total_time") + self.route_time.seconds


class ResultSummary(ResultSummaryBase):
    result = models.OneToOneField(
        Result,
        on_delete=models.CASCADE,
        related_name=constants.SUMMARY,
        primary_key=True,
    )

    class Meta:
        verbose_name = constants.SUMMARY_SK
        verbose_name_plural = constants.SUMMARY_SK

    def __str__(self):
        return self.result.team


class Site(models.Model):
    number = models.IntegerField(
        verbose_name=_("Číslo"), default=1, unique=True
    )
    name = models.CharField(
        verbose_name=constants.NAME_SK, max_length=50, default=""
    )
    task = models.CharField(
        verbose_name=_("Zapisuje sa"),
        max_length=50,
        choices=TASK_CHOICES,
        help_text=(
            f'{TASK_EVAL_REPORTED_RESULT_HUMAN} - {_("vyhodnocuje sa na základe odchýlky od referenčnej hodnoty")}<br>'  # noqa
            f'{TASK_EVAL_CORRECT_ANSWERS_HUMAN} - {_("počet správnych odpovední = počet bonusových minút")}<br>'  # noqa
        ),
    )

    # Timing.
    time_limit = models.IntegerField(
        verbose_name=_("Časový limit [min]"),
        help_text=_("Čas na zvládnutie úlohy."),
    )
    time_limit_diff_penalty = models.IntegerField(
        verbose_name=_("Hodnotenie rozdielu [sek]"),
        help_text=_(
            "Penalizácia/bonifikácia za každú sekundu nad/pod časový limit."
        ),
    )
    missed_penalty = models.IntegerField(
        verbose_name=_("Trest za vynechanie [min]")
    )
    time_limit_max = models.IntegerField(
        verbose_name=_("Maximálny časový limit [min]"),
        help_text=_("Maximálny čas na zvládnutie úlohy."),
        blank=True,
        null=True,
    )
    time_limit_max_penalty = models.IntegerField(
        verbose_name=_("Hodnotenie maximálneho časového limitu [min]"),
        help_text=_(
            "Jednorázová penalizácia za prekročenie maximálneho času na "
            "zvládnutie úlohy."
        ),
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = constants.SITE_SK.lower()
        verbose_name_plural = constants.SITE_PLURAL_SK
        ordering = ("number",)

    def __str__(self):
        return f"{constants.SITE_SK} {self.number}: {self.name}"


class SiteVariant(models.Model):
    name = models.CharField(
        verbose_name=constants.NAME_SK, max_length=50, default=""
    )
    reference_value = models.FloatField(
        verbose_name=_("Referenčná hodnota"),
        help_text=_("Výsledok meriania stanovený rozhodcami."),
    )
    unit = models.CharField(
        max_length=10,
        verbose_name=_("Jednotka referenčnej hodnoty"),
        help_text=_("Slúži len na popisné účely."),
    )
    precision = models.FloatField(verbose_name=_("Presnosť merania"))
    deviation_tolerance = models.FloatField(
        verbose_name=_("Povolená odchýlka (+/-)")
    )
    deviation_tolerance_penalty = models.IntegerField(
        verbose_name=_("Hodnotenie povolenej odchýlky [min]"),
        help_text=_("Penalizácia za každú jednotku nad povolenú odchýlku."),
    )
    deviation_tolerance_max = models.FloatField(
        verbose_name=_("Maximálna povolená odchýlka")
    )
    deviation_tolerance_max_penalty = models.IntegerField(
        verbose_name=_("Hodnotenie maximálnej povolenej odchýlky [min]"),
        help_text=_(
            "Jednorázová penalizácia za prekročenie maximálnej povolenej "
            "odchýlky."
        ),
    )

    site = models.ForeignKey(Site, on_delete=models.CASCADE)

    class Meta:
        verbose_name = constants.VARIANT_SK.lower()
        verbose_name_plural = _("Presnosť - nie je relevantné pre testy")

    def __str__(self):
        return f"{constants.VARIANT_SK} {self.name}"


class SiteResult(models.Model):
    time = models.DurationField(
        verbose_name=constants.TIME_SK, blank=True, null=True
    )
    stop_time_start = models.TimeField(blank=True, null=True)
    stop_time_end = models.TimeField(blank=True, null=True)
    value = models.FloatField(
        verbose_name=constants.RESULT_SK, blank=True, null=True
    )
    missed = models.BooleanField(
        verbose_name=constants.MISSED_SK, default=False
    )

    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, verbose_name=constants.SITE_SK
    )
    variant = models.ForeignKey(
        SiteVariant,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=constants.VARIANT_SK,
    )
    # TODO: shoudl be handled as OneToOneField - only one SiteResult per site.
    result = models.ForeignKey(Result, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = constants.RESULT_PLURAL_SK

    def __str__(self):
        return f"{self.result.team} - {self.site.name}"

    @property
    def task_within_timebox(self):
        if self.site.time_limit_max is not None:
            return self.time.seconds < self.site.time_limit_max * 60

        return True

    @property
    def stop_time(self):
        if self.missed:
            return 0

        if self.stop_time_end and self.stop_time_start:
            delta = get_time_delta(self.stop_time_start, self.stop_time_end)
            return -delta.seconds

        return 0

    @property
    def missed_penalty(self):
        return self.site.missed_penalty * 60

    @property
    def time_penalty(self):
        if self.missed:
            return 0

        if not self.task_within_timebox:
            # TODO check if not None!
            return self.site.time_limit_max_penalty * 60

        reference_time = timedelta(minutes=self.site.time_limit)
        return calculate_time_penalty(
            reference_time, self.time, self.site.time_limit_diff_penalty
        )

    def _calculate_precision_penalty(self):
        if self.missed:
            return 0, True, True

        return calculate_precision_penalty(
            self.variant.reference_value,
            self.value,
            self.variant.deviation_tolerance,
            self.variant.deviation_tolerance_penalty,
            self.variant.deviation_tolerance_max,
            self.variant.deviation_tolerance_max_penalty,
            self.variant.precision,
        )

    @property
    def precision_penalty(self):
        if self.missed:
            return 0

        if not self.task_within_timebox:
            return 0

        if self.site.task == TASK_EVAL_CORRECT_ANSWERS:
            # Correct answer == 1 point; 1 point == 1.5 bonus minute.
            return -self.value * 90

        return self._calculate_precision_penalty()[0]

    @property
    def precision_within_tolerance(self):
        if self.site.task == TASK_EVAL_CORRECT_ANSWERS:
            return True

        # Deviation tolerance not specified.
        if self.variant.deviation_tolerance == 0:
            return True

        return self._calculate_precision_penalty()[1]

    @property
    def precision_within_max_tolerance(self):
        if self.site.task == TASK_EVAL_CORRECT_ANSWERS:
            return True

        return self._calculate_precision_penalty()[2]

    @property
    def total_penalty_correction(self):
        if self.site.task == TASK_EVAL_CORRECT_ANSWERS:
            return 0

        total_penalty = self._calculate_total_penalty()
        if total_penalty > self.missed_penalty:
            return self.missed_penalty - total_penalty

        # Slow.
        if self.time_penalty > 0:
            # Not precise at all.
            if not self.precision_within_max_tolerance:
                return 0

            if self.variant.deviation_tolerance == 0:
                return 0

            # Not precise.
            dev_max_pen = self.variant.deviation_tolerance_max_penalty * 60
            if total_penalty > dev_max_pen:
                return dev_max_pen - total_penalty
        # Fast.
        elif self.time_penalty < 0:
            if not self.precision_within_tolerance:
                return -self.time_penalty

        return 0

    def _calculate_total_penalty(self):
        if self.missed:
            return self.missed_penalty

        return self.precision_penalty + self.time_penalty

    @property
    def total_penalty(self):
        total_penalty = self._calculate_total_penalty()

        # Slow.
        if self.time_penalty > 0:
            # Not precise at all.
            if not self.precision_within_max_tolerance:
                return min(total_penalty, self.missed_penalty)
            # Not precise.
            elif not self.precision_within_tolerance:
                return min(
                    total_penalty,
                    self.variant.deviation_tolerance_max_penalty * 60,
                )
        # Fast.
        elif self.time_penalty < 0:
            if not self.precision_within_tolerance:
                return total_penalty - self.time_penalty

        return total_penalty

    @property
    def total_time(self):
        if self.missed:
            return self.total_penalty

        return self.total_penalty + self.stop_time


# NOTE: required for ordering by sites in admin.
class SiteResultSummary(ResultSummaryBase):
    result = models.OneToOneField(
        SiteResult,
        on_delete=models.CASCADE,
        related_name=constants.SUMMARY,
        primary_key=True,
    )
