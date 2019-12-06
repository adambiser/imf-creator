"""A collection of various utility methods."""
import os


def clamp(value: int, minimum: int, maximum: int):
    """Clamps a value within the given range."""
    return max(minimum, min(value, maximum))


def get_file_size(fp):
    """Returns the file size for the given file object."""
    return os.fstat(fp.fileno()).st_size


def get_all_subclasses(cls):
    """Returns a list of all subclasses of the given class recusively."""
    subclasses = cls.__subclasses__()
    for sub in cls.__subclasses__():
        subclasses += get_all_subclasses(sub)
    return subclasses
