from uuid import UUID
from typing import Any
from datetime import date
from dateutil.relativedelta import relativedelta

from sqlalchemy import exc

from leverance.core.runners.service_runner import ServiceRunner
from leverance.core.logger_adapter import ServiceLoggerAdapter
from spark_core.components.core_types import OutputTable
from spark_core.components.base_component import NonSessionComponent


class JNNotatFeedbackBusinessComponent(NonSessionComponent, ServiceRunner):
    """
    Denne Leverancekomponent bruges til at gemme og hente kunderådgiveres feedback og
    feedback på journalnotater.

    Komponenten kan eksekveres som service, hvor den skriver til tabellen
    jn.notat_feedback. Tabellen indeholder én række per journalnotat.

    **Tabellen indeholder følgende kolonner:**

    * call_id      (nvarchar):        ID på opkald mellem borger og kunderådgiver.
    * agent_id     (nvarchar):        ID for kunderådgiveren.
    * feedback     (nvarchar):        Feedback fra kunderådgiveren på journalnotatet.
    * rating       (nvarchar):        Score fra 1-5, som kunderådgiveren har givet journalnotatet.
    * benyttet     (tinyint):         Binær variabel for hvorvidt notatet er benyttet eller ej.
    * load_time    (datetime2):       Tidspunktet for kørsel af komponenten.

    Komponenten indeholder følgende servicefunktioner:

    * gem_feedback: Gemmer kunderådgivers feedback og rating.
    * hent_feedback: Henter feedback for journalnotater fra de sidste 'history_depth' dage.

    """

    def __init__(self, request_uid: UUID = None, config_name=None):

        # Initialisér NonSessionComponent
        NonSessionComponent.__init__(self, app=None)

        # Initialisér ServiceRunner
        ServiceRunner.__init__(
            self, "jn", request_uid=request_uid, config_name=config_name
        )

        # Logger
        self.service_logger = ServiceLoggerAdapter(self.app.log)

        # Variable der angiver placering af output for batch komponenter, tabellen trunkeres ved kørsel
        self.db = self.app.config.LEVERANCE_BUSINESS_DATABASE_NAME()
        self.schema = "jn"
        self.table = "notat_feedback"

        self.output_tables = [
            OutputTable(db=self.db, schema=self.schema, table=self.table)
        ]

        # Antal dage tilbage i tid for hent_feedback (2 kalendermåneder)
        two_months_ago = date.today() - relativedelta(months=2)
        self.history_depth = (date.today() - two_months_ago).days

    def gem_feedback(
        self,
        call_id: str,
        agent_id: str,
        feedback: str,
        rating: int,
        benyttet: int,
    ) -> int:
        """
        Gemmer kunderådgivers feedback for det pågældende journalnotat i jn.notat_feedback.
        """

        # Fjern rating hvis allerede findes en i jn.notat_feedback
        delete_query = f"""
            DELETE FROM {self.db}.{self.schema}.{self.table}
            WHERE call_id = '{call_id}' 
            AND agent_id = '{agent_id}'
            AND rating <> -1
        """

        # Indsæt data i jn.notat_feedback
        insert_query = f"""
            INSERT INTO {self.db}.{self.schema}.{self.table}
            (call_id,
                agent_id,
                feedback,
                rating,
                benyttet,
                load_time
            )
            VALUES
            (
                '{call_id}',
                '{agent_id}',
                '{feedback}',
                {rating},
                {benyttet},
                GETDATE()
            )
        """
        try:
            if rating != -1:
                self.execute_sql(delete_query)
                self.session.commit()
            self.execute_sql(insert_query)
            self.session.commit()
            return 0
        except exc.SQLAlchemyError as e:
            self.service_logger.service_exception(
                self, f"Fejl ved indsættelse af data i SQL-tabellen: {e}"
            )
            return -1

    def hent_feedback(self) -> list[Any]:
        """
        Henter feedback fra jn.feedback fra de sidste 'self.history_depth' dage.
        """
        # SQL-streng
        sql = f"""
        SELECT
            call_id,
            MAX(agent_id)   AS agent_id,
            MAX(feedback)   AS feedback,
            MAX(rating)     AS rating,
            MIN(benyttet) AS benyttet,
            MAX(load_time)  AS load_time
        FROM {self.db}.{self.schema}.{self.table}
        WHERE load_time > DATEADD(DAY, -{self.history_depth}, GETDATE())
        GROUP BY call_id
        """

        # Kør SQL
        try:
            result = self.execute_sql(sql).fetchall()
            self.session.commit()
        except Exception as e:
            self.service_logger.service_exception(
                self,
                f"Fejl ved udtrækning af feedback i SQL-tabellen {self.db}.{self.schema}.{self.table}: {e}",
            )
            result = []

        return result
