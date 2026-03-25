from typing import Any
from uuid import UUID

from leverance.core.logger_adapter import ServiceLoggerAdapter
from leverance.core.runners.service_runner import ServiceRunner
from spark_core.components.base_component import NonSessionComponent

from sqlalchemy.exc import IntegrityError, SQLAlchemyError


class JNConfigBusinessComponent(NonSessionComponent, ServiceRunner):
    """
    Denne Leverancekomponent bruges til at hente en konfiguration for en bestemt
    kunderådgiver. Konfigurationen specificerer hvilket JN-miljø, kunderådgiveren skal
    bruge, samt hvilken version af audiostreameren, transcriberen og ChatGPT der skal
    bruges. Konfigurationen indeholder også forretningsområdet for kunderådgiveren, som
    kan bruges til at tilpasse prompten til ChatGPT.

    Komponenten skal kun eksekveres som service til hjemmesiden.


    **Konfigurationstabellen indeholder følgende kolonner:**

    * kr_initialer        (nvarchar):   Kunderådgivers initialer.
    * miljoe              (int):        Hvilket JN-miljø kunderådgiveren bruger, fx dev,
                                         pilo eller prod.
    * streamer_version    (nvarchar):   Hvilken version af audio-streameren der skal
                                         bruges (fx openai).
    * transcriber_version (nvarchar):   Hvilken version af transcriberen der skal bruges
                                         (bruges ikke lige nu, men skal bruges i fase 3).
    * chatgpt_version     (nvarchar):   Hvilken version af ChatGPT der skal bruges
                                         (bruges ikke lige nu, men skal bruges i fase 3).
    * controller_version  (nvarchar):   Hvilken controller der skal bruges (onprem eller azure).
    * forretningsomraade  (nvarchar):   Forretningsområdet for kunderådgiveren.
    * load_time           (datetime2):  Tidspunktet for kørsel af komponent.

    Komponenten indeholder følgende servicemetoder:

    * hent_kr_konfiguration:            Hent konfiguration for en kunderdågiver.
    * indsaet_kr_konfiguration:         Indsæt konfiguration for en kunderådgiver.
    * slet_kr_konfiguration:            Slet konfiguration for en kunderådgiver.
    """

    def __init__(self, request_uid: UUID = None, config_name=None):

        # Initialize NonSessionComponent
        NonSessionComponent.__init__(self, app=None)

        # Initialize ServiceRunner
        ServiceRunner.__init__(
            self, "jn", request_uid=request_uid, config_name=config_name
        )

        # Variable til konfigurationer
        self.temp_prefix = self.__class__.__name__
        self.placeholder_config = {
            "chatgpt_version": "o1",
            "forretningsomraade": "",
            "kr_initialer": "",
            "miljoe": "prod",
            "streamer_version": "openai",
            "transcriber_version": "azure",
            "controller_version": "onprem",
        }

        # Komponenten benytter følgende tabeller
        self.kr_config_table = "jn.config"

        # Logger
        self.service_logger = ServiceLoggerAdapter(self.app.log)

    def hent_kr_konfiguration(self, kr_initialer: str) -> dict[str, Any]:
        """
        Henter konfiguration for kunderådgiveren.
        """
        sql = f"""
            SELECT TOP(1)
                kr_initialer,
                miljoe,
                streamer_version,
                transcriber_version,
                chatgpt_version,
                controller_version,
                forretningsomraade
            FROM {self.kr_config_table}
            WHERE kr_initialer = '{kr_initialer}'
        """

        try:
            result = self.execute_sql(sql).fetchone()
            self.session.close()
            return dict(result._mapping) if result else self.placeholder_config
        except Exception as e:
            self.service_logger.service_exception(
                self,
                f"Fejl ved hentning af konfiguration for kunderådgiver {kr_initialer}: {str(e)}",
            )

    def indsaet_kr_konfiguration(
        self,
        chatgpt_version,
        controller_version,
        forretningsomraade,
        kr_initialer,
        miljoe,
        streamer_version,
        transcriber_version,
    ):
        """
        Metode til at indsætte en ny konfiguration for en kunderådgiver. Hvis
        der allerede findes en konfiguration for kunderådgiveren opdateres denne med de
        nye værdier.
        """
        # Hvis der findes en konfiguration på kunderådgiveren, så opdatér den
        upd_statement = f"""
                UPDATE {self.kr_config_table}
                SET
                    miljoe = '{miljoe}',
                    streamer_version = '{streamer_version}',
                    transcriber_version = '{transcriber_version}',
                    chatgpt_version = '{chatgpt_version}',
                    controller_version = '{controller_version}',
                    forretningsomraade = '{forretningsomraade}',
                    load_time = GETDATE()
                WHERE kr_initialer = '{kr_initialer}'
        """

        insert_statement = f"""
                INSERT INTO {self.kr_config_table}
                (
                    kr_initialer,
                    miljoe,
                    streamer_version,
                    transcriber_version,
                    chatgpt_version,
                    controller_version,
                    forretningsomraade,
                    load_time
                )
                VALUES
                (
                    '{kr_initialer}',
                    '{miljoe}',
                    '{streamer_version}',
                    '{transcriber_version}',
                    '{chatgpt_version}',
                    '{controller_version}',
                    '{forretningsomraade}',
                    GETDATE()
                )
        """

        sql = f"""
            IF EXISTS (SELECT 1 FROM {self.kr_config_table} WHERE kr_initialer = '{kr_initialer}')
            BEGIN
                {upd_statement}
            END
            ELSE
            BEGIN
                {insert_statement}
            END;
        """

        try:
            self.execute_sql(sql)
            self.session.commit()
            self.session.close()
            return "Konfigurationen blev indsat eller opdateret.", 200
        except IntegrityError as e:
            self.service_logger.service_exception(
                self,
                f"Fejl i indsættelse af konfiguration for kunderådgiver {kr_initialer}: {str(e)}",
            )
            return (
                "Forkert værdi forsøgt indsat",
                500,
            )

    def slet_kr_konfiguration(self, kr_initialer: str) -> str:
        """
        Metode til at slette en konfiguration for en kunderådgiver.
        """
        sql_begin = "BEGIN TRANSACTION"

        sql_delete = f"""
            DELETE FROM {self.kr_config_table}
            WHERE kr_initialer = '{kr_initialer}'
            """

        sql_commit = "COMMIT TRANSACTION"

        try:
            self.execute_sql(sql_begin)
            self.execute_sql(sql_delete)
            self.execute_sql(sql_commit)
            self.session.commit()
            self.session.close()
            return 0, f"Konfiguration for {kr_initialer} blev slettet."
        except SQLAlchemyError as e:
            self.service_logger.service_exception(
                f"Fejl ved sletning af konfiguration for kunderådgiver {kr_initialer}: {str(e)}"
            )
            return -1, f"Fejl ved sletning af konfiguration."
