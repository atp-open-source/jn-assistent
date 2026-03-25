import datetime as dt
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from dateutil.relativedelta import relativedelta

from leverance.core.common.timeout_handler import run_with_timeout
from leverance.core.runners.service_runner import ServiceRunner
from leverance.core.logger_adapter import ServiceLoggerAdapter
from spark_core.components.core_types import OutputTable
from spark_core.components.base_component import NonSessionComponent

from leverance.components.business.jn.jn_storage_account_business_component import (
    JNStorageAccountBusinessComponent,
)


class JNNotatBusinessComponent(NonSessionComponent, ServiceRunner):
    """
    Denne Leverancekomponent bruges til at gemme og hente journalnotater.

    Komponenten kan eksekveres som service til hjemmesiden, hvor den skriver til
    jn.notat. Tabellen indeholder én række per journalnotat.

    Komponenten kan også eksekveres i batchmode, hvor den sanerer journalnotater som er ældre end 2 måneder.


    **Tabellen indeholder følgende kolonner:**

    * call_id                (nvarchar):   ID på opkald fra borger.
    * genererings_prompt_id  (int):        ID for prompt der er brugt til at generere notat.
    * validerings_prompt_id  (int):        ID for prompt der er brugt til at validere notat.
    * queue                  (nvarchar):   Telefonkøen for opkaldet.
    * kr_initialer           (nvarchar):   Initialer på kunderådgiveren der tog opkaldet.
    * forretningsomraade     (nvarchar):   Forretningsområde for kunderådgiveren der tog opkaldet.
    * notat                  (nvarchar):   Journalnotatet lavet af ChatGPT.
    * load_time              (datetime2):  Tidspunktet for kørsel af komponent.

    Komponenten indeholder følgende servicemetoder:

    * gem_notat:               Gem journalnotat.
    * hent_opkald_status:      Hent status for seneste opkald fra Azure Queue.
    * hent_notat:              Hent journalnotat for kunderådgiver.
    * hent_alle_notater:       Hent alle journalnotater inden for en given periode.
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

        # Variable der angiver placering af output for batch komponenter, tabellen trunkeres ikke ved kørsel
        self.db = self.app.config.LEVERANCE_BUSINESS_DATABASE_NAME()
        self.schema = "jn"
        self.table = "notat"

        # Variable til konfigurationer
        self.temp_prefix = self.__class__.__name__

        # Output tables
        self.output_tables = [
            OutputTable(self.db, self.schema, self.table, do_not_delete=True),
        ]

        # Initialisér Azure Queue Client max message size (max 32)
        self.max_msg = 32

        # Variable
        self.sekund_threshold = 3600
        self.opkald_afsluttet_status = "end-call"
        self.opkald_ingen_status = "no-status"
        self.opkald_ingen_status_key = "no-status-key"
        self.opkald_status_duration_exceeded = "call-state-duration-exceeded"
        two_months_ago = dt.date.today() - relativedelta(months=2)
        self.history_depth = (dt.date.today() - two_months_ago).days

        # Initialisér Azure Storage Account Business Component
        self.jn_storage_account = JNStorageAccountBusinessComponent(self.request_uid)

        # Variable der bruges specifikt til batch kørsel
        # Journalnotater saneres hver anden måned
        self.saneringsdato = dt.date.today() - relativedelta(months=2)

        # Denne komponent skal ikke give en advarsel ved 0 indsatte rækker
        self.ignore_zero_row_warning = True

    def gem_notat(
        self,
        call_id: str | None,
        cpr: str | None,
        genererings_prompt_id: int | None,
        validerings_prompt_id: int | None,
        queue: str | None,
        kr_initialer: str | None,
        forretningsomraade: str | None,
        notat: str,
    ) -> int:
        """
        Gemmer notat i tabellen jn.notat.
        """
        # Giv en advarsel hvis notat mangler
        if notat == "":
            self.service_logger.service_warning(
                self,
                f"Notat fra opkald med call-id {call_id} for kunderådgiver {kr_initialer} er tomt!",
            )

        # Giv en advarsel hvis anden værdi mangler
        for val, col in zip(
            [
                call_id,
                cpr,
                genererings_prompt_id,
                validerings_prompt_id,
                queue,
                kr_initialer,
                forretningsomraade,
            ],
            [
                "call_id",
                "cpr",
                "genererings_prompt_id",
                "validerings_prompt_id",
                "queue",
                "kr_initialer",
                "forretningsomraade",
            ],
        ):
            if not val:
                if call_id:
                    self.service_logger.service_warning(
                        self,
                        f"Manglende værdi for {col} i notat med call-id {call_id}!",
                    )
                else:
                    self.service_logger.service_warning(
                        self,
                        f"Manglende værdi for {col}!",
                    )

        # Indsæt data i jn.notat
        self._sql_insert_into(
            call_id,
            genererings_prompt_id,
            validerings_prompt_id,
            queue,
            kr_initialer,
            forretningsomraade,
            notat,
        )

        return 200

    def _sql_insert_into(
        self,
        call_id: str | None,
        genererings_prompt_id: int | None,
        validerings_prompt_id: int | None,
        queue: str | None,
        kr_initialer: str | None,
        forretningsomraade: str | None,
        notat: str,
    ) -> None:
        """
        SQL-streng der indsætter i komponentens tabel.
        """

        # Håndtér manglende værdier
        call_id = f"'{call_id}'" if call_id else "NULL"
        genererings_prompt_id = (
            genererings_prompt_id if genererings_prompt_id else "NULL"
        )
        validerings_prompt_id = (
            validerings_prompt_id if validerings_prompt_id else "NULL"
        )
        queue = f"'{queue}'" if queue else "NULL"
        kr_initialer = f"'{kr_initialer}'" if kr_initialer else "NULL"
        forretningsomraade = f"'{forretningsomraade}'" if forretningsomraade else "NULL"
        notat = f"'{notat}'" if notat else "NULL"

        # Brug en enkelt statement til at tjekke eksistens og indsætte hvis ikke findes
        insert_query = f"""
            INSERT INTO {self.db}.{self.schema}.{self.table}
            (call_id, genererings_prompt_id, validerings_prompt_id, queue, kr_initialer, forretningsomraade, notat, load_time)
            SELECT {call_id}, {genererings_prompt_id}, {validerings_prompt_id}, {queue}, {kr_initialer}, {forretningsomraade}, {notat}, '{dt.datetime.now()}'
        """
        try:
            self.execute_sql(insert_query)
            self.session.commit()
        except Exception as e:
            self.service_logger.service_exception(
                self,
                f"Fejl ved indsættelse af række i SQL-tabellen {self.db}.{self.schema}.{self.table} for call-id {call_id}: {e}",
            )

    def _hent_messages_azure(self, kr_initialer: str) -> list | None:
        """
        Henter beskeder fra en Azure Queue for en specifik kunderådgiver.

        Argumenter:
            kr_initialer (str): Initialer for kunderådgiveren.

        Returnerer:
            list | None: En liste af beskeder sorteret efter tidspunkt eller None, hvis ingen beskeder findes.
        """

        # Definér navn på Azure Queue
        queue_name = f"status-{kr_initialer}"

        # Opret Azure Queue klient med storage account name og storage account key
        queue_client = self.jn_storage_account.create_queue_client(queue_name)

        messages = None

        msg_page = queue_client.peek_messages(max_messages=self.max_msg)
        # hvis der stadig er flere beskeder i køen, slet alle beskeder undtagen den sidste
        if len(msg_page) > 1:
            oldest_msg = queue_client.receive_messages(max_messages=len(msg_page) - 1)
            for msg in oldest_msg:
                queue_client.delete_message(msg)
            # Tag den sidste besked i msg_page
            msg = msg_page[-1]
        elif len(msg_page) == 1:
            # Hvis der kun er én besked i køen, brug den direkte
            msg = msg_page[0]
        else:
            self.service_logger.service_warning(
                self,
                f"Kunne ikke finde nogen beskeder for {kr_initialer}",
            )
            return messages

        try:
            msg_value = json.loads(msg.content)
            messages = [
                (
                    datetime.fromtimestamp(msg.inserted_on.timestamp()),
                    msg_value,
                )
            ]
        except json.decoder.JSONDecodeError as e:
            self.service_logger.service_warning(
                self,
                f"Kunne ikke afkode beskeden for {kr_initialer} {msg.content}. Fik fejlen: {e}",
            )

        return messages

    def hent_opkald_status(self, kr_initialer: str) -> str:
        """
        Henter beskeder fra kunderådgivers status-kø og returnerer status for den nyeste
        besked.

        Argumenter:
            kr_initialer (str): Initialer for kunderådgiveren.

        Returnerer:
            str: Status for den nyeste besked. Hvis der ikke er nogen beskeder, returneres
                 "no-status" hvis der ikke findes nogen statusbesked,
                 "no-status-key" hvis 'status' key mangler i beskeden eller
                "call-state-duration-exceeded" hvis status har været uændret i over en time.

        """

        # Hent beskeder fra Azure Queue
        messages = self._hent_messages_azure(kr_initialer=kr_initialer)

        if messages is None:
            fejl_info_str = f"Kan ikke finde status i køen med initialerne {kr_initialer} i Azure Queue."
            status = self.opkald_ingen_status
            self.service_logger.service_warning(
                self,
                fejl_info_str,
            )
            return status

        if messages:
            try:
                opkald_status = messages[-1][1]["status"]
            except KeyError:
                status = self.opkald_ingen_status_key
                self.service_logger.service_warning(
                    self,
                    f"Kunne ikke finde key 'status' i seneste besked fra køen for kunderådgiver med initialerne {kr_initialer}.",
                )
                return status

            # Hvis seneste besked ikke er self.opkald_afsluttet_status og er oprettet for self.sekund_threshold eller flere sekunder siden
            if (
                opkald_status != self.opkald_afsluttet_status
                and (datetime.now() - messages[-1][0]).total_seconds()
                >= self.sekund_threshold
            ):
                fejl_info_str = f"Fejl - status for seneste opkald hos KR {kr_initialer} har været '{opkald_status}' i mere end {self.sekund_threshold / (60*60)} time(r)."
                status = self.opkald_status_duration_exceeded

                # Log og returnér fejl-info
                self.service_logger.service_warning(self, fejl_info_str)
                return status
            else:
                # Returnér status for seneste besked
                return messages[-1][1]["status"]
        else:
            status = self.opkald_ingen_status
            return status

    @run_with_timeout(
        timeout=20,
        result_by_timeout=(
            "Fejl: Det tog for lang tid at hente journalnotatet.",
            None,
            504,
        ),
        log_besked="Timeout ved hentning af notat fra jn.notat.",
        log_type="error",
    )
    def hent_notat(
        self, kr_initialer: str, call_id: str | None
    ) -> tuple[str, str | None, int]:
        """
        Henter seneste journalnotat for kunderådgiveren. Hvis call-id er givet, hentes
        notatet tilknyttet dette frem for det nyeste.

        Statuskoder:
            200: Notat fundet.
            204: Intet notat fundet.
            500: Fejl ved hentning af notat.
            504: Timeout ved hentning af notat (styres af decoratoren).

        Argumenter:
            kr_initialer (str): Initialer for kunderådgiveren
            call_id (str | None): ID for opkaldet

        Returnerer:
            tuple[str, str | None, int]: Notatet el. fejlbesked, call-id og statuskode.
        """

        # Hent seneste notat for kunderådgiver
        sql = f"""
            SELECT TOP 1
                notat,
                call_id
            FROM {self.db}.{self.schema}.{self.table}
            WHERE kr_initialer = '{kr_initialer}'
        """
        # Hvis call-id er specificeret, tilføj dette i SQL-strengen
        if call_id:
            sql += f" AND call_id = '{call_id}'"

        sql += " ORDER BY load_time DESC"

        # Kør SQL
        try:
            result = self.execute_sql(sql).fetchone()
        except Exception as e:
            self.service_logger.service_exception(
                self,
                f"Fejl ved udtrækning af seneste notat for kunderådgiveren {kr_initialer} i SQL-tabellen {self.db}.{self.schema}.{self.table}: {e}",
            )
            return (
                "Fejl: Der opstod en fejl ved hentning af journalnotat.",
                call_id,
                500,
            )

        # Returnér notat og call-id hvis det findes, ellers returnér en fejlbesked
        if result:
            return result[0], result[1], 200

        else:
            intet_notat_fundet = (
                f"Intet notat fundet for kunderådgiverinitialer {kr_initialer}"
            )
            if call_id:
                intet_notat_fundet += f" og call-id {call_id}."
            else:
                intet_notat_fundet += "."

            return intet_notat_fundet, call_id, 204

    def hent_alle_notater(self, dagens_historik, ordning_list=None) -> list[Any]:
        """
        Henter notater fra jn.notat fra de sidste 'self.history_depth' dage.
        Hvis dagens_historik er True, hentes kun notater fra i dag.
        """
        if dagens_historik:
            dato_filter = "CONVERT(date, notat.load_time) = CONVERT(date, GETDATE())"
        else:
            dato_filter = (
                f"notat.load_time > DATEADD(DAY, -{self.history_depth}, GETDATE())"
            )

        if "alle_ordninger" in ordning_list:
            ordning_filter = "AND 1=1"
        else:
            ordning_filter = f"""AND forretningsomraade IN ({', '.join(f"'{ordning}'" for ordning in ordning_list)})"""

        sql = f"""
            SELECT
                call_id,
                queue,
                kr_initialer,
                notat,
                load_time,
                forretningsomraade AS ordning
            FROM {self.db}.{self.schema}.{self.table}
            WHERE {dato_filter}
                {ordning_filter}
        """

        # Kør SQL
        try:
            result = self.execute_sql(sql).fetchall()
            self.session.commit()
        except Exception as e:
            self.service_logger.service_exception(
                self,
                f"Fejl ved udtrækning af alle notater i SQL-tabellen {self.db}.{self.schema}.{self.table}: {e}",
            )
            result = []

        return result

    def _sanering(
        self,
    ) -> None:
        """
        Metode til at sanere notater i komponentens tabel når de er ældre end 2 måneder.
        """
        update_conditions = f"load_time < '{self.saneringsdato}'"
        kolonne = "notat"

        # SQL-streng
        sql = f"""
            UPDATE {self.db}.{self.schema}.{self.table}
            SET {kolonne} = NULL
            WHERE {update_conditions};
        """

        return sql

    def create_sql(self, mode="batch"):
        """
        Sammensætter og returnerer SQL'en der bruges i komponenten. "mode" angiver, hvorvidt
        det er batch versionen eller servicemode versionen, som skal genereres.
        Hvis forkert 'mode' angives, smides der en fejl. Denne komponent har ikke nogen servicemode da det ikke er
        meningen at den skal kaldes af en anden service.
        """
        if mode == "batch":
            sql = [
                self._sanering(),
            ]

        elif mode == "service":
            sql = f"{self.__class__.__name__} har ikke nogen servicemode"

        return sql

    def execute_all(self):
        """
        Eksekverer alle SQL statements i den givne rækkefølge som angivet i create_sql
        """
        for statement in self.create_sql():
            if isinstance(statement, str):
                self.execute_sql(statement)
                self.session.commit()
            else:
                statement(self)
