import unittest

from leverance import data
from spark_core.testing.base_test_executor import BaseTestExecutor

from .jn_config_business_component import JNConfigBusinessComponent


class TestJNConfigBusinessComponent(unittest.TestCase):
    """
    Indeholder de forskellige tests for JNConfigBusinessComponent
    """

    # Variabler til test
    konfigurationer = [
        # Test-konfiguration
        {
            "kr_initialer": "test",
            "miljoe": "dev",
            "streamer_version": "openai",
            "transcriber_version": "azure",
            "chatgpt_version": "azure",
            "controller_version": "onprem",
            "forretningsomraade": "pension",
        },
        # Opdateret konfiguration
        {
            "kr_initialer": "test",
            "miljoe": "dev",
            "streamer_version": "ny_version",
            "transcriber_version": "azure",
            "chatgpt_version": "azure",
            "controller_version": "azure",
            "forretningsomraade": "fy",
        },
    ]

    test_uuid = "TEST-UUID"

    def test_happy_day_scenario(self):
        """
        Komponenten eksekveres som en service, og det tjekkes at metoden
        "hent_kr_konfiguration" korrekt udhenter en konfiguration på en kunderådgiver.
        Først udhentes en konfiguration for en kunderådgiver i tabellen, og det tjekkes,
        at det er de korrekte værdier, der er udhentet. Herefter forsøges det at udhente
        en konfiguration på en ikke-eksisterende kunderådgiver, og det tjekkes, at der
        returneres en bestemt placeholder-dictionary.
        """

        with JNConfigExecutor() as context:

            # Indsæt testdata
            context.insert_testdata(self.konfigurationer[0])

            # Initialiser komponenten og hent konfiguration
            komp = JNConfigBusinessComponent(
                request_uid=self.test_uuid, config_name=None
            )
            result = komp.hent_kr_konfiguration(self.konfigurationer[0]["kr_initialer"])
            non_result = komp.hent_kr_konfiguration("ABCD")

            # Forventet antal rækker
            self.assertEqual(
                len(self.konfigurationer[0].keys()),
                len(result.keys()),
                "Korrekt antal rækker",
            )
            self.assertEqual(
                komp.placeholder_config, non_result, "Korrekt placeholderværdi"
            )

            # Forventet konfiguration
            for key in self.konfigurationer[0].keys():
                self.assertEqual(
                    self.konfigurationer[0][key],
                    result[key],
                    f"Korrekt værdi for kolonne {key}",
                )

    def test_indsaet_kr_konfiguration(self):
        """
        Tester at metoden indsaet_kr_konfiguration indsætter korrekt data i databasen.
        Først indsættes en konfiguration på en kunderådgiver.
        Herefter indsættes en ny konfiguration for den første kunderådgiver, og det
        tjekkes at denne bliver opdateret.
        """

        with JNConfigExecutor() as context:
            komp = JNConfigBusinessComponent(request_uid=self.test_uuid)
            expected_results = [200, 200]
            check_inserted_data = [True, True]

            # Indsæt konfigurationer
            for i, konfiguration in enumerate(self.konfigurationer):
                _, status = komp.indsaet_kr_konfiguration(
                    kr_initialer=konfiguration["kr_initialer"],
                    miljoe=konfiguration["miljoe"],
                    streamer_version=konfiguration["streamer_version"],
                    transcriber_version=konfiguration["transcriber_version"],
                    chatgpt_version=konfiguration["chatgpt_version"],
                    controller_version=konfiguration["controller_version"],
                    forretningsomraade=konfiguration["forretningsomraade"],
                )
                self.assertEqual(
                    expected_results[i], status, "Korrekt status for indsættelse"
                )

                # Tjek om data blev korrekt indsat
                if check_inserted_data[i]:
                    result = komp.hent_kr_konfiguration(
                        self.konfigurationer[i]["kr_initialer"]
                    )
                    self.assertEqual(
                        konfiguration, result, "Korrekt indsat konfiguration"
                    )

    def test_slet_kr_konfiguration(self):
        """
        Tester at metoden slet_kr_konfiguration sletter data korrekt.
        Først indsættes en konfiguration, derefter tjekkes det at konfigurationen eksisterer.
        Herefter slettes konfigurationen, og det tjekkes at konfigurationen er slettet og
        at den korrekte returværdi returneres.
        Til sidst testes sletning af en ikke-eksisterende konfiguration.
        """
        with JNConfigExecutor() as context:
            komp = JNConfigBusinessComponent(request_uid=self.test_uuid)

            # Indsæt konfiguration
            test_config = self.konfigurationer[0]
            komp.indsaet_kr_konfiguration(
                kr_initialer=test_config["kr_initialer"],
                miljoe=test_config["miljoe"],
                streamer_version=test_config["streamer_version"],
                transcriber_version=test_config["transcriber_version"],
                chatgpt_version=test_config["chatgpt_version"],
                controller_version=test_config["controller_version"],
                forretningsomraade=test_config["forretningsomraade"],
            )

            # Bekræft at konfigurationen findes
            result = komp.hent_kr_konfiguration(test_config["kr_initialer"])
            self.assertEqual(test_config, result, "Konfiguration blev indsat korrekt")

            # Slet konfiguration og tjek returværdi
            status_code, message = komp.slet_kr_konfiguration(
                test_config["kr_initialer"]
            )
            self.assertEqual(0, status_code, "Korrekt statuskode")
            self.assertIn(
                f"Konfiguration for {test_config['kr_initialer']} blev slettet",
                message,
                "Korrekt besked for sletning",
            )

            # Bekræft at konfigurationen er slettet
            result_after_delete = komp.hent_kr_konfiguration(
                test_config["kr_initialer"]
            )
            self.assertEqual(
                komp.placeholder_config,
                result_after_delete,
                "Konfiguration blev slettet korrekt",
            )

            # Test sletning af ikke-eksisterende konfiguration
            status_code, message = komp.slet_kr_konfiguration("ikke_eksisterende")
            self.assertEqual(
                0,
                status_code,
                "Korrekt statuskode for sletning af ikke-eksisterende konfiguration",
            )


class JNConfigExecutor(BaseTestExecutor):
    """
    Varetager indsætning og sletning af testdata, samt eksekvering af komponenten
    """

    def __init__(self):
        super().__init__()

    def __enter__(self):
        super().__enter__()
        self.delete_testdata()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.delete_testdata()
        super().__exit__(exc_type, exc_val, exc_tb)

    def delete_testdata(self):
        self.db_dfd_spark_kilde.delete_from_table(
            data.kilder.dfd_spark_kilde.map.Borger
        )
        self.db_dfd_leverance_forretning.delete_from_table(
            data.leverance.business.jn.Config
        )

        self.db_dfd_leverance_forretning.session.commit()
        self.db_dfd_spark_kilde.session.commit()
        self.db_dfd_spark_bestand.session.commit()

        self.drop_temp_tables()
        self.delete_output_tables(JNConfigBusinessComponent)

    def insert_testdata(
        self,
        expected_items: dict[str, str],
    ):
        self.db_dfd_leverance_forretning.insert_into_table(
            data.leverance.business.jn.Config,
            kr_initialer=expected_items["kr_initialer"],
            miljoe=expected_items["miljoe"],
            streamer_version=expected_items["streamer_version"],
            transcriber_version=expected_items["transcriber_version"],
            chatgpt_version=expected_items["chatgpt_version"],
            controller_version=expected_items["controller_version"],
            forretningsomraade=expected_items["forretningsomraade"],
        )

        self.db_dfd_leverance_forretning.session.commit()
