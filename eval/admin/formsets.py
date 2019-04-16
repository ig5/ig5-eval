from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from eval import constants
from eval import models
from eval.admin import utils


class SiteVariantInlineFormSet(forms.models.BaseInlineFormSet):
    model = models.SiteVariant

    def clean(self):
        super().clean()

        # If there's an error in the inline.
        if not hasattr(self, "cleaned_data"):
            return

        if self.instance.task == models.TASK_EVAL_REPORTED_RESULT:
            if not self.cleaned_data:
                raise ValidationError(
                    _(
                        "Stanovisko typu "
                        f"'{models.TASK_EVAL_REPORTED_RESULT_HUMAN}' musí mať "
                        "minimálne jednu variantu."
                    )
                )


class SiteResultlInlineFormSet(forms.models.BaseInlineFormSet):
    model = models.SiteResult

    def __init__(self, *args, **kwargs):
        exists = kwargs["instance"].pk

        # Preselect sites.
        if not exists:
            kwargs["initial"] = utils.get_initial_site_pks()

        super().__init__(*args, **kwargs)

        # Filter variants per site.
        for index, form in enumerate(self.forms):
            if exists:
                try:
                    site_pk = form.instance.site.pk
                except models.SiteResult.site.RelatedObjectDoesNotExist:
                    # In case a new site was added after a result was created.
                    site = models.Site.objects.get(number=index + 1)
                    site_pk = site.pk
                    form.initial["site"] = site_pk
            else:
                site_pk = form.initial["site"]

            qs = models.SiteVariant.objects.filter(site__pk=site_pk)
            variant = form.fields["variant"]
            variant.queryset = qs

            # Auto select if 0 or 1 variants are available.
            qs_len = len(qs)
            if qs_len <= 1:
                variant.disabled = True
            if qs_len == 1:
                form.initial["variant"] = qs.first().pk

    def clean(self):
        super().clean()

        # If there's an error in the inline.
        if not hasattr(self, "cleaned_data"):
            return

        for index, form_cleaned_data in enumerate(self.cleaned_data):
            if not form_cleaned_data:
                self.forms[index].add_error(
                    "",
                    ValidationError(
                        _(
                            "Stanovisko musí mať vyplnené minimálne "
                            f"'{constants.TIME_SK.lower()}' a "
                            f"'{constants.RESULT_SK.lower()}' "
                            "alebo zakliknuté "
                            f"'{constants.MISSED_SK.lower()}'."
                        )
                    ),
                )
            else:
                if form_cleaned_data["missed"]:
                    continue

                field_errors = [(("time", "value"), _("Zadajte hodnotu."))]

                if form_cleaned_data["site"].sitevariant_set.all():
                    field_errors.append(
                        (("variant",), _("Vyberte jednu z možností."))
                    )

                for fields, error in field_errors:
                    for field in fields:
                        if form_cleaned_data[field] is None:
                            self.forms[index].add_error(
                                field, ValidationError(error)
                            )
