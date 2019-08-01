import jinja2.sandbox


class SandboxedModelEnvironment(jinja2.sandbox.SandboxedEnvironment):
    def is_safe_callable(self, obj):
        if getattr(obj, 'alters_data', False):
            return False
        return super().is_safe_callable(obj)
