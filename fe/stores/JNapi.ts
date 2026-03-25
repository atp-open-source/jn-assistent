import { defineStore } from "pinia";
import axios from "axios";
import { useRouter } from "vue-router";

/*
JNapi
________________________________________________________________________________________

Denne store indeholder de funktioner der bruges til at forbinde
webappen til API'et, der henter data fra Leverance.
________________________________________________________________________________________

Bruges i følgende filer:
- JNNotatFeedback.vue
- JNScaleFeedback.vue
- JNJournalnotatStore.ts
- JNConfig.vue
*/

export const useApiStore = defineStore("ApiStore", () => {
  const router = useRouter();
  const baseUrl: string = import.meta.env.VITE_API_SERVER;

  function generateUID(): string {
    /**
     * Genererer et unikt ID baseret på tilfældigt tal.
     *
     * @returns {string} Et unikt ID på 9 tegn.
     */
    return Math.random().toString(36).substring(2, 11);
  }

  async function fetchUsername(): Promise<string | null> {
    /**
     * Finder brugernavnet (initialer) på den kunderådgiver, der er logget ind.
     * Initialerne hentes fra routerens metadata.
     *
     * @returns {Promise<string | null>} Initialer som en streng, eller null hvis de ikke kunne findes.
     */
    try {
      // Hent brugernavn (initialer) fra routerens metadata
      const username = router.currentRoute.value.meta.username;
      if (username && typeof username === "string") {
        if (username === "Guest") {
          console.warn(
            "Kunderådgiver er logget ind som 'Guest'. Initialer kan ikke hentes korrekt.",
          );
          return null;
        }
        return username;
      }
      console.log("Kunne ikke hente kunderådgivers initialer.");
      return null;
    } catch (error) {
      console.error("Fejl under hentning af kunderådgivers initialer:", error);
      return null;
    }
  }

  async function fetchStatus(): Promise<string | undefined> {
    /**
     * Henter status på opkaldet fra Kafka gennem API endpoint i leverance.
     *
     * @returns {Promise<any>} Status-data fra API'et.
     */
    // Hent brugernavn og UUID
    const myUUID: string = generateUID();
    const username: string | null = await fetchUsername();

    if (username === null) {
      console.error(
        "Kan ikke hente status uden gyldige kunderådgiver initialer.",
      );
      return undefined;
    }
    // Definér URL
    const url: string = `${baseUrl}/api/jn/fetch_status`;
    const argsUpdated: string[] = ["kr_initialer=" + username, "uid=" + myUUID];
    let response: any;

    const endpoint = url + "?" + argsUpdated.join("&");

    response = await axios.get(endpoint);

    if (response && response.data) {
      return response.data.Status;
    }
  }

  async function fetchNotat(): Promise<{
    notat: string | null;
    call_id: string | null;
    statusCode: number | null;
  }> {
    /**
     * Henter journalnotat og tilhørende opkalds-ID fra API'et.
     *
     * @returns {Promise<{ notat: string | null; call_id: string | null; statusCode: number | null }>}
     * Objekt med journalnotat og opkalds-ID samt statuskode.
     * Hvis intet notat findes eller der opstår en fejl, returneres null værdier.
     */
    try {
      // Hent brugernavn og UUID
      const myUUID: string = generateUID();
      const username: string | null = await fetchUsername();

      // Definér URL
      const url: string = `${baseUrl}/api/jn/get_notat`;
      const argsUpdated: string[] = [
        "kr_initialer=" + username,
        "uid=" + myUUID,
      ];
      const endpoint = url + "?" + argsUpdated.join("&");
      let response = await axios.get(endpoint);

      return extractNotatData(response);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        console.error("Axios-fejl ved hentning af notat:", error.message);
        return extractNotatData(error.response);
      } else {
        console.error("Fejl ved hentning af notat:", error);
        return extractNotatData(null);
      }
    }
  }

  function extractNotatData(response: any): {
    notat: string | null;
    call_id: string | null;
    statusCode: number | null;
  } {
    /**
     * Hjælpefunktion til at ekstrahere journalnotat, opkalds-ID og statuskode fra
     * API-responsen.
     *
     * @param {any} response - Responsobjekt fra API'et.
     * @returns {{ notat: string | null; call_id: string | null; statusCode: number | null }}
     * Objekt med journalnotat, opkalds-ID og statuskode.
     */
    const data = response?.data;
    const status = response?.status;
    if (!data?.notat || status !== 200) {
      console.warn(
        `Ingen journalnotat fundet eller uventet statuskode: ${status}`,
      );
    }
    return {
      notat: (status === 200 ? data?.notat : null) ?? null,
      call_id: (status === 200 ? data?.call_id : null) ?? null,
      statusCode: status ?? null,
    };
  }

  async function saveNotatFeedback(
    agentId: string,
    call_id: string | null,
    feedback: string | null,
    rating: number | null,
    benyttet: boolean,
  ): Promise<void> {
    /**
     * Sender feedback og rating af journalnotat til Leverance.
     *
     * @param {string} agentId - Kunerådgivers initialer.
     * @param {string | null} call_id - Opkalds-ID (kan være null).
     * @param {string | null} feedback - Feedbacktekst (kan være null).
     * @param {number | null} rating - Vurdering på en skala (kan være null; -1 hvis ingen vurdering).
     * @param {boolean} benyttet - Indikator for om notatet er benyttet eller ej.
     */
    try {
      const url = `${baseUrl}/api/jn/feedback`;
      const uid = generateUID();

      const postData = {
        call_id,
        agent_id: agentId,
        feedback: feedback || "",
        rating: rating !== null ? rating : -1,
        benyttet: benyttet ? 1 : 0,
        uid,
      };

      if (!call_id) {
        console.warn("Call_id mangler! Sender feedback uden call_id.");
      }

      const response = await axios.post(url, postData);
      if (response.status === 200 || response.status === 201) {
        console.log("Feedback er sendt til Leverance:", response.data);
      } else {
        console.warn("Uventet statuskode: ${response.status}", response.data);
      }
    } catch (error) {
      if (axios.isAxiosError(error)) {
        console.error("Axios-fejl:", error.message);
        if (error.response) {
          console.error(
            "Serveren svarede med status ${error.response.status}:",
            error.response.data,
          );
        }
      } else {
        console.error("Fejl:", error);
      }
    }
  }

  async function fetchConfig(kr_initialer: string): Promise<any> {
    /**
     * Henter konfiguration for kunderådgiver ved at kalde /get_config endpoint i leverance.
     *
     * @returns {Promise<any>} Konfiguration for kunderådgiver eller null hvis der opstår en fejl.
     */
    try {
      // Generér et unikt ID til anmodningen
      const uid: string = generateUID();

      // Definér URL og parametre
      const url: string = `${baseUrl}/api/jn/get_config`;
      const params: string[] = ["kr_initialer=" + kr_initialer, "uid=" + uid];

      const endpoint = url + "?" + params.join("&");

      // Udfør GET-anmodningen
      const response = await axios.get(endpoint);

      if (response.status === 200 && response.data) {
        console.log("Konfiguration hentet for kunderådgiver:", kr_initialer);
        return response.data;
      } else {
        console.warn(`Uventet statuskode: ${response.status}`, response.data);
        return null;
      }
    } catch (error) {
      if (axios.isAxiosError(error)) {
        console.error(
          "Axios-fejl ved hentning af konfiguration:",
          error.message,
        );
        if (error.response) {
          console.error(
            `Leverance svarede med status ${error.response.status}:`,
            error.response.data,
          );
        }
      } else {
        console.error(
          `Fejl ved hentning af konfiguration for kunderådgiver ${kr_initialer}:`,
          error,
        );
      }
      return null;
    }
  }

  async function insertConfig(
    kr_initialer: string,
    miljoe: string,
    streamer_version: string,
    transcriber_version: string,
    chatgpt_version: string,
    forretningsomraade: string,
    controller_version: string,
  ): Promise<{
    message: string;
    success: boolean;
    successfulKr: string[];
    failedKr: string[];
  }> {
    /**
     * Indsætter eller opdaterer konfiguration for en eller flere kunderådgivere ved at kalde /insert_config
     * endpoint i Leverance.
     *
     * @param {string} kr_initialer: Kunderådgiverens initialer (enkelt eller kommasepareret liste)
     * @param {string} miljoe: Miljøet (f.eks. 'dev', 'prod')
     * @param {string} streamer_version: Version af streameren ('kafka' eller 'azure')
     * @param {string} transcriber_version: Version af transcriberen
     * @param {string} chatgpt_version: Version af sprogmodellen
     * @param {string} forretningsomraade: Kunderådgivers forretningsområde
     * @param {string} controller_version: Navn på controlleren ('onprem' eller 'azure')
     * @returns {Promise<{ message: string; success: boolean; successfulKr: string[]; failedKr: string[] }>} Resultat af kald.
     */
    try {
      // Fjern alle mellemrum og split på komma
      const initialerArray = kr_initialer
        .replace(/\s+/g, "")
        .toLowerCase()
        .split(",")
        .filter((init) => init.length > 0);

      if (initialerArray.length === 0) {
        return {
          message: "Ingen gyldige kunderådgiver initialer angivet.",
          success: false,
          successfulKr: [],
          failedKr: [],
        };
      }

      // Forbered data til POST anmodning
      const postData = {
        miljoe: miljoe.toLowerCase(),
        streamer_version: streamer_version.toLowerCase(),
        transcriber_version: transcriber_version.toLowerCase(),
        chatgpt_version: chatgpt_version.toLowerCase(),
        forretningsomraade: forretningsomraade.toLowerCase(),
        controller_version: controller_version.toLowerCase(),
      };

      const results: Array<{ kr: string; success: boolean; message: string }> =
        [];

      // Indsæt konfiguration for hver kunderådgiver
      for (const initialer of initialerArray) {
        try {
          const uid: string = generateUID();
          const url: string = `${baseUrl}/api/jn/insert_config?uid=${uid}`;

          const response = await axios.post(url, {
            ...postData,
            kr_initialer: initialer,
          });

          const msg = response.data?.msg;
          results.push({
            kr: initialer,
            success: response.status === 200,
            message: msg || `Konfiguration gemt for ${initialer}`,
          });
        } catch (error) {
          const msg = axios.isAxiosError(error) && error.response?.data?.msg;
          results.push({
            kr: initialer,
            success: false,
            message:
              msg || `Fejl ved gemning af konfiguration for ${initialer}`,
          });
        }
      }

      // Opdel resultater i succesfulde og fejlede
      const successfulKr = results
        .filter((r) => r.success)
        .map((r) => r.kr.toUpperCase());
      const failedKr = results
        .filter((r) => !r.success)
        .map((r) => r.kr.toUpperCase());

      const allSuccess = failedKr.length === 0;

      const message =
        initialerArray.length === 1
          ? results[0].message
          : `${successfulKr.length} af ${initialerArray.length} konfigurationer blev gemt.`;

      return {
        message,
        success: allSuccess,
        successfulKr,
        failedKr,
      };
    } catch (error) {
      console.error(`Fejl ved indsættelse af konfiguration:`, error);
      return {
        message: `Der opstod en uventet fejl ved indsættelse af konfiguration.`,
        success: false,
        successfulKr: [],
        failedKr: [],
      };
    }
  }

  async function deleteConfig(
    kr_initialer: string,
  ): Promise<{ message: string; success: boolean }> {
    /**
     * Sletter konfiguration for en kunderådgiver ved at kalde /delete_config endpoint i Leverance.
     *
     * @param {string} kr_initialer: Kunderådgiverens initialer
     * @returns {Promise<{ message: string; success: boolean }>} Resultat af kald.
     */
    try {
      // Generér et unikt ID til anmodningen
      const uid: string = generateUID();

      // Definér URL, parametre og endpoint
      const url: string = `${baseUrl}/api/jn/delete_config?kr_initialer=${kr_initialer.toLocaleLowerCase()}&uid=${uid}`;

      // Lav GET-anmodningen
      const response = await axios.get(url);
      const msg = response.data?.msg || response.data;

      return {
        message:
          msg ||
          `Konfigurationen for kunderådgiver ${kr_initialer} blev slettet.`,
        success: response.status === 200,
      };
    } catch (error) {
      const msg = axios.isAxiosError(error) && error.response?.data?.msg;

      console.error(
        `Fejl ved sletning af konfiguration for kunderådgiver ${kr_initialer}:`,
        error,
      );
      return {
        message:
          msg ||
          `Der opstod en fejl ved sletning af konfiguration for kunderådgiver ${kr_initialer}.`,
        success: false,
      };
    }
  }

  return {
    fetchUsername,
    fetchNotat,
    saveNotatFeedback,
    fetchStatus,
    fetchConfig,
    insertConfig,
    deleteConfig,
  };
});
