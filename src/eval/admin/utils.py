import csv
from datetime import timedelta
import types

from django.db.models import OuterRef, Subquery
from django.http import HttpResponse
from django.utils.safestring import mark_safe

from eval import models
from eval import constants


def get_initial_site_pks():
    return [
        {"site": pk} for pk in models.Site.objects.values_list("pk", flat=True)
    ]


def get_site_numbers():
    return models.Site.objects.values_list("number", flat=True)


def format_seconds(
    value,
    empty_sign="&nbsp;&nbsp;",
    default_color="",
    colorful=True,
    signed=True,
):

    if value == 0:
        color = default_color
        sign = empty_sign
    elif value < 0:
        color = "green"
        sign = "-"
    else:
        color = "red"
        sign = "+"

    if not colorful:
        color = default_color

    if not signed:
        sign = empty_sign

    seconds = f"{sign}{timedelta(seconds=abs(value))}"

    if colorful:
        return mark_safe(
            f'<span style="color: {color}">{seconds}</span>'
        )

    return mark_safe(seconds)


def format_like_table(labels, values, distinguish_last=True):
    text = ""
    for index, items in enumerate(zip(labels, values)):
        label, value = items

        if distinguish_last and index + 1 == len(values):
            label = f"<strong>{label}</strong>"
            value = f"<strong>{value}</strong>"

        text += (
            '<span style="display:table-row">'
            f'<span style="display:table-cell">{label}</span>&nbsp;'
            f'<span style="display:table-cell">{value}</span>'
            "</span>"
        )
    return mark_safe(text.strip())


def display_no_data_on_exc(f):
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception:
            return constants.DISPLAY_NO_DATA

    return wrapper


def add_dynamic_get_site_ordering_annotations(qs):
    # Dynamic `get_site_*` ordering annotation prep.
    for site_number in get_site_numbers():
        annotation_name = f"site_{site_number}_ann"
        annotation = {
            annotation_name: Subquery(
                models.SiteResult.objects.filter(
                    site__number=site_number, result=OuterRef("pk")
                ).values_list("summary__total_penalty")
            )
        }
        qs = qs.annotate(**annotation)

    return qs


def get_site_total_time_items(obj, apply_formatting=True):
    labels = [constants.STOP_TIME, constants.PENALTY_SK, constants.TOTAL_SK]

    values = [
        obj.summary.stop_time,
        obj.summary.total_penalty,
        obj.summary.total_time,
    ]

    if apply_formatting:
        values = [format_seconds(value) for value in values]

    return labels, values


def get_site_factory(self):
    @display_no_data_on_exc
    def get_site(self, obj):
        site_number = get_site.__name__[-1]
        obj = obj.siteresult_set.get(result=obj, site__number=site_number)
        return format_seconds(obj.summary.total_penalty)

    return get_site


def add_dynamic_get_site_field_methods(self):
    # Dynamic `get_site_*` fields prep.
    dynamic_get_site_fields = []

    for number, name in models.Site.objects.values_list("number", "name"):
        method_name = f"get_site_{number}"

        get_site = get_site_factory(self)
        get_site.__name__ = method_name
        get_site.short_description = f"ST {number}: {name}"
        get_site.admin_order_field = f"site_{number}_ann"

        setattr(self, method_name, types.MethodType(get_site, self))
        dynamic_get_site_fields.append(method_name)

    return dynamic_get_site_fields


def export_results_as_csv(queryset, export_name):
    ARTIFICIAL_TIME_OFFSET = 43200  # 12 hours
    CAT1 = f"ΣΣ ({constants.CATEGORY_SK} 1)"
    CAT2 = f"Σ {constants.PENALTY_SK} ({constants.CATEGORY_SK} 2)"
    CAT_2_OFFSETTED = f"{CAT2} {constants.OFFSET_SK}"

    fields = [constants.ORDER_SK, constants.TEAM_SK]

    siteresult_fields = []
    for siteresut in queryset.first().siteresult_set.all():
        siteresult_fields.extend(
            [
                f"ST{siteresut.site.number} {siteresut.site.name}",
                constants.TIME_SK,
                constants.STOP_TIME,
                constants.VARIANT_SK,
                constants.REFERENCE_VALUE_SK,
                constants.MEASSURED_VALUE_SK,
                constants.PENALTY_SPEED_SK,
                constants.PENALTY_PRECISION_SK,
                constants.CORRECTION_SK,
                f"Σ {constants.PENALTY_SK}",
            ]
        )
    fields.extend(siteresult_fields)
    fields.extend(
        [
            constants.TOTAL_SK,
            constants.ROUTE_SK,
            f"Σ {constants.STOP_TIME}",
            CAT2,
            CAT_2_OFFSETTED,
            CAT1,
        ]
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f"attachment; filename={export_name}.csv"

    writer = csv.writer(response)
    writer.writerow(fields)

    fields_to_convert = {
        constants.MEASSURED_VALUE_SK,
        constants.PENALTY_SPEED_SK,
        constants.PENALTY_PRECISION_SK,
        constants.CORRECTION_SK,
        CAT2,
    }
    indexes_to_convert = [index for index, field in enumerate(fields) if field in fields_to_convert]

    for final_position, obj in enumerate(queryset, start=1):
        values = [f"{final_position}.", obj.team]

        siteresult_values = []
        for siteresut in obj.siteresult_set.all():
            siteresult_values.extend(
                [
                    "",
                    siteresut.time,
                    siteresut.stop_time,
                    siteresut.variant.name if siteresut.variant else "",
                    siteresut.variant.reference_value if siteresut.variant else "",
                    siteresut.value,
                    siteresut.summary.time_penalty,
                    siteresut.summary.precision_penalty,
                    siteresut.total_penalty_correction,
                    siteresut.summary.total_penalty,
                ]
            )
        values.extend(siteresult_values)
        values.extend(
            [
                "",
                obj.route_time,
                obj.summary.stop_time,
                obj.summary.total_penalty,
                ARTIFICIAL_TIME_OFFSET + obj.summary.total_penalty,
                obj.summary.total_time,
            ]
        )

        for index, value in enumerate(values):
            if isinstance(value, (str, float)):
                continue
            elif value is None:
                value = 0
            elif isinstance(value, int):
                value = value
            else:
                # Assuming `datetime.timedelta`.
                value = value.seconds

            if index in indexes_to_convert:
                values[index] = format_seconds(value, empty_sign="", colorful=False)
            else:
                values[index] = str(timedelta(seconds=abs(value)))

        writer.writerow(values)

    return response
