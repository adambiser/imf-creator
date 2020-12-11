"""A collection of various utility methods."""
import os as _os


def clamp(value, minimum, maximum):
    """Clamps a value within the given range."""
    return max(minimum, min(value, maximum))


def get_file_size(f):
    """Returns the file size for the given file object or file path."""
    try:
        return _os.fstat(f.fileno()).st_size
    except AttributeError:
        return _os.stat(f).st_size


def get_file_extension(filename):
    return _os.path.splitext(filename)[1]


# def get_all_subclasses(cls):
#     """Returns a list of all subclasses of the given class recursively."""
#     subclasses = cls.__subclasses__()
#     for sub in cls.__subclasses__():
#         subclasses += get_all_subclasses(sub)
#     return subclasses
