import { defineStore } from "pinia";
import { ref } from "vue";
import { useApiStore } from "../stores/JNapi.js";
import DOMPurify from "dompurify";

/*
JNJournalnotatStore
________________________________________________________________________________________

Denne store indeholder de funktioner der bruges i webappen, der
sørger for kontinuerligt at vise den rigtige status og at vise
journalnotatet, når det er genereret. Derudover indeholder den
funktionaliteterne for "Kopiér notat", "Færdig" og "Notat ikke
benyttet"-knapperne.
________________________________________________________________________________________

Bruges i følgende komponentfiler:
- JNNotatView.vue
*/

export const useJournalStore = defineStore("journal", () => {
  const call_id = ref<string | null>(null);
  const hasBeenCopied = ref<boolean>(false);
  const icon = ref<string>("ready");
  const text = ref<string>("Klar til brug");
  const summarytext = ref<string>("");
  const statusArray: string[] = ["start-call", "end-call", "end-summary"];
  const fejlstatusArray: string[] = [
    "call-state-duration-exceeded",
    "no-status",
    "no-status-key",
  ];
  const isDone = ref<boolean>(false);
  const hasFetchedNotat = ref<boolean>(false);
  const isGenerating = ref<boolean>(false);
  const isVisible = ref<boolean>(false);
  const ratingGiven = ref<boolean>(false);
  const notatUsed = ref<boolean>(true);
  const api_store = useApiStore();
  // Konstanter for tidsgrænser
  const POLL_INTERVAL_FAST = 10000; // 10 sekunder
  const POLL_INTERVAL_SLOW = 60000; // 1 minut
  const POLL_INTERVAL_END_CALL = 2000; // 2 sekunder
  const SLOW_POLL_THRESHOLD = 15 * 60 * 1000; // 15 minutter
  const END_CALL_THRESHOLD = 20000; // 20 sekunder
  const MAX_WAIT_TIME = 30 * 60 * 1000; // 30 minutter
  // Fejlmeddelelser for notathentning
  const NOTAT_ERROR_MESSAGES: Record<number, string> = {
    204: "Der blev ikke fundet noget notat.",
    500: "Der opstod en serverfejl ved hentning af notatet.",
    504: "Timeout-fejl: Det tog for lang tid at hente notatet.",
  };
  const DEFAULT_NOTAT_ERROR_MESSAGE =
    "Der opstod en ukendt fejl ved hentning af notatet.";

  const copyToClipboard = async (element: HTMLElement) => {
    /**
     * Kopierer indholdet af det angivne HTML-element til udklipsholderen.
     * Opretter både en formateret version (HTML) og en ren tekstversion uden HTML-tags.
     * Formateringen fjerner <br>-tags og erstatter dem med linjeskift.
     *
     * @param {HTMLElement} element: Det HTML-element, hvis indhold skal kopieres.
     * @returns {Promise<string | void>}: promise med formateret tekst.
     */
    let formattedText: string = "";
    let plaintext: string = "";

    // Bevar linjeskift ved at erstate <br>-tags med \n
    formattedText = element.innerHTML.replace(/<br\s*\/?>/g, "<br>");
    plaintext = element.innerHTML.replace(/<br\s*\/?>/g, "\n");

    // Opret ClipboardItem med både formateret og ren tekst
    const clipboardItem = new ClipboardItem({
      ["text/html"]: new Blob([formattedText], { type: "text/html" }),
      ["text/plain"]: new Blob([plaintext], { type: "text/plain" }),
    });

    // Kopiér til udklipsholderen
    try {
      await navigator.clipboard.write([clipboardItem]);
      hasBeenCopied.value = true;
      return formattedText;
    } catch (e) {
      console.error(`Error copying to clipboard: ${e}`);
    }
  };

  const checkIfCopied = () => {
    /**
     * Tjekker om teksten er blevet kopieret til udklipsholderen
     * og om der er givet hjerter.
     * Resetter status og gør feedbackskalaen synlig igen.
     */
    let message = "";

    if (!hasBeenCopied.value && !ratingGiven.value) {
      message =
        "Du har hverken kopieret journalnotatet eller givet hjerter. Er du sikker på, at du vil fortsætte?";
    } else if (!hasBeenCopied.value) {
      message =
        "Du har ikke kopieret journalnotatet. Er du sikker på, at du vil fortsætte?";
    } else if (!ratingGiven.value) {
      message =
        "Du har ikke givet hjerter. Er du sikker på, at du vil fortsætte?";
    }

    if (message) {
      const confirmProceed = window.confirm(message);
      if (confirmProceed) {
        isDone.value = true;
        reset();
      }
      // Hvis brugeren trykker på "Annullér", gør intet
    } else {
      isDone.value = true;
      reset();
    }
  };

  const getStatus = async () => {
    /**
     * Henter opkaldsstatus og mapper den til et tilsvarende ikon og statusbesked.
     * Håndterer de forskellige stadier i opkaldet og returnerer et array med ikonet og
     * den tekst, der skal vises.
     *
     * @returns {Promise<[string, string]>} En promise, der løser sig med et array, som indeholder:
     *  - ikonet (streng),
     *  - statusbeskeden (streng).
     */
    try {
      // Hent status
      const response_status = await api_store.fetchStatus();
      if (response_status === null) {
        return ["inactive", "Ingen forbindelse", response_status];
      }

      // Map status til ikon og tekst til statusbaren
      if (response_status === statusArray[0]) {
        isDone.value = false;
        summarytext.value = "";
        isVisible.value = false;
        hasFetchedNotat.value = false;
        call_id.value = null;
        hasBeenCopied.value = false;
        ratingGiven.value = false;
        notatUsed.value = true;
        return ["listening", "Lytter til opkald...", response_status];
      } else if (response_status === statusArray[1]) {
        isVisible.value = false;
        return ["working", "Genererer notat...", response_status];
      } else if (response_status === statusArray[2] && !isDone.value) {
        return ["generated", "Notat er genereret", response_status];
      } else {
        if (response_status === fejlstatusArray[0]) {
          summarytext.value =
            "Der har ikke været en ny status på opkaldet i over en time. Genindlæs siden når et nyt opkald er startet eller hvis notat afventes.";
        } else if (
          response_status === fejlstatusArray[1] ||
          response_status === fejlstatusArray[2]
        ) {
          summarytext.value =
            "Tag et nyt opkald for at generere et journalnotat.";
        }
        isVisible.value = false;
        return ["ready", "Klar til brug", response_status];
      }
    } catch (error) {
      console.error("Fejl i hentning af status:", error);
      isVisible.value = false;
      summarytext.value = "";
      return ["inactive", "Ingen forbindelse: Prøv igen om 5 minutter", ""];
    }
  };

  const updateSummaryText = async (newText: string | null) => {
    /**
     * Opdaterer `summarytext`-variablen med den angivne tekst.
     * Teksten renses med DOMPurify.
     *
     * @param {string | null} newText - Den nye tekst, der skal vises.
     */
    summarytext.value = DOMPurify.sanitize(newText || "");
  };

  const reset = () => {
    /**
     * Rydder tekstfeltet, resetter statusikonet, og gør feedbackområdet usynligt igen.
     */

    // Reset tekstfelt og status
    console.log("Resetting...");
    summarytext.value = "";
    icon.value = "ready";
    text.value = "Klar til brug";
    hasFetchedNotat.value = false;
    call_id.value = null;

    // Reset variable
    hasBeenCopied.value = false;
    ratingGiven.value = false;

    // Hvis der ikke er trykket på "Notat ikke benyttet", send feedback om at notatet er benyttet
    if (notatUsed.value) {
      try {
        sendNotatUsedFeedback();
      } catch (error) {
        console.error("Fejl ved at sende standard feedback:", error);
      }
    }

    // Reset knappen
    notatUsed.value = true;

    // Gør feedbackområdet usynligt
    isVisible.value = false;
  };

  const updateStatusContinuously = async () => {
    /**
     * Opdaterer opkaldsstatus kontinuerligt.
     * Anvendes til at opdatere statusikonet og statusbeskeden.
     */
    let username: string | null;

    username = await api_store.fetchUsername();
    if (!username) {
      console.error("Kunderådgiver initialer kunne ikke hentes.");
      summarytext.value = "";
      icon.value = "inactive";
      text.value = "Ingen Forbindelse: Fejl ved hentning af brugers initialer";
      isVisible.value = false;
      return;
    }

    let last_seen_msg = "";
    let startTime = Date.now();

    while (true) {
      // Hent status og opdater ikon og tekst
      let [fetchedIcon, fetchedText, new_msg] = await getStatus();

      // Nulstil startTime hvis der er ny status
      if (last_seen_msg !== new_msg) {
        startTime = Date.now();
      }

      const timeSinceLastChange = Date.now() - startTime;
      const minutesSinceLastChange = Math.floor(timeSinceLastChange / 60000);
      last_seen_msg = new_msg;

      // Vis en spinner i tekstboks, så bruger ved den arbejder på notatet
      if (fetchedIcon === "working") {
        isGenerating.value = true;
      }

      // Hvis notatet er genereret, hentes notatet
      if (fetchedIcon === "generated" && !hasFetchedNotat.value) {
        const result = await api_store.fetchNotat();
        isGenerating.value = false;
        call_id.value = result.call_id;
        if (result.notat) {
          updateSummaryText(result.notat);
          hasFetchedNotat.value = true;
          isVisible.value = true;
        } else {
          // Vis fejlmeddelelse baseret på statuskode
          const errorMessage =
            typeof result.statusCode === "number"
              ? (NOTAT_ERROR_MESSAGES[result.statusCode] ??
                DEFAULT_NOTAT_ERROR_MESSAGE)
              : DEFAULT_NOTAT_ERROR_MESSAGE;
          summarytext.value = errorMessage;
          // Reset statusikon og tekst, og sæt isDone så vi ikke forsøger at hente notatet igen
          fetchedIcon = "ready";
          fetchedText = "Klar til brug";
          isVisible.value = false;
          isDone.value = true;
        }
      }
      icon.value = fetchedIcon;
      text.value = fetchedText;

      if (new_msg === "") {
        console.error("Ingen forbindelse til server.");
        break;
      }

      if (new_msg === fejlstatusArray[0]) {
        // Hvis opkaldet har været inaktivt for længe, reset alt
        console.log(
          "Opkaldets status har været uændret i over en time. givet besked til KR om genindlæsning af siden.",
        );
        break;
      }

      // Håndter timeout på 30 minutter
      if (timeSinceLastChange > MAX_WAIT_TIME) {
        // Hvis der er gået mere end 30 minutter siden sidste statusændring
        if (last_seen_msg === statusArray[0]) {
          summarytext.value = `Opkaldet har varet over 30 minutter. Genindlæs siden når opkaldet er færdig.`;
          console.log("Opkald har kørt i over 30 minutter.");
        } else {
          summarytext.value = `Der har ikke været en ny status i over 30 minutter. Genindlæs siden.`;
          console.log("Ingen statusændring i over 30 minutter.");
        }
        break;
      }

      // Bestem polling interval og vis besked til bruger
      let pollInterval = POLL_INTERVAL_FAST;

      // Hvis der er gået mere end 15 minutter, opdater kun hvert minut
      // 98% af opkalene vil være færdige indenfor 15 minutter
      if (timeSinceLastChange > SLOW_POLL_THRESHOLD) {
        pollInterval = POLL_INTERVAL_SLOW;
        const nextCheckTime = new Date(Date.now() + 60000);
        const timeString = nextCheckTime.toLocaleString("da-DK", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
        summarytext.value = `Der har ikke være en ny status på opkaldet i ${minutesSinceLastChange} minutter. Henter ny status efter 1 minut (kl. ${timeString}). 
        Hvis opkaldet er afsluttet og notat afventes, genindlæs siden.`;
      }
      // Hvis status er end-call, poll hvert andet sekund de første 20 sekunder, for at få notatet så hurtigt som muligt.
      else if (
        new_msg === statusArray[1] &&
        timeSinceLastChange <= END_CALL_THRESHOLD
      ) {
        pollInterval = POLL_INTERVAL_END_CALL;
      }
      // Vent før næste polling
      await new Promise((resolve) => setTimeout(resolve, pollInterval));
    }
  };

  const markNotatNotUsed = async () => {
    /**
     * Marker notatet som "ikke benyttet" og deaktiver knappen.
     */
    try {
      notatUsed.value = false;
      sendNotatUsedFeedback();
    } catch (error) {
      console.error("Fejl ved at sende feedback:", error);
      // Hvis der opstår en fejl, aktiver knappen igen
      notatUsed.value = true;
    }
  };

  const sendNotatUsedFeedback = async () => {
    // Hent brugernavn
    const username = await api_store.fetchUsername();
    if (!username) {
      console.error("Brugernavn kunne ikke findes.");
      return;
    }

    // Send feedback til API'et med ingen feedback og ingen rating
    await api_store.saveNotatFeedback(
      username,
      call_id.value,
      null,
      null,
      notatUsed.value,
    );
  };

  return {
    copyToClipboard,
    checkIfCopied,
    updateStatusContinuously,
    markNotatNotUsed,
    call_id,
    isVisible,
    icon,
    text,
    hasBeenCopied,
    isGenerating,
    summarytext,
    ratingGiven,
    notatUsed,
  };
});
