import unittest
from datetime import datetime
from leverance import data
from spark_core.testing.base_test_executor import BaseTestExecutor
from .jn_samtale_business_component import JNSamtaleBusinessComponent
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time
from sqlalchemy import select


class TestJNSamtaleBusinessComponent(unittest.TestCase):
    """
    Indeholder de forskellige tests for JNSamtaleBusinessComponent
    """

    samtale = [
        {"speaker": "agent", "sentence": "Kunderådgiver snakker."},
        {"speaker": "caller", "sentence": "Borger snakker."},
        {"speaker": "agent", "sentence": "Kunderådgiver snakker igen."},
    ]

    data = {
        "call_id": "test-1",
        "queue": "kø-1",
        "kr_initialer": "TEST",
        "samtale": samtale,
        "cpr": "1111111111",
    }
    today = datetime.today()

    def test_happy_day_scenario(self):
        """
        Komponenten eksekveres som en service, og det tjekkes at metoden "gem_samtale"
        skriver en række til tabellen og at indholdet er som forventet.
        """

        forventede_roller = [
            "Kunderådgiver",
            "Borger/fuldmagtshaver/hjælper",
            "Kunderådgiver",
        ]

        with JNSamtaleExecutor() as context:
            uuid = "ET-MEGET-UNIKT-ID"
            komp = JNSamtaleBusinessComponent(request_uid=uuid, config_name=None)
            komp.session = context.db_leverance.session

            response_code = komp.gem_samtale(
                self.data["call_id"],
                self.data["cpr"],
                self.data["queue"],
                self.data["kr_initialer"],
                self.data["samtale"],
            )

            self.assertEqual(200, response_code, "Korrekt HTTP response_code")

            result = context.fetch_all_results()

            self.assertEqual(len(self.samtale), len(result), "Korrekt antal rækker")

            for i in range(len(self.samtale)):
                # Tjek at data i tabellen matcher de indtastede værdier
                self.assertEqual(
                    self.data["call_id"], result[i].call_id, "Korrekt call_id"
                )
                self.assertEqual(self.data["queue"], result[i].queue, "Korrekt queue")
                self.assertEqual(
                    self.data["kr_initialer"],
                    result[i].kr_initialer,
                    "Korrekt kr_initialer",
                )
                self.assertEqual(
                    self.samtale[i]["sentence"],
                    result[i].tekststykke,
                    "Korrekt tekststykke",
                )
                self.assertEqual(forventede_roller[i], result[i].rolle, "Korrekt rolle")

    def test_manglende_vaerdier(self):
        """
        Tester forventet adfærd ved manglende værdier i de forskellige kolonner.
        Der indsættes tre rækker:
                  - En med manglende samtale
                  - En med manglende call-id
                  - En med manglende cpr-nr, kr_initialer og queue.
        Der forventes:
                  - En http response_code 400 ved første række, da samtalen er tom.
                  - En række i tabellen hvor call-id er NULL og de øvrige kolonner er udfyldt.
                  - En række i tabellen hvor broger_id, kr_initialer og queue er NULL men de øvrige kolonner er udfyldt
        """

        # Input data til test hvor der kun indsættes et samtalestykke per kald
        input_data = [
            {
                "call_id": "test-missing-values-1",
                "cpr": self.data["cpr"],
                "queue": self.data["queue"],
                "kr_initialer": self.data["kr_initialer"],
                "samtale": None,
            },
            {
                "call_id": None,
                "cpr": self.data["cpr"],
                "queue": self.data["queue"],
                "kr_initialer": self.data["kr_initialer"],
                "samtale": [self.data["samtale"][0]],
            },
            {
                "call_id": "test-missing-values-2",
                "cpr": None,
                "queue": None,
                "kr_initialer": None,
                "samtale": [self.data["samtale"][1]],
            },
        ]
        uuid = "TEST-UUID"

        forventede_response_codes = [400, 200, 200]

        for i in range(len(input_data)):
            with JNSamtaleExecutor() as context:
                komp = JNSamtaleBusinessComponent(request_uid=uuid)
                komp.session = context.db_leverance.session

                # Test med call_id og queue
                response_code = komp.gem_samtale(
                    input_data[i]["call_id"],
                    input_data[i]["cpr"],
                    input_data[i]["queue"],
                    input_data[i]["kr_initialer"],
                    input_data[i]["samtale"],
                )

                self.assertEqual(
                    forventede_response_codes[i], response_code, "Korrekt response_code"
                )
                result = context.fetch_all_results()

                if response_code == 200:
                    self.assertEqual(1, len(result), "Korrekt antal rækker")

                    self.assertEqual(
                        input_data[i]["call_id"],
                        result[0].call_id,
                        "Korrekt call_id",
                    )

                    self.assertEqual(
                        input_data[i]["queue"], result[0].queue, "Korrekt queue"
                    )
                    self.assertEqual(
                        input_data[i]["kr_initialer"],
                        result[0].kr_initialer,
                        "Korrekt kr_initialer",
                    )
                    self.assertEqual(
                        input_data[i]["samtale"][0]["sentence"],
                        result[0].tekststykke,
                        "Korrekt tekstsykke",
                    )
                else:
                    # Vi tjekker at hvis der opstod et fejl response så er der ikke indsat noget i tabellen
                    self.assertEqual(0, len(result), "Korrekt antal rækker")

    def test_sanering(self):
        """
        Tester at metoden _sanering korrekt sanerer de transkriberede samtaler. Der indsættes to rækker i
        tabellen DFD_LEVERANCE_forretning.jn.samtale som er hhv. under og over to
        måneder gammel. Derefter kaldes metoden og efterfølgende tjekkes det at samtalestykket
        er saneret i rækken der er over to måneder gammel.
        """
        uuid = "TEST-UUID"

        # Data
        input_data = [
            {
                "call_id": "call_id-1",
                "cpr": self.data["cpr"],
                "queue": self.data["queue"],
                "kr_initialer": self.data["kr_initialer"],
                "samtale": [self.data["samtale"][0]],
            },
            {
                "call_id": "call_id-2",
                "cpr": self.data["cpr"],
                "queue": self.data["queue"],
                "kr_initialer": self.data["kr_initialer"],
                "samtale": [self.data["samtale"][1]],
            },
        ]
        forventede_tekststykker = [self.samtale[0]["sentence"], None]

        with JNSamtaleExecutor() as context:
            komp = JNSamtaleBusinessComponent(request_uid=uuid)
            komp.session = context.db_leverance.session

            # Test med call_id og queue
            komp.gem_samtale(
                input_data[0]["call_id"],
                input_data[0]["cpr"],
                input_data[0]["queue"],
                input_data[0]["kr_initialer"],
                input_data[0]["samtale"],
            )

            with freeze_time(self.today - relativedelta(months=10)):
                komp.gem_samtale(
                    input_data[1]["call_id"],
                    input_data[1]["cpr"],
                    input_data[1]["queue"],
                    input_data[1]["kr_initialer"],
                    input_data[1]["samtale"],
                )

            # Kører komponenten i batch-mode
            context.execute_component(komp)

            # Henter alt data fra komponentens tabel
            result = context.fetch_all_results()

            # Forventede antal rækker
            self.assertEqual(2, len(result), "Korrekt antal rækker")

            # Det verificeres at tabellen indeholder forventet data
            for i in range(len(input_data)):
                self.assertEqual(self.data["queue"], result[i].queue, f"Korrekt queue")
                self.assertEqual(
                    self.data["kr_initialer"],
                    result[i].kr_initialer,
                    f"Korrekt kr_initialer",
                )
                self.assertEqual(
                    input_data[i]["call_id"],
                    result[i].call_id,
                    f"Korrekt call-id",
                )
                self.assertEqual(
                    forventede_tekststykker[i],
                    result[i].tekststykke,
                    f"Korrekt teksttykke",
                )


class JNSamtaleExecutor(BaseTestExecutor):
    """
    Varetager indsætning og sletning af testdata samt at hente data fra komponentens tabel.
    """

    def __enter__(self):
        super().__enter__()
        self.delete_testdata()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.delete_testdata()
        super().__exit__(exc_type, exc_val, exc_tb)

    def delete_testdata(self):
        self.db_dfd_leverance_forretning.delete_from_table(
            data.leverance.business.jn.t_samtale
        )

        self.db_dfd_leverance_forretning.session.commit()

        self.drop_temp_tables()
        self.delete_output_tables(JNSamtaleBusinessComponent)

    def fetch_all_results(self):
        """
        Returnerer alle rækker fra komponentens tabel sorteret efter call_id og sekvens_nr.
        """
        return self.db_dfd_leverance_forretning.session.execute(
            select(data.leverance.business.jn.t_samtale).order_by(
                data.leverance.business.jn.t_samtale.c.call_id,
                data.leverance.business.jn.t_samtale.c.sekvens_nr,
            )
        ).all()

    def execute_component(self, komp):
        """
        Kører komponenten i batch-mode
        """
        komp.execute_all()
