import logging
from .core import NaimCo

# http://docs.python.org/2/howto/logging.html#library-config
# Avoids spurious error messages if no logger is configured by the user

logging.getLogger(__name__).addHandler(logging.NullHandler())

__version__ = "0.0.1"
__author__ = "Yngvi Þór Sigurjónsson"
__email__ = "blitzkopf@gmail.com"

__all__ = ["NaimCo"]
