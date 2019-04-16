from django.contrib import admin
from django.utils.safestring import mark_safe

from eval import constants
from eval import models
from eval.admin import common
from eval.admin import formsets
from eval.admin import utils


class SiteVariantInline(admin.StackedInline):
    extra = 0
    formset = formsets.SiteVariantInlineFormSet
    model = models.SiteVariant

    def has_delete_permission(self, request, obj=None):
        return False


class ResultSummaryInline(common.ResultSummaryBase, admin.TabularInline):
    obj_attr = "result"

    model = models.ResultSummary
    fields = common.ResultSummaryBase.list_display[1:]
    readonly_fields = fields

    def has_delete_permission(self, request, obj=None):
        return False


class SiteResultInline(admin.TabularInline):
    fields = (
        "site",
        "variant",
        "missed",
        "time",
        "value",
        "get_penalty",
        "stop_time_start",
        "stop_time_end",
        "get_time",
    )
    formset = formsets.SiteResultlInlineFormSet
    model = models.SiteResult
    ordering = ("site__number",)
    readonly_fields = ("get_penalty", "get_time")

    def get_extra(self, request, obj=None, **kwargs):
        return len(utils.get_initial_site_pks())

    def get_max_num(self, request, obj=None, **kwargs):
        return self.get_extra(request, obj, **kwargs)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)

        time_placeholder = "hh:mm:ss"
        for field in ("stop_time_start", "stop_time_end"):
            field = formset.form.base_fields[field]
            field.widget.attrs["placeholder"] = time_placeholder

        time = formset.form.base_fields["time"]
        time.widget.attrs["placeholder"] = time_placeholder

        value = formset.form.base_fields["value"]
        value.widget.attrs["placeholder"] = "0.00"

        site = formset.form.base_fields["site"]
        site.disabled = True
        site.widget.can_add_related = False
        site.widget.can_change_related = False

        return formset

    @utils.display_no_data_on_exc
    def get_penalty(self, obj):
        labels = [
            constants.SPEED_SK,
            constants.PRECISION_SK,
            constants.TOTAL_SK,
        ]
        values = [
            utils.format_seconds(obj.summary.time_penalty),
            utils.format_seconds(obj.summary.precision_penalty),
            utils.format_seconds(obj.summary.total_penalty),
        ]

        # Add info about missed penalty.
        if obj.missed:
            labels.insert(2, constants.MISSED_SK)
            values.insert(2, utils.format_seconds(obj.missed_penalty))
        # Add info about penalty correction.
        elif obj.total_penalty_correction:
            labels.insert(2, constants.CORRECTION_SK)
            values.insert(
                2, utils.format_seconds(obj.total_penalty_correction)
            )

        return utils.format_like_table(labels, values)

    get_penalty.short_description = constants.PENALTY_SK

    @utils.display_no_data_on_exc
    def get_time(self, obj):
        labels, values = utils.get_site_total_time_items(obj)
        return utils.format_like_table(labels, values)

    get_time.short_description = mark_safe("&Sigma;")
