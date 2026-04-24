from queue import Queue
from threading import Event
from unittest import TestCase, mock

from audio_streamer.streamer import (
    MicrophoneRecorder,
    SimpleRecordingManager,
)


class TestMicrophoneRecorder(TestCase):
    def test_create_metadata(self):
        """
        Test the _create_metadata method of MicrophoneRecorder.
        """
        stop_event = Event()
        data_queue = Queue()
        args = {
            "CallID": "test_call",
            "AgentID": "test_agent",
            "Queue": "test_queue",
        }
        recorder = MicrophoneRecorder(stop_event, data_queue, args)
        metadata = recorder._create_metadata(
            status="start",
            channels=1,
            sample_width=2,
            frame_rate=44100,
            speaker="agent",
        )
        self.assertIn("call_id", metadata)
        self.assertIn("agent_id", metadata)


class TestSimpleRecordingManager(TestCase):
    def test_create_flag_file(self):
        """
        Test the _create_flag_file method of SimpleRecordingManager.
        """
        args = {
            "CallID": "test_call",
            "AgentID": "test_agent",
            "Queue": "test_queue",
        }
        config = mock.Mock()
        manager = SimpleRecordingManager(args, config)
        with mock.patch("builtins.open", mock.mock_open()) as mocked_file:
            manager._create_flag_file()
            mocked_file.assert_called_once()

    def test_remove_flag_file(self):
        """
        Test the _remove_flag_file method of SimpleRecordingManager.
        """
        args = {
            "CallID": "test_call",
            "AgentID": "test_agent",
            "Queue": "test_queue",
        }
        config = mock.Mock()
        manager = SimpleRecordingManager(args, config)
        with (
            mock.patch("os.path.exists", return_value=True),
            mock.patch("os.remove") as mocked_remove,
        ):
            manager._remove_flag_file()
            mocked_remove.assert_called_once()
