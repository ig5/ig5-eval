from datetime import datetime, timedelta

import factory
from eval import models


now = datetime.now()


class ResultFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Result

    team = factory.Sequence(lambda n: f"Team {n}")
    start = now.time()
    finish = (now + timedelta(hours=3)).time()


class SiteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Site

    number = factory.Sequence(lambda n: n)
    name = factory.Sequence(lambda n: f"site {n}")
