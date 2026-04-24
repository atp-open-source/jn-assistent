import importlib
import unittest
from datetime import UTC, datetime
from time import sleep
from unittest import mock

import numpy as np
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time
from spark_core.testing.base_test_executor import BaseTestExecutor

from leverance import data
from leverance.components.business.jn.jn_notat_business_component import (
    JNNotatBusinessComponent,
)
from leverance.core.common import timeout_handler


class TestJNNotatBusinessComponent(unittest.TestCase):
    """
    Indeholder de forskellige tests for JNNotatBusinessComponent
    """

    data = {
        "call_id": "test-1",
        "genererings_prompt_id": 1,
        "validerings_prompt_id": 2,
        "queue": "kø-1",
        "kr_initialer": "TEST",
        "forretningsomraade": "pension",
        "notat": "Jo selvfølgelig! Her er et beskrivende journalnotat til samtalen:",
        "cpr": "0707070707",
    }
    today = datetime.today()
    topic = "status-test"
    conf = {
        "bootstrap.servers": "localhost:9092",
        "client.id": "test-producer",
    }
    azure_data = {
        "values": [
            {
                "call_id": "gram_test",
                "agent_id": "gram",
                "koe_id": "gram_queue",
                "status": "start",
                "channels": 2,
                "sample_width": 2,
                "frame_rate": 48000,
                "speaker": "caller",
            },
            {
                "call_id": "gram_test",
                "agent_id": "gram",
                "koe_id": "gram_queue",
                "status": "venter på notat",
                "channels": 2,
                "sample_width": 2,
                "frame_rate": 48000,
                "speaker": "caller",
            },
            {
                "call_id": "gram_test",
                "agent_id": "gram",
                "koe_id": "gram_queue",
                "status": f"slut {today}",
                "channels": 2,
                "sample_width": 2,
                "frame_rate": 48000,
                "speaker": "caller",
            },
        ],
        "no_status_value": {  # Mangler 'status' key
            "call_id": "gram_test",
            "agent_id": "gram",
            "koe_id": "gram_queue",
            "channels": 2,
            "sample_width": 2,
            "frame_rate": 48000,
            "speaker": "caller",
        },
    }

    def test_gem_notat(self):
        """
        Komponenten eksekveres som en service, og det tjekkes at metoden "gem_notat"
        skriver en række til tabellen og at indholdet er som defineret. Servicemetoden
        "lookup_for_service" bruges til læse fra tabellen for at tjekke indholdet af
        tabellen er som forventet.
        """

        with JNNotatExecutor() as context:
            uuid = "TEST-UUID"
            komp = JNNotatBusinessComponent(request_uid=uuid, config_name=None)
            komp.session = context.db_leverance.session

            return_val = komp.gem_notat(
                self.data["call_id"],
                self.data["cpr"],
                self.data["genererings_prompt_id"],
                self.data["validerings_prompt_id"],
                self.data["queue"],
                self.data["kr_initialer"],
                self.data["forretningsomraade"],
                self.data["notat"],
            )

            result = komp.lookup_for_service(
                komp.session,
                input_dict={"1": ["1"]},
                output_column_list=list(self.data.keys())[:-1],
            )

            # Forventede antal rækker
            self.assertEqual(1, len(result), "Korrekt antal rækker")

            # Tjek return_val
            self.assertEqual(200, return_val, "korrekt return_val, 200")

            # Det verificeres at tabellen indeholder forventet data
            self.assertEqual(self.data["call_id"], result["call_id"][0], "Korrekt call-id")
            self.assertEqual(
                self.data["genererings_prompt_id"],
                result["genererings_prompt_id"][0],
                "Korrekt genererings_prompt_id",
            )
            self.assertEqual(
                self.data["validerings_prompt_id"],
                result["validerings_prompt_id"][0],
                "Korrekt validerings_prompt_id",
            )
            self.assertEqual(self.data["queue"], result["queue"][0], "Korrekt queue")
            self.assertEqual(
                self.data["kr_initialer"],
                result["kr_initialer"][0],
                "Korrekt kr_initialer",
            )
            self.assertEqual(
                self.data["forretningsomraade"],
                result["forretningsomraade"][0],
                "Korrekt forretningsomraade",
            )
            self.assertEqual(self.data["notat"], result["notat"][0], "Korrekt notat")

    def test_manglende_vaerdier(self):
        """
        Tester at manglende værdier indsættes korrekt, uden at smide en fejl.
        Der indsættes to rækker:
                  - En med manglende call-id, genererings_prompt_id, validerings_prompt_id
                    og queue.
                  - En med manglende cpr-nr, kr-initialer, forretningsomraade og notat.
        Der forventes to rækker indsat:
                  - En med NULL i call-id, genererings_prompt_id, validerings_prompt_id
                    og queue, men værdier i resterende kolonner.
                  - En med NULL i cpr-nr, kr-initialer, forretningsomraade og notat,
                    men værdier i resterende kolonner.
        """

        with JNNotatExecutor() as context:
            uuid = "TEST-UUID"
            komp = JNNotatBusinessComponent(request_uid=uuid)
            komp.session = context.db_leverance.session

            komp.gem_notat(
                None,
                self.data["cpr"],
                None,
                None,
                None,
                self.data["kr_initialer"],
                self.data["forretningsomraade"],
                self.data["notat"],
            )

            komp.gem_notat(
                self.data["call_id"],
                None,
                self.data["genererings_prompt_id"],
                self.data["validerings_prompt_id"],
                self.data["queue"],
                None,
                None,
                "",
            )

            result = komp.lookup_for_service(
                komp.session,
                input_dict={"1": ["1"]},
                output_column_list=list(self.data.keys())[:-1],
            ).replace({np.nan: None})

            # Forventede antal rækker
            self.assertEqual(2, len(result), "Korrekt antal rækker")

            for i in range(2):
                self.assertEqual(
                    [None, self.data["call_id"]][i],
                    result["call_id"][i],
                    "Korrekt call-id",
                )
                self.assertEqual(
                    [None, self.data["genererings_prompt_id"]][i],
                    result["genererings_prompt_id"][i],
                    "Korrekt genererings_prompt_id",
                )
                self.assertEqual(
                    [None, self.data["validerings_prompt_id"]][i],
                    result["validerings_prompt_id"][i],
                    "Korrekt validerings_prompt_id",
                )
                self.assertEqual([None, self.data["queue"]][i], result["queue"][i], "Korrekt queue")
                self.assertEqual(
                    [self.data["kr_initialer"], None][i],
                    result["kr_initialer"][i],
                    "Korrekt kr-initialer",
                )
                self.assertEqual(
                    [self.data["forretningsomraade"], None][i],
                    result["forretningsomraade"][i],
                    "Korrekt forretningsomraade",
                )
                self.assertEqual([self.data["notat"], None][i], result["notat"][i], "Korrekt notat")

    def _get_utc_time(self, insert_minutes_ago: float = 0) -> datetime:
        """
        Hjælpefunktion til at få et UTC datetime objekt, som bruges til at
        specificere, hvornår en besked blev indsat. "insert_minutes_ago" kan bruges til
        at simulere, at en besked er indsat på et tidligere tidspunkt, f. eks betyder
        insert_minutes_ago=5 at beskeden er indsat i køen for 5 minutter siden.
        Standard er at timestamp oprettes for nuværende tidspunkt.
        """
        return datetime.fromtimestamp(
            int(
                (self.today.astimezone(UTC) - relativedelta(minutes=insert_minutes_ago)).timestamp()
            )
        )

    def test_hent_opkald_status_azure(self):
        """
        Tester at det er den seneste besked der hentes fra Azure Queue. Først mockes det,
        at Queue returnerer tre beskeder. Herefter tjekkes det,
        at det kun er opkaldsstatus for den seneste besked, der returneres.
        Yderligere tjekkes at de rigtige fejlbeskeder returneres når:
            - Azure Queue forsøger at hente beskeder fra en kø, der ikke findes
            - Beskeden fra Queue ikke indeholder en 'status' key
        """

        with JNNotatExecutor() as context:
            uuid = "TEST-UUID"
            komp = JNNotatBusinessComponent(uuid)
            komp.session = context.db_leverance.session

            # Mock output fra _hent_messages_azure
            with mock.patch.object(komp, "_hent_messages_azure") as patched:
                patched.return_value = [
                    (
                        self._get_utc_time(),
                        self.azure_data["values"][i],
                    )
                    for i in range(len(self.azure_data["values"]))
                ]

                # Hent status
                status = komp.hent_opkald_status(
                    kr_initialer="test",
                )

                # Mock Queue for ikke-eksisterende kø
                patched.return_value = None

                # Hent opkald status fra kø der ikke eksisterer
                initialer_findes_ikke = "jeg-findes-ikke"
                status_findes_ikke = komp.hent_opkald_status(
                    kr_initialer=initialer_findes_ikke,
                )

                # Mock at Client Queue returner en besked uden 'status' key
                patched.return_value = [
                    (
                        self._get_utc_time(),
                        self.azure_data["no_status_value"],
                    )
                ]

                # Hent opkald status fra besked uden 'status' key
                status_ingen_status = komp.hent_opkald_status(
                    kr_initialer="test",
                )

                # Tjek at det er seneste status der er hentet
                self.assertEqual(self.azure_data["values"][-1]["status"], status, "Korrekt status")

                # Tjek fejlbesked for kø som ikke findes
                self.assertEqual(
                    "no-status",
                    status_findes_ikke,
                    "Korrekt fejlbesked.",
                )

                # Tjek fejlbesked for besked uden 'status' key
                self.assertEqual(
                    "no-status-key",
                    status_ingen_status,
                    "Korrekt fejlbesked.",
                )

    def test_hent_opkald_graenser_azure(self):
        """
        Tester at opkaldsstatus kun returneres for beskeder, der er oprettet inden for
        den sidste time, og at den rigtige fejlbesked returneres for beskeder oprettet
        for en time eller mere siden.

        Det mockes først, at Client Queue retunerer en besked, som er oprettet for en
        time siden. Her forventes det, at der bliver returneret en fejlbesked.
        Dernæst mockes det, at Client Queue returnerer en besked, som er oprettet for
        50 minutter siden. Her forventes det at opkaldsstatus returneres.
        """

        # Kald hent_opkald_status for at hente seneste status på opkald
        with JNNotatExecutor() as context:
            uuid = "TEST-UUID"
            komp = JNNotatBusinessComponent(uuid)
            komp.session = context.db_leverance.session
            kr_initialer = "test"

            with mock.patch.object(komp, "_hent_messages_azure") as patched:
                # Mock besked indsat for en time siden
                patched.return_value = [
                    (
                        self._get_utc_time(insert_minutes_ago=60),
                        self.azure_data["values"][0],
                    )
                ]

                # Hent status på opkald
                status_1 = komp.hent_opkald_status(
                    kr_initialer=kr_initialer,
                )

                # Mock besked indsat for 50 min siden
                patched.return_value = [
                    (
                        self._get_utc_time(insert_minutes_ago=50),
                        self.azure_data["values"][0],
                    )
                ]

                # Hent status på opkald
                status_2 = komp.hent_opkald_status(
                    kr_initialer=kr_initialer,
                )

                # Tjek at korrekt fejlbesked blev returneret for første opkald
                self.assertEqual(
                    "call-state-duration-exceeded",
                    status_1,
                    "Korrekt fejlbesked.",
                )

            # Tjek at korrekt status blev returneret for andet opkald
            self.assertEqual(self.azure_data["values"][0]["status"], status_2, "Korrekt status.")

    def test_hent_notat(self):
        """
        Tester at metoden "hent_notat" returnerer det seneste notat for en given
        kunderådgiver, med mindre et call-id er specificeret, i hvilket tilfælde notatet
        for det call-id skal returneres. Der indsættes to rækker for samme
        kunderådgiver, hvorefter der laves et kald til "hent_notat" med kunderådgiverens
        initialer uden call-id. Det forventes, at det nyeste notat returneres, fordi
        call-id er None. Herefter laves et kald til "hent_notat" med kunderådgiverens
        initialer og et call-id. Her forventes notatet for det givne call-id returneret.
        """

        notater = ["Dette er det første notat.", "Dette er det andet notat."]
        call_ids = ["test-1", "test-2"]
        genererings_prompt_ids = [1, 3]
        validerings_prompt_ids = [2, 4]

        with JNNotatExecutor() as context:
            uuid = "TEST-UUID"
            komp = JNNotatBusinessComponent(request_uid=uuid)
            komp.session = context.db_leverance.session

            # Gem to notater i jn.notat
            komp.gem_notat(
                call_ids[0],
                self.data["cpr"],
                genererings_prompt_ids[0],
                validerings_prompt_ids[0],
                self.data["queue"],
                self.data["kr_initialer"],
                self.data["forretningsomraade"],
                notater[0],
            )

            sleep(1)  # Sleep for at sikre at notaterne har forskellige tidspunkter

            komp.gem_notat(
                call_ids[1],
                self.data["cpr"],
                genererings_prompt_ids[1],
                validerings_prompt_ids[1],
                self.data["queue"],
                self.data["kr_initialer"],
                self.data["forretningsomraade"],
                notater[1],
            )

            # Forsøg at hente seneste notat for kunderådgiver
            test_call_ids = [call_ids[0], None]
            for i, test_call_id in enumerate(test_call_ids):
                result, call_id, status = komp.hent_notat(
                    kr_initialer=self.data["kr_initialer"], call_id=test_call_id
                )

                # Tjek at de korrekte notater blev returneret
                self.assertEqual(notater[i], result, f"Korrekt notat {i+1}")
                self.assertEqual(call_ids[i], call_id, f"Korrekt call_id {i+1}")
                self.assertEqual(200, status, f"Korrekt statuskode {i+1}")

    def test_hent_notat_manglende_vaerdier(self):
        """
        Tester at den korrekte fejlbesked returneres, hvis der ikke bliver fundet noget
        notat for en given kunderådgiver. Der indsættes to rækker i jn.notat. Først
        forsøges det at hente et notat for kr-initialer, som ikke findes, men med et
        call-id der findes på nogle andre kr-initialer. Dernæst forsøges det at hente et
        notat for kr-initialer som findes, men for et call-id der ikke findes på de
        kr-initialer. Til sidst forsøges det at hente et notat for kr-initialer der ikke
        findes, uden at specificere et call-id. Det forventes at den korrekte fejlbesked
        returneres i begge tilfælde.
        """

        notater = ["Dette er det første notat.", "Dette er det andet notat."]
        call_ids = ["test-1", "test-2"]
        kr_initialer = ["TEST", "SAME", "JEG-FINDES-IKKE"]
        genererings_prompt_ids = [1, 3]
        validerings_prompt_ids = [2, 4]

        with JNNotatExecutor() as context:
            uuid = "TEST-UUID"
            komp = JNNotatBusinessComponent(request_uid=uuid)
            komp.session = context.db_leverance.session

            # Gem to notater i jn.notat
            for i in range(len(call_ids)):
                komp.gem_notat(
                    call_ids[i],
                    self.data["cpr"],
                    genererings_prompt_ids[i],
                    validerings_prompt_ids[i],
                    self.data["queue"],
                    kr_initialer[i],
                    self.data["forretningsomraade"],
                    notater[i],
                )

            # Forsøg at hente notat for kunderådgiver der ikke findes med et call-id der findes på en anden kunderådgiver
            test_call_ids = [call_ids[0], call_ids[0], None]
            kr_initialer[0] = kr_initialer[2]
            for i in range(len(kr_initialer)):
                result, _, status = komp.hent_notat(
                    kr_initialer=kr_initialer[i], call_id=test_call_ids[i]
                )

                # Tjek at de korrekte notater bliver returneret
                self.assertEqual(
                    (
                        f"Intet notat fundet for kunderådgiverinitialer {kr_initialer[i]}"
                        + (f" og call-id {test_call_ids[i]}." if i < 2 else ".")
                    ),
                    result,
                    f"Korrekt notat {i+1}",
                )

                # Tjek at de korrekte statuskoder bliver returneret
                self.assertEqual(204, status, "Korrekt statuskode ")

    def test_hent_notat_fejl(self):
        """
        Tester at den korrekte fejlbesked returneres, hvis der opstår en fejl under
        hentning af notatet. Der mockes en undtagelse i metoden "execute_sql", som
        bruges til at hente notatet. Det forventes at den korrekte fejlbesked returneres
        sammen med en statuskode på 500.
        """

        with JNNotatExecutor() as context:
            uuid = "TEST-UUID"
            komp = JNNotatBusinessComponent(request_uid=uuid)
            komp.session = context.db_leverance.session

            # Mock undtagelse i hentning af notat
            with mock.patch.object(komp, "execute_sql") as patched:
                patched.side_effect = Exception("Der opstod en mystisk SQL fejl :(")

                # Forsøg at hente notat
                result, call_id, status = komp.hent_notat(
                    kr_initialer=self.data["kr_initialer"], call_id=None
                )

                # Tjek at den korrekte fejlbesked og statuskode blev returneret
                self.assertEqual(
                    "Fejl: Der opstod en fejl ved hentning af journalnotat.",
                    result,
                    "Korrekt fejlbesked.",
                )
                self.assertIsNone(call_id, "Korrekt call_id.")
                self.assertEqual(500, status, "Korrekt statuskode.")

    def test_hent_notat_timeout(self):
        """
        Tester at metoden "hent_notat" håndterer timeout korrekt ved at mocke en
        forsinkelse i hentningen af notatet, som overstiger timeout-værdien. Det
        forventes at den korrekte fejlbesked returneres sammen med en statuskode på 504.

        For at testen ikke skal tage for lang tid at køre, mockes run_with_timeout
        decoratoren til at bruge en meget kort timeout-værdi under testen.
        """

        # Gem reference til den rigtige run_with_timeout metode
        real_run_with_timeout = timeout_handler.run_with_timeout

        with mock.patch.object(
            timeout_handler, "run_with_timeout", autospec=True
        ) as patched_timeout:
            # Mock run_with_timeout til at bruge en meget kort timeout-værdi
            patched_timeout.side_effect = lambda timeout, *args, **kwargs: real_run_with_timeout(
                *args, timeout=0.1, **kwargs
            )

            # Reload jn_notat_business_component modulet for at bruge den mockede
            # run_with_timeout metode
            from leverance.components.business.jn import (
                jn_notat_business_component as jn_module,
            )

            importlib.reload(jn_module)

            with JNNotatExecutor() as context:
                uuid = "TEST-UUID"
                # Brug komponenten fra det reloadede modul
                komp = jn_module.JNNotatBusinessComponent(request_uid=uuid)
                komp.session = context.db_leverance.session

                real_execute_sql = komp.execute_sql

                # Mock forsinkelse i hentning af notat
                with mock.patch.object(komp, "execute_sql") as patched:

                    def slow_execute_sql(*args, **kwargs):
                        sleep(1)
                        return real_execute_sql(*args, **kwargs)

                    patched.side_effect = slow_execute_sql

                    # Forsøg at hente notat
                    result, call_id, status = komp.hent_notat(
                        kr_initialer=self.data["kr_initialer"], call_id=None
                    )

                    # Tjek at den korrekte fejlbesked og statuskode blev returneret
                    self.assertEqual(
                        "Fejl: Det tog for lang tid at hente journalnotatet.",
                        result,
                        "Korrekt fejlbesked.",
                    )
                    self.assertIsNone(call_id, "Korrekt call_id.")
                    self.assertEqual(504, status, "Korrekt statuskode.")

    def test_sanering(self):
        """
        Tester at metoden _sanering korrekt sanerer journalnotat data. Der indsættes to rækker i
        tabellen DFD_LEVERANCE_forretning.jn.notat som er hhv. under og over to
        måneder gammel. Derefter kaldes metoden og efterfølgende tjekkes det at notatet
        er saneret i rækken der er over to måneder gammel.
        """

        # Data
        call_ids = ["test-1", "test-2"]
        genererings_prompt_ids = [1, 3]
        validerings_prompt_ids = [2, 4]
        notater = ["Dette er det første notat.", "Dette er det andet notat."]
        forventede_notater = ["Dette er det første notat.", None]

        with JNNotatExecutor() as context:
            uuid = "TEST-UUID"
            komp = JNNotatBusinessComponent(request_uid=uuid)
            komp.session = context.db_leverance.session

            # Gem to notater i jn.notat
            komp.gem_notat(
                call_ids[0],
                self.data["cpr"],
                genererings_prompt_ids[0],
                validerings_prompt_ids[0],
                self.data["queue"],
                self.data["kr_initialer"],
                self.data["forretningsomraade"],
                notater[0],
            )
            with freeze_time(self.today - relativedelta(months=10)):
                komp.gem_notat(
                    call_ids[1],
                    self.data["cpr"],
                    genererings_prompt_ids[1],
                    validerings_prompt_ids[1],
                    self.data["queue"],
                    self.data["kr_initialer"],
                    self.data["forretningsomraade"],
                    notater[1],
                )

            # Kører komponenten i batch-mode
            context.execute_component(komp)

            result = komp.lookup_for_service(
                komp.session,
                input_dict={"1": ["1"]},
                output_column_list=list(self.data.keys())[:-1],
            )

            # Forventede antal rækker
            self.assertEqual(2, len(result), "Korrekt antal rækker")

            # Det verificeres at tabellen indeholder forventet data
            for i in range(len(notater)):
                self.assertEqual(
                    genererings_prompt_ids[i],
                    result["genererings_prompt_id"][i],
                    f"Korrekt genererings_prompt_id {i+1}",
                )
                self.assertEqual(
                    validerings_prompt_ids[i],
                    result["validerings_prompt_id"][i],
                    f"Korrekt validerings_prompt_id {i+1}",
                )
                self.assertEqual(self.data["queue"], result["queue"][i], f"Korrekt queue {i+1}")
                self.assertEqual(
                    self.data["kr_initialer"],
                    result["kr_initialer"][i],
                    f"Korrekt kr_initialer {i+1}",
                )
                self.assertEqual(call_ids[i], result["call_id"][i], f"Korrekt call-id {i+1}")
                self.assertEqual(
                    self.data["forretningsomraade"],
                    result["forretningsomraade"][i],
                    f"Korrekt forretningsomraade {i+1}",
                )
                self.assertEqual(forventede_notater[i], result["notat"][i], f"Korrekt notat {i+1}")

    def test_hent_alle_notater(self):
        """
        Tester, at metoden hent_alle_notater returnerer korrekte notater baseret på datoer
        samt forretningsområder.

        Der indsættes følgende notater:
            - Notat 1: Forretningsområde 'pension', oprettet i dag
            - Notat 2: Forretningsområde 'fy', oprettet i dag
            - Notat 3: Forretningsområde 'pension', oprettet i går
            - Notat 4: Forretningsområde 'fy', oprettet en dag udenfor grænsen (2 måneder)

        Ved dagens_historik=True og ordning_list=['pension'] forventes kun Notat 1 returneret.
        Ved dagens_historik=True og ordning_list=['alle_ordninger'] forventes Notat 1 og Notat 2 returneret.
        Ved dagens_historik=False og ordning_list=['alle_ordninger'] forventes Notat 1, Notat 2 og Notat 3 returneret.
        """

        component = JNNotatBusinessComponent()
        depth = component.history_depth
        today = datetime.now()
        yesterday = today - relativedelta(days=1)

        # Indsæt data i jn.notat
        component.gem_notat(
            "test-call-id-1",
            "0101010101",
            1,
            2,
            "kø-1",
            "LARS",
            "pension",
            "Der var engang en pensionist...",
        )
        component.gem_notat(
            "test-call-id-2",
            "0202020202",
            1,
            2,
            "kø-2",
            "LULU",
            "fy",
            "...som havde en stok",
        )
        with freeze_time(yesterday):
            component.gem_notat(
                "test-call-id-3",
                "0303030303",
                1,
                2,
                "kø-1",
                "AAGE",
                "pension",
                "...og en hat",
            )
        with freeze_time(today - relativedelta(days=depth)):
            component.gem_notat(
                "test-call-id-4",
                "0505050505",
                1,
                2,
                "kø-1",
                "KIM",
                "fy",
                "...men ingen løbesko",
            )

        # Hent notater fra forretningsområdet 'pension' indenfor den angivne tidsperiode dagens_historik=True
        result = component.hent_alle_notater(dagens_historik=True, ordning_list=["pension"])

        # Verificér resultater
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].call_id, "test-call-id-1")

        # Test at alle notater for alle ordninger hentes korrekt
        result_all = component.hent_alle_notater(
            dagens_historik=True, ordning_list=["alle_ordninger"]
        )
        self.assertEqual(len(result_all), 2)

        # Hent notater fra alle forretningsområder indenfor den angivne tidsperiode dagens_historik=False,
        # hvilket vil sige komponentens standardhistorik (2 måneder)
        result = component.hent_alle_notater(dagens_historik=False, ordning_list=["alle_ordninger"])

        # Verificér resultater
        self.assertEqual(len(result), 3)

        # Udtræk call_id'er uden at antage rækkefølge
        ids = {row.call_id for row in result}

        # Tjek at de rigtige er med
        self.assertEqual(
            ids,
            {"test-call-id-1", "test-call-id-2", "test-call-id-3"},
        )

        # Tjek at den gamle (udenfor grænsen) IKKE er med
        self.assertNotIn("test-call-id-4", ids)


class JNNotatExecutor(BaseTestExecutor):
    """
    Varetager indsætning og sletning af testdata, samt eksekvering af komponenten
    """

    def __enter__(self):
        super().__enter__()
        self.delete_testdata()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.delete_testdata()
        super().__exit__(exc_type, exc_val, exc_tb)

    def delete_testdata(self):
        self.db_dfd_leverance_forretning.delete_from_table(data.leverance.business.jn.t_notat)
        self.db_dfd_leverance_forretning.session.commit()
        self.db_dfd_spark_bestand.session.commit()

        self.drop_temp_tables()
        self.delete_output_tables(JNNotatBusinessComponent)

    def execute_component(self, komp):
        """
        Kører komponenten i batch-mode
        """
        komp.execute_all()
