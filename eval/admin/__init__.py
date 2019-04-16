from django.contrib import admin
from django.db.models import Case, Count, F, Q, When

from eval import constants
from eval import models
from eval.admin import common
from eval.admin import inlines as eval_inlines
from eval.admin import utils


class SiteAdmin(admin.ModelAdmin):
    fieldsets = (
        (None, {"fields": ("number", "name", "task")}),
        (
            constants.TIMING_SK,
            {
                "fields": (
                    "time_limit",
                    "time_limit_diff_penalty",
                    "missed_penalty",
                    "time_limit_max",
                    "time_limit_max_penalty",
                )
            },
        ),
    )
    inlines = (eval_inlines.SiteVariantInline,)


class ResultAdmin(common.ResultSummaryBase, admin.ModelAdmin):
    actions = ["recalculate_results", "export_as_csv"]
    inlines = [eval_inlines.SiteResultInline, eval_inlines.ResultSummaryInline]
    list_per_page = 1000

    class Media:
        js = ("eval/js/admin/fieldEvents.js",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            missed_sites=Count("siteresult", filter=Q(siteresult__missed=True))
        )
        # 5 days in seconds --> artifical penalty for DSQ teams.
        dsq = 60 * 60 * 24 * 5
        qs = qs.annotate(
            category_1_ordering=Case(
                When(
                    missed_sites__gte=constants.CATEGORY_1_MISSED_SITES_DSQ,
                    then=F("summary__total_time") + dsq,
                ),
                default=F("summary__total_time"),
            ),
            category_2_ordering=Case(
                When(
                    missed_sites__gte=constants.CATEGORY_2_MISSED_SITES_DSQ,
                    then=F("summary__total_penalty") + dsq,
                ),
                default=F("summary__total_penalty"),
            ),
        )
        return utils.add_dynamic_get_site_ordering_annotations(qs)

    def get_list_display(self, request):
        list_display = list(super().get_list_display(request))
        get_site_fields = utils.add_dynamic_get_site_field_methods(self)

        list_display[1:1] = get_site_fields
        return list_display

    def export_as_csv(self, request, queryset):
        return utils.export_results_as_csv(queryset, "ig5-results")

    export_as_csv.short_description = (
        f"Export selected {constants.RESULT_PLURAL_SK} as CSV"
    )

    def recalculate_results(self, request, queryset):
        for result in queryset:
            for site_result in result.siteresult_set.all():
                site_result.save()

            result.save()

    recalculate_results.short_description = (
        f"Recalculate selected {constants.RESULT_PLURAL_SK}"
    )


admin.site.site_header = "International Geodetic Pentathlon"
admin.site.site_url = None
admin.site.register(models.Site, SiteAdmin)
admin.site.register(models.Result, ResultAdmin)
