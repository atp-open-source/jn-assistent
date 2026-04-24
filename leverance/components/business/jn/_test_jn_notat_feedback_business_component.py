import unittest
from datetime import datetime, timedelta

from spark_core.testing.base_test_executor import BaseTestExecutor
from sqlalchemy import select

from leverance import data

from .jn_notat_feedback_business_component import JNNotatFeedbackBusinessComponent


class TestJNNotatFeedbackBusinessComponent(unittest.TestCase):
    """
    Indeholder de forskellige tests for JNNotatFeedbackBusinessComponent.
    """

    data = {
        "call_id": "some_call_id",
        "agent_id": "some_agent_id",
        "feedback": "some_feedback",
        "rating": 5,
        "benyttet": 0,
    }

    def test_happy_day_scenario(self):
        """
        Komponenten eksekveres som en service, og det tjekkes at metoden "gem_feedback"
        skriver en række til tabellen, og at indholdet er som forventet.
        """

        with JNNotatFeedbackExecutor() as context:
            komp = JNNotatFeedbackBusinessComponent(
                request_uid="test_request_uid", config_name=None
            )
            return_val = komp.gem_feedback(
                self.data["call_id"],
                self.data["agent_id"],
                self.data["feedback"],
                self.data["rating"],
                self.data["benyttet"],
            )

            result = context.fetch_result()

            # Forventede antal rækker
            self.assertEqual(1, len(result), "Korrekt antal rækker")

            # Forventede værdier
            self.assertEqual(self.data["call_id"], result[0].call_id, "Korrekt call-id")
            self.assertEqual(self.data["agent_id"], result[0].agent_id, "Korrekt agent-id")
            self.assertEqual(self.data["feedback"], result[0].feedback, "Korrekt feedback")
            self.assertEqual(self.data["rating"], result[0].rating, "Korrekt feedback")
            self.assertEqual(self.data["benyttet"], result[0].benyttet, "Korrekt benyttet")

            # Forventet exit code
            self.assertEqual(0, return_val, "Korrekt exit code")

    def test_flere_ratinger(self):
        """
        Komponenten eksekveres som en service, og det tjekkes at metoden "gem_feedback"
        sletter den tidligere rating med den nye. Pånær hvis rating er -1, da denne rating
        gives ved gem af feedback eller ikke benyttet.
        """

        with JNNotatFeedbackExecutor() as context:
            komp = JNNotatFeedbackBusinessComponent(request_uid="test_request_uid")

            ratings = [-1, 3, 2]
            for element in ratings:
                call_id = "some_call_id"
                agent_id = "some_agent_id"
                feedback = ""
                rating = element
                benyttet = 1

                _ = komp.gem_feedback(call_id, agent_id, feedback, rating, benyttet)

            result = context.fetch_result()

            # Forventede antal rækker
            self.assertEqual(2, len(result), "Korrekt antal rækker")

            # Forventede ratings
            self.assertEqual(-1, result[0].rating, "Korrekt rating")
            self.assertEqual(2, result[1].rating, "Korrekt rating")

    def test_hent_feedback(self):
        """
        Tester, at metoden hent_feedback returnerer feedback for journalnotater inden
        for en given periode, som i komponenten er defineret som de sidste 2 måneder (history_depth).
        Der indsættes følgende:
            - Feedback fra i dag som forventes at blive hentet.
            - Feedback fra history_depth - 1 dage siden som forventes at blive hentet.
            - Feedback fra history_depth dage siden som ikke forventes at blive hentet.
        """
        now = datetime.now()

        with JNNotatFeedbackExecutor() as context:
            komp = JNNotatFeedbackBusinessComponent(request_uid="test_request_uid")

            # Indsæt testdata med forskellige datoer
            agent_ids = ["LULU", "LARS", "AAGE"]
            feedbacks = [
                "OMG bedste notat ever! Det er da lige til at blive glad af :-)",
                "Ej det er sgu en ommer - der mangler mange vigtige detaljer",
                "Der er ikke noget at komme efter!",
            ]
            ratings = [5, 3, 5]
            benyttet_values = [1, 0, 1]
            days_ago = [0, komp.history_depth - 1, komp.history_depth]

            test_data = [
                {
                    "call_id": f"call-id-{i+1}",
                    "agent_id": agent_ids[i],
                    "feedback": feedbacks[i],
                    "rating": ratings[i],
                    "benyttet": benyttet_values[i],
                    "load_time": now - timedelta(days=days_ago[i]),
                }
                for i in range(len(agent_ids))
            ]

            # Indsæt testdata
            context.insert_test_data(komp, test_data)

            # Hent feedback
            result = komp.hent_feedback()

            # Verificér resultater
            self.assertEqual(len(result), 2)
            self.assertTrue(any(r.call_id == "call-id-1" for r in result))
            self.assertTrue(any(r.call_id == "call-id-2" for r in result))


class JNNotatFeedbackExecutor(BaseTestExecutor):
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
        self.db_dfd_leverance_forretning.delete_from_table(
            data.leverance.business.jn.t_notat_feedback
        )

        self.db_dfd_leverance_forretning.session.commit()

        self.drop_temp_tables()
        self.delete_output_tables(JNNotatFeedbackBusinessComponent)

    def initialise_component(self):
        """
        Initialiserer komponenten.
        """
        component = JNNotatFeedbackBusinessComponent(request_uid="test_request_uid")

        return component

    def fetch_result(self):
        """
        Returnerer alle rækker sorteret efter call-id.
        """

        return self.db_dfd_leverance_forretning.session.execute(
            select(data.leverance.business.jn.t_notat_feedback).order_by(
                data.leverance.business.jn.t_notat_feedback.c.call_id
            )
        ).all()

    def insert_test_data(self, komp, test_data):
        """
        Indsætter testdata i tabellen.
        """
        for row in test_data:
            sql = f"""
                INSERT INTO {komp.db}.{komp.schema}.{komp.table}
                (call_id, agent_id, feedback, rating, benyttet, load_time)
                VALUES (
                    '{row["call_id"]}',
                    '{row["agent_id"]}',
                    '{row["feedback"]}',
                    {row["rating"]},
                    {row["benyttet"]},
                    '{row["load_time"].strftime("%Y-%m-%d %H:%M:%S")}'
                )
            """
            komp.execute_sql(sql)
            komp.session.commit()
