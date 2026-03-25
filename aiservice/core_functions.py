import random
import string


def generate_random_id(length: int) -> str:
    """
    Generate a random alphanumeric string of the given length.

    :param length: The length of the random ID.
    Returns: A random alphanumeric string.
    """
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))
