from importlib.metadata import PackageNotFoundError, version


class DistributionNotFound(Exception):
    pass


class _Distribution:
    def __init__(self, package_name):
        self.version = version(package_name)


def get_distribution(package_name):
    try:
        return _Distribution(package_name)
    except PackageNotFoundError as exc:
        raise DistributionNotFound(str(exc)) from exc
