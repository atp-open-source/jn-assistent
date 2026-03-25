from audio_streamer.config import get_config

from base_jn_user import BaseJNHttpUser
from parameters import ENV, CONTROLLER_VERSION
from utils import disable_insecure_request_warnings, register_listeners

disable_insecure_request_warnings()
register_listeners()


class JNHttpUser(BaseJNHttpUser):
    """
    Locust brugerklasse der simulerer en JN bruger.
    """

    # Audiostreamer konfiguration
    config = get_config(env=ENV, azure=CONTROLLER_VERSION == "azure")

    # Host URL for leverance-endpoints
    host = config.LEVERANCE_URL
