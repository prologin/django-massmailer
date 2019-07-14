REGISTERED_ENUMS = {}


def register_enum(namespace, enum_name=None):
    def decorator(f):
        nonlocal enum_name
        if enum_name is None:
            enum_name = f.__name__
        REGISTERED_ENUMS[namespace + '.' + enum_name] = f
        return f

    return decorator
