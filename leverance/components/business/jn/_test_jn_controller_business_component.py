import unittest
from unittest.mock import patch
import json

from leverance.components.business.jn.jn_controller_business_component import (
    JNControllerBusinessComponent,
)


class TestController(unittest.TestCase):
    """
    Indeholder tests for JNControllerBusinessComponent.
    """

    beskeder = [
        {
            "call_id": "call_me_maybe",
            "agent_id": "carly_rae",
            "koe_id": "carly_queue",
            "cpr": "1234567890",
            "status": "start",
        },
        {
            "sentence": "don't ask me, I'll never tell",
            "timestamp": "5.0",
            "speaker": "carly_2",
        },
        {
            "sentence": "I threw a wish in the well",
            "timestamp": "0",
            "speaker": "carly_1",
        },
        {
            "call_id": "call_me_maybe",
            "agent_id": "carly_rae",
            "koe_id": "carly_queue",
            "cpr": "1234567890",
            "status": "end",
        },
    ]

    uuid = "TEST-UUID"

    @patch(
        "leverance.components.business.jn.jn_controller_business_component.JNControllerBusinessComponent._extract_messages_blob"
    )
    def test_read_and_sort_messages(self, mock_extract_messages_blob):
        """
        Tester metoden "read_and_sort_messages" for at sikre korrekt håndtering og
        sortering af beskederne fra Azure Blob.

        Beskederne fra Azure Blob mockes og sendes til "read_and_sort_messages"
        metoden.

        De to beskeder har følgende timestamps:
            - Besked 1: 5.0
            - Besked 2: 0

        Teksten fra besked 2 skal derfor komme først i samtalen, da den er sendt først.

        Forventet output:
            - agent_id (str): carly_rae
            - koe_id (str): carly_queue
            - cpr (str): 1234567890
            - samtale (List[dict]): [
                {'speaker': 'carly_1', 'text': "I threw a wish in the well"},
                {'speaker': 'carly_2', 'text': 'don't ask me, I'll never tell'}
              ]
        """

        # Mock besked
        mock_extract_messages_blob.return_value = self.beskeder

        # Initialisér Controller-klassen
        controller = JNControllerBusinessComponent(
            request_uid=self.uuid, config_name=None
        )

        # Kald metoden
        agent_id, koe_id, cpr, samtale = controller.read_and_sort_messages(
            call_id=self.beskeder[0]["call_id"]
        )

        # Tjek resultat
        self.assertEqual(agent_id, self.beskeder[0]["agent_id"])
        self.assertEqual(koe_id, self.beskeder[0]["koe_id"])
        self.assertEqual(cpr, self.beskeder[0]["cpr"])

        forventet_samtale = [
            {
                "speaker": f'{self.beskeder[2]["speaker"]}',
                "sentence": f'{self.beskeder[2]["sentence"]}',
            },
            {
                "speaker": f'{self.beskeder[1]["speaker"]}',
                "sentence": f'{self.beskeder[1]["sentence"]}',
            },
        ]

        self.assertEqual(samtale, forventet_samtale)

    @patch(
        "leverance.components.business.jn.jn_storage_account_business_component.JNStorageAccountBusinessComponent.create_container_client"
    )
    def test_extract_messages_blob(self, mock_create_container_client):
        """
        Tester at metoden _extract_messages_blob udtrækker beskederne korrekt fra Blob.
        Der er en blob til både agent og caller. Begge blobs er i JSON Lines format,
        dvs. hver linje er et JSON-objekt.

        Vi mocker ContainerClient (som forbinder til Azure Blob Storage) samt indholdet
        af de to blobs.

        Vi forventer at beskederne fra begge blobs bliver opdelt korrekt og samlet i én liste.
        """

        # Mock indholdet af de to blobs vha. en side_effect.
        # Vi simulerer at den første blob indeholder de første 2 beskeder,
        # og den anden blob indeholder de sidste 2 beskeder.
        mock_create_container_client.return_value.get_blob_client.return_value.download_blob.return_value.readall.side_effect = [
            "".join(
                json.dumps(besked) + "\n" for besked in self.beskeder[start:end]
            ).encode("utf-8")
            for start, end in [(0, 2), (2, 4)]
        ]

        # Initialisér Controller-klassen
        controller = JNControllerBusinessComponent(request_uid=self.uuid)

        # Kald metoden
        messages = controller._extract_messages_blob(
            call_id=self.beskeder[0]["call_id"],
        )

        # Tjek resultat
        self.assertEqual(messages, self.beskeder)
