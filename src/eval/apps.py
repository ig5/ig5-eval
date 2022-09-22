from django.apps import AppConfig


class EvalConfig(AppConfig):
    name = "eval"
    verbose_name = "Vyhodnotenie"

    def ready(self):
        import eval.signals  # noqa
