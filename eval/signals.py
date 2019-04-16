from django.db.models.signals import post_save
from django.dispatch import receiver

from eval import models


@receiver(post_save, sender=models.Site)
@receiver(post_save, sender=models.SiteVariant)
def update_summaries_after_site(sender, instance, created, **kwargs):
    for result in models.Result.objects.all():
        for site_result in result.siteresult_set.all():
            site_result.summary.take_fields_from_result()

        result.summary.take_fields_from_result()


@receiver(post_save, sender=models.Result)
@receiver(post_save, sender=models.SiteResult)
def update_summaries_after_result(sender, instance, created, **kwargs):
    sender_is_site_result = sender is models.SiteResult

    if sender_is_site_result:
        summary = models.SiteResultSummary
    else:
        summary = models.ResultSummary

    if created:
        instance.summary = summary(result=instance)

    # Update `ResultSummary` after each `SiteResultSummary` change.
    if sender_is_site_result:
        instance.summary.take_fields_from_result()
        instance.result.summary.take_fields_from_result()
