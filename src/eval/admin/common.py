from django.utils.safestring import mark_safe


from eval import constants
from eval.admin import utils


class ResultSummaryBase:
    obj_attr = ""

    list_display = (
        "team",
        "get_route_time",
        "get_total_stop_time",
        "get_total_penalty",
        "get_total_time",
    )
    exclude = ("route_time",)

    def _get_obj_attr(self, obj):
        if self.obj_attr:
            return getattr(obj, self.obj_attr)

        return obj

    def _get_missed_sites_count(self, obj):
        # NOTE comes from annotation.
        if hasattr(obj, "missed_sites"):
            missed_sites = obj.missed_sites
        else:
            missed_sites = obj.siteresult_set.filter(missed=True).count()

        return missed_sites

    def _format_disqualified(self, formatted_seconds):
        return mark_safe(f"<span>{formatted_seconds} (DSQ)</span>")

    def get_route_time(self, obj):
        obj = self._get_obj_attr(obj)

        return utils.format_seconds(
            obj.route_time.seconds, colorful=False, signed=False
        )

    get_route_time.short_description = constants.ROUTE_SK
    get_route_time.admin_order_field = "route_time"

    def get_total_stop_time(self, obj):
        obj = self._get_obj_attr(obj)

        return utils.format_seconds(obj.summary.stop_time, "&nbsp;")

    get_total_stop_time.short_description = mark_safe(
        f"&Sigma; {constants.STOP_TIME}"
    )
    get_total_stop_time.admin_order_field = "summary__stop_time"

    def get_total_penalty(self, obj):
        obj = self._get_obj_attr(obj)

        formatted_seconds = utils.format_seconds(obj.summary.total_penalty, "")

        missed_sites = self._get_missed_sites_count(obj)
        is_dnf = missed_sites >= constants.CATEGORY_2_MISSED_SITES_DSQ
        if is_dnf:
            return self._format_disqualified(formatted_seconds)

        return formatted_seconds

    get_total_penalty.short_description = mark_safe(
        f"&Sigma; {constants.PENALTY_SK} ({constants.CATEGORY_SK} 2)"
    )
    # NOTE comes from annotation.
    get_total_penalty.admin_order_field = "category_2_ordering"

    def get_total_time(self, obj):
        obj = self._get_obj_attr(obj)

        formatted_seconds = utils.format_seconds(
            obj.summary.total_time, colorful=False, signed=False
        )

        missed_sites = self._get_missed_sites_count(obj)
        is_dnf = missed_sites >= constants.CATEGORY_1_MISSED_SITES_DSQ
        if is_dnf:
            return self._format_disqualified(formatted_seconds)

        return formatted_seconds

    get_total_time.short_description = mark_safe(
        f"&Sigma;&Sigma; ({constants.CATEGORY_SK} 1)"
    )
    # NOTE comes from annotation.
    get_total_time.admin_order_field = "category_1_ordering"
