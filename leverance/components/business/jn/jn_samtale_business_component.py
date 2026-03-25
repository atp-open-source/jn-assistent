from uuid import UUID
from spark_core.components.core_types import OutputTable
from spark_core.components.base_component import NonSessionComponent
from leverance.components.functions.speaker_mapping_function import speaker_mapping
from leverance.core.runners.service_runner import ServiceRunner
from leverance.core.logger_adapter import ServiceLoggerAdapter
import datetime as dt
from dateutil.relativedelta import relativedelta


class JNSamtaleBusinessComponent(NonSessionComponent, ServiceRunner):
    """
    Denne komponent bruges til at gemme transskriberede samtaler.

    Komponenten kan eksekveres som service til hjemmesiden, hvor den skriver til
    jn.samtale.
    Tabellen indeholder én række for hver transkriberet tekststykke i en samtale mellem en kunderådgiver og en borger.

    Komponenten kan også eksekveres i batchmode, hvor den sanerer samtaler som er ældre end 3 måneder

    **Tabellen indeholder følgende kolonner:**

    * call_id      (nvarchar):      ID på opkald fra borger.
    * queue        (nvarchar):      Telefonkøen for opkaldet.
    * kr_initialer (nvarchar):      Initialer på kunderådgiveren der tog opkaldet.
    * tekststykke  (nvarchar):      Et stykke af samtallen i transskriberet format mellem kunderådgiver og borger.
    * rolle        (nvarchar):      Angiver om samtalestykke er fra kunderådgiver eller borger.
    * sekvens_nr   (int):           Angiver rækkefølge af den transskriberet tekst i samtalen.
    * load_time    (datetime2):     Tidspunktet for hvornår data er indsat.

    Komponenten indeholder følgende servicemetoder:

    * gem_samtale:             Gem transskriberet samtale.
    """

    def __init__(self, request_uid: UUID = None, config_name=None):

        NonSessionComponent.__init__(self, app=None)

        ServiceRunner.__init__(
            self, "jn", request_uid=request_uid, config_name=config_name
        )

        self.service_logger = ServiceLoggerAdapter(self.app.log)

        # Variable der angiver placering af output for batch komponenter, tabellen trunkeres ikke ved kørsel
        self.db = self.app.config.LEVERANCE_BUSINESS_DATABASE_NAME()
        self.schema = "jn"
        self.table = "samtale"

        # Komponenten benytter følgende tabeller

        self.output_tables = [
            OutputTable(self.db, self.schema, self.table, do_not_delete=True),
        ]

        # Variable der bruges specifikt til batch kørsel
        # Journalnotater saneres hver anden måned
        self.saneringsdato = dt.date.today() - relativedelta(months=2)

        # Denne komponent skal ikke give en advarsel ved 0 indsatte rækker
        self.ignore_zero_row_warning = True

        # Maksimal længde af tekststykke i tabellen
        self.max_len = 4000

    def gem_samtale(
        self,
        call_id: str | None,
        cpr: str | None,
        queue: str | None,
        kr_initialer: str | None,
        samtale: list[dict[str, str]],
    ) -> int:
        """
        Gemmer den preprocesserede samtale i tabellen jn.samtale. Der gemmes en række per samtalestykke for det specifikke opkald.
        """
        try:
            if not samtale:
                self._log_warning(
                    f"Samtale fra opkald med call-id '{call_id}' er tom og gemmes derfor ikke",
                )
                return 400

            params = {
                "call_id": call_id,
                "cpr": cpr,
                "queue": queue,
                "kr_initialer": kr_initialer,
            }

            # Logger en warning for de resterende parametre hvis der mangler værdier i parametrene
            self._log_missing_parameters_before_saving(params, call_id)

            # Kombiner eksistenscheck og indsættelse i ét for at reducere round-trips
            now = dt.datetime.now()
            rows = []
            seq = 1

            for entry in samtale:
                tekst = entry["sentence"]
                rolle = speaker_mapping(entry["speaker"])

                # Split tekst i chunk-størrelser
                for chunk_start in range(0, len(tekst), self.max_len):
                    chunk = tekst[chunk_start : chunk_start + self.max_len]
                    rows.append(
                        {
                            "call_id": call_id,
                            "queue": queue,
                            "kr_initialer": kr_initialer,
                            "tekst": chunk,
                            "rolle": rolle,
                            "sekvens_nr": seq,
                            "load_time": now,
                        }
                    )
                    seq += 1

            if rows:
                values_clause = ", ".join(
                    f"(:call_id{i}, :queue{i}, :kr_initialer{i}, :tekst{i}, :rolle{i}, :sekvens_nr{i}, :load_time{i})"
                    for i in range(len(rows))
                )
                insert_query = f"""
                    INSERT INTO {self.db}.{self.schema}.{self.table}
                    (call_id, queue, kr_initialer, tekststykke, rolle, sekvens_nr, load_time)
                    VALUES {values_clause}
                """

                params = {}
                for idx, row in enumerate(rows):
                    for key, val in row.items():
                        params[f"{key}{idx}"] = val

                self.execute_sql(insert_query, params=params)

            self.session.commit()

        except Exception as e:
            self.session.rollback()
            self._log_warning(
                f"Fejl ved gemning af samtale med call-id '{call_id}': {e}"
            )
            return 500

        return 200

    def _log_missing_parameters_before_saving(
        self, params: dict[str, any], call_id: str | None
    ) -> None:
        """
        Logger advarsler for manglende parametre når en samtale gemmes
        """
        for key, value in params.items():
            if not value:
                if call_id:
                    message = (
                        f"Manglende værdi for {key} i samtale med call-id {call_id}!"
                    )
                else:
                    message = f"Manglende værdi for {key}!"
                self._log_warning(message)

    def _log_warning(self, message: str) -> None:
        """Hjælpemetode til at logge advarsler med kontekst hvis muligt."""
        self.service_logger.service_warning(self, message)

    def _sanering(
        self,
    ) -> None:
        "Metode til at sanere samtaler i komponentens tabel når de er ældre end 2 måneder."

        sql = f"""
            UPDATE {self.db}.{self.schema}.{self.table}
            SET tekststykke = NULL
            WHERE load_time < '{self.saneringsdato}';
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
