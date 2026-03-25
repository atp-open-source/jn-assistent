import datetime as dt
from uuid import UUID

from leverance.core.runners.service_runner import ServiceRunner
from leverance.core.logger_adapter import ServiceLoggerAdapter
from spark_core.components.core_types import OutputTable
from spark_core.components.base_component import NonSessionComponent


class JNPromptsBusinessComponent(NonSessionComponent, ServiceRunner):
    """
    Denne Leverancekomponent bruges til at hente og gemme prompts, der bruges i JN.

    Komponenten kan eksekveres som service, hvor den skriver til
    jn.prompts. Tabellen indeholder én række per prompt.

    **Tabellen indeholder følgende kolonner:**

    * prompt_id      (int, primary key): Unikt ID for prompten.
    * model          (nvarchar):         Navn på den model der bruges.
    * prompt         (nvarchar):         Hele prompten.
    * ordning        (nvarchar):         Det forretningsområde/ordning, som prompten tilhører.
    * er_evaluering  (tinyint):          Indikerer om prompten er en evalueringsprompt eller ej.
    * api_version    (nvarchar):         API-version af model.
    * sekvens_nr     (nvarchar):         Sekventiel angivning af hvornår prompten skal bruges i flowet.
    * load_time      (datetime2):        Tidspunkt for indlæsning af rækken.

    Komponenten indeholder følgende servicemetoder:

    * hent_notat_prompts:       Hent prompts til generering og validering af journalnotat.
    * hent_eval_prompts:        Hent prompts til evaluering af journalnotat og transskriberet samtale.
    * gem_prompt:               Indsætter ny prompt i jn.prompts tabel.

    """

    def __init__(self, request_uid: UUID = None, config_name=None):

        # Initialisér NonSessionComponent
        NonSessionComponent.__init__(self, app=None)

        # Initialisér ServiceRunner
        ServiceRunner.__init__(
            self, "jn", request_uid=request_uid, config_name=config_name
        )

        # Opsæt logger
        self.service_logger = ServiceLoggerAdapter(self.app.log)

        # Variable der angiver placering af output for batchkomponenter, tabellen trunkeres ikke ved kørsel
        self.db = self.app.config.LEVERANCE_BUSINESS_DATABASE_NAME()
        self.schema = "jn"
        self.table = "prompts"

        # Variable til konfigurationer
        self.temp_prefix = self.__class__.__name__

        # Output tables
        self.output_tables = [
            OutputTable(self.db, self.schema, self.table, do_not_delete=True),
        ]

    def hent_notat_prompts(
        self, forretningsomraade: str = "standard"
    ) -> tuple[str, str, int | None, str, str, int | None]:
        """
        Henter prompts og modelversion til generering og validering af journalnotat for det angivne forretningsområde.

        Argumenter:
            forretningsomraade (str): forretningsområde som prompten tilhører. Default er 'standard'.

        Returnerer:
            tuple: (
                notat_prompt,
                notat_model,
                notat_prompt_id,
                notat_val_prompt,
                notat_val_model,
                notat_val_prompt_id
            )
        """

        # Hent prompts for angivet forretningsområde
        sql = f"""
            WITH ranked AS (
                SELECT
                    prompt_id,
                    model,
                    prompt,
                    ordning,
                    er_evaluering,
                    api_version,
                    sekvens_nr,
                    load_time,
                    ROW_NUMBER() OVER (
                        PARTITION BY sekvens_nr, ordning
                        ORDER BY load_time DESC
                    ) AS rn,
                    CASE 
                        WHEN LOWER(ordning) = '{forretningsomraade.lower()}' THEN 1
                        WHEN LOWER(ordning) = 'standard' THEN 2
                        ELSE 3
                    END AS priority
                FROM {self.db}.{self.schema}.{self.table}
                WHERE
                    sekvens_nr IN (1, 2)
                    AND LOWER(ordning) IN ('{forretningsomraade.lower()}', 'standard')
            )
            SELECT TOP (2)
                prompt_id,
                model,
                prompt,
                ordning,
                er_evaluering,
                api_version,
                sekvens_nr  
            FROM ranked
            WHERE rn = 1
            ORDER BY priority ASC;
            """

        # Kør SQL
        try:
            results = self.execute_sql(sql).fetchall()
        except Exception as e:
            self.service_logger.service_exception(
                self,
                f"Fejl ved udtrækning af prompts for ordning '{forretningsomraade}' i SQL-tabellen {self.db}.{self.schema}.{self.table}: {e}",
            )
            return "", "gpt-4o", None, "", "gpt-4o", None

        # Returnér prompts hvis de findes, ellers returnér tomme strenge
        if not results:
            self.service_logger.service_warning(
                self,
                f"Der blev ikke fundet prompts for ordning '{forretningsomraade}' eller standard i SQL-tabellen {self.db}.{self.schema}.{self.table}",
            )
            return "", "gpt-4o", None, "", "gpt-4o", None

        # Udtræk genererings- og valideringsprompt (genereringsprompt har sekvens_nr 1 og valideringsprompt har sekvens_nr 2)
        notat_prompt = ""
        notat_val_prompt = ""
        notat_model = ""
        notat_val_model = ""
        notat_prompt_id = None
        notat_val_prompt_id = None
        sekvens_found = set()
        for row in results:
            if row.sekvens_nr == "1" and "1" not in sekvens_found:
                notat_prompt = row.prompt
                notat_model = row.model
                notat_prompt_id = row.prompt_id
                sekvens_found.add("1")
            elif row.sekvens_nr == "2" and "2" not in sekvens_found:
                notat_val_prompt = row.prompt
                notat_val_model = row.model
                notat_val_prompt_id = row.prompt_id
                sekvens_found.add("2")

        # Giv en advarsel hvis en prompt mangler
        if not notat_prompt:
            self.service_logger.service_warning(
                self,
                f"Ingen notat_prompt med sekvens_nr=1 (prompt til generering af notat) fundet for ordning {forretningsomraade}",
            )
        if not notat_val_prompt:
            self.service_logger.service_warning(
                self,
                f"Ingen notat_val_prompt med sekvens_nr=2 (prompt til validering af notat) fundet for ordning {forretningsomraade}",
            )

        return (
            notat_prompt,
            notat_model,
            notat_prompt_id,
            notat_val_prompt,
            notat_val_model,
            notat_val_prompt_id,
        )

    def hent_eval_prompts(self) -> tuple[str, str, str, str, str, str, str, str]:
        """
        Henter prompts og modelversioner til evaluering af journalnotat og transskriberet samtale.

        Returnerer:
            tuple: (
                retningslinjer_notat_prompt,
                retningslinjer_notat_val_prompt,
                hallucination_prompt,
                samtale_kvalitet_prompt,
                retningslinjer_notat_model,
                retningslinjer_notat_val_model,
                hallucination_model,
                samtale_kvalitet_model
            )
        """
        # Hent evalueringsprompts
        sql = f"""
            WITH ranked AS (
                SELECT
                    model,
                    prompt,
                    ordning,
                    er_evaluering,
                    api_version,
                    sekvens_nr,
                    ROW_NUMBER() OVER (
                        PARTITION BY sekvens_nr
                        ORDER BY load_time DESC
                    ) AS rn
                FROM {self.db}.{self.schema}.{self.table}
                WHERE er_evaluering = 1
                AND sekvens_nr IN (1, 2, 3, 4)
            )
            SELECT
                model,
                prompt,
                ordning,
                er_evaluering,
                api_version,
                sekvens_nr
            FROM ranked
            WHERE rn = 1;
            """
        # Kør SQL
        try:
            results = self.execute_sql(sql).fetchall()
        except Exception as e:
            self.service_logger.service_exception(
                self,
                f"Fejl ved udtrækning af evalueringsprompts i SQL-tabellen {self.db}.{self.schema}.{self.table}: {e}",
            )
            return (
                "",
                "",
                "",
                "",
                "gpt-4o-mini",
                "gpt-4o-mini",
                "gpt-4o-mini",
                "gpt-4o-mini",
            )

        # Returnér prompts hvis de findes, ellers returnér tomme strenge
        if not results:
            self.service_logger.service_warning(
                self,
                f"Der blev ikke fundet evalueringsprompts i SQL-tabellen {self.db}.{self.schema}.{self.table}",
            )
            return (
                "",
                "",
                "",
                "",
                "gpt-4o-mini",
                "gpt-4o-mini",
                "gpt-4o-mini",
                "gpt-4o-mini",
            )

        # Udtræk evalueringsprompts og modelspecifikation
        retningslinjer_notat_prompt = ""
        retningslinjer_notat_val_prompt = ""
        hallucination_prompt = ""
        samtale_kvalitet_prompt = ""

        retningslinjer_notat_model = ""
        retningslinjer_notat_val_model = ""
        hallucination_model = ""
        samtale_kvalitet_model = ""

        for row in results:
            if row.sekvens_nr == "1":
                retningslinjer_notat_prompt = row.prompt
                retningslinjer_notat_model = row.model
            elif row.sekvens_nr == "2":
                retningslinjer_notat_val_prompt = row.prompt
                retningslinjer_notat_val_model = row.model
            elif row.sekvens_nr == "3":
                hallucination_prompt = row.prompt
                hallucination_model = row.model
            elif row.sekvens_nr == "4":
                samtale_kvalitet_prompt = row.prompt
                samtale_kvalitet_model = row.model

        # Giv en advarsel hvis en evalueringsprompt mangler
        if not retningslinjer_notat_prompt:
            self.service_logger.service_warning(
                self,
                f"Ingen retningslinjer_notat_prompt med sekvens_nr=1 fundet",
            )
        if not retningslinjer_notat_val_prompt:
            self.service_logger.service_warning(
                self,
                f"Ingen retningslinjer_notat_val_prompt med sekvens_nr=2 fundet",
            )
        if not hallucination_prompt:
            self.service_logger.service_warning(
                self,
                f"Ingen hallucination_prompt med sekvens_nr=3 fundet",
            )
        if not samtale_kvalitet_prompt:
            self.service_logger.service_warning(
                self,
                f"Ingen samtale_kvalitet_prompt med sekvens_nr=4 fundet",
            )

        return (
            retningslinjer_notat_prompt,
            retningslinjer_notat_val_prompt,
            hallucination_prompt,
            samtale_kvalitet_prompt,
            retningslinjer_notat_model,
            retningslinjer_notat_val_model,
            hallucination_model,
            samtale_kvalitet_model,
        )

    def gem_prompt(
        self,
        model: str,
        prompt: str,
        ordning: str,
        er_evaluering: int,
        api_version: str,
        sekvens_nr: str,
    ) -> int:
        """
        Gemmer prompt i tabellen jn.prompts.
        """
        # Giv en advarsel hvis en værdi mangler
        for val, col in zip(
            [model, prompt, ordning, er_evaluering, api_version, sekvens_nr],
            [
                "model",
                "prompt",
                "ordning",
                "er_evaluering",
                "api_version",
                "sekvens_nr",
            ],
        ):
            if val is None or (isinstance(val, str) and val.strip() == ""):
                self.service_logger.service_warning(
                    self,
                    f"Værdi for '{col}' mangler ved forsøg på at gemme prompt i SQL-tabellen {self.db}.{self.schema}.{self.table}. Rækken blev ikke indsat.",
                )
                return 400

        # Indsæt data i jn.notat
        self._sql_insert_into(
            model, prompt, ordning, er_evaluering, api_version, sekvens_nr
        )

        return 200

    def _sql_insert_into(
        self,
        model: str | None,
        prompt: str | None,
        ordning: str | None,
        er_evaluering: int | None,
        api_version: str | None,
        sekvens_nr: str | None,
    ) -> None:
        """
        SQL-streng der indsætter i komponentens tabel.
        """

        # Håndtér manglende værdier
        model = f"'{model}'" if model else "NULL"
        prompt = f"'{prompt}'" if prompt else "NULL"
        ordning = f"'{ordning}'" if ordning else "NULL"
        er_evaluering = er_evaluering if er_evaluering is not None else "NULL"
        api_version = f"'{api_version}'" if api_version else "NULL"
        sekvens_nr = f"'{sekvens_nr}'" if sekvens_nr else "NULL"

        # Tjek om der findes en tilsvarende række i forvejen
        query = f"""
            SELECT
                1
            FROM {self.db}.{self.schema}.{self.table}
            WHERE model = {model}
              AND prompt = {prompt}
              AND ordning = {ordning}
              AND er_evaluering = {er_evaluering}
              AND api_version = {api_version}
              AND sekvens_nr = {sekvens_nr}
        """
        try:
            exists = self.execute_sql(query).fetchone()
        except Exception as e:
            self.service_logger.service_exception(
                self,
                f"Fejl ved forespørgsel om der allerede findes en række i SQL-tabellen {self.db}.{self.schema}.{self.table}: {e}",
            )
            return

        if not exists:
            # Rækken findes ikke. Rækken tilføjes.
            insert_query = f"""
                BEGIN TRANSACTION
                INSERT INTO {self.db}.{self.schema}.{self.table} WITH (TABLOCKX)
                (
                    model,
                    prompt,
                    ordning,
                    er_evaluering,
                    api_version,
                    sekvens_nr,
                    load_time
                )
                VALUES
                (
                    {model},
                    {prompt},
                    {ordning},
                    {er_evaluering},
                    {api_version},
                    {sekvens_nr},
                    '{dt.datetime.now()}'
                )
                COMMIT TRANSACTION
            """
            try:
                self.execute_sql(insert_query)
                self.session.commit()
            except Exception as e:
                self.service_logger.service_exception(
                    self,
                    f"Fejl ved indsættelse af række i SQL-tabellen {self.db}.{self.schema}.{self.table}: {e}",
                )
        else:
            self.service_logger.service_warning(
                self,
                f"Rækken findes allerede i SQL-tabellen {self.db}.{self.schema}.{self.table}! Ingen data blev indsat.",
            )
