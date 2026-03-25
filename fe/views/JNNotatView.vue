<!-- 
JNNotatView
________________________________________________________________________________________

Denne komponent repræsenterer den primære side, som brugeren interagerer med. Komponenten 
viser JN-figuren i hjørnet med en statusbar, genererer en statusbesked, og giver brugeren 
mulighed for at kopiere eller afslutte notatet.
________________________________________________________________________________________

Funktionaliteter:
- StatusBar: Viser JN figuren, som illustrerer den nuværende status, dertil en statusbesked.
- Overskrift: Viser en titel, der indikerer, at dette er en automatisk journalnotatgenereringsside.
- Spinner: Vises under genereringen af notatet og signalerer, at en proces er i gang.
- Kopierings- og færdigknapper: Giver brugeren mulighed for at kopiere notatet og markere 
  processen som afsluttet.
- Feedback: Inkluderer komponenter til at give feedback og en skala.

JournalnotatStore funktioner:
- updateStatusContinuously: Opdaterer status for opkaldet kontinuerligt.
- copyToClipboard: Kopierer indholdet af `.summary-text` HTML-elementet til udklipsholderen.
- checkIfCopied: Tjekker om notatet er kopieret og om der er givet en rating.
-->

<template>
  <body id="jn">
    <div class="container">
      <header style="padding: 0 0.9rem">
        <StatusBar :icon="icon" :text="text" :class="icon">
          <div class="status-message"></div>
        </StatusBar>
      </header>

      <!-- Tekstboks til at vise notatet -->
      <div class="summary-textbox">
        <div v-if="isGenerating" class="spinner-container">
          <div class="spinner"></div>
          <div class="spinner-text">Genererer notat...</div>
        </div>
        <div v-else class="summary-text" v-html="summarytext"></div>
      </div>

      <!-- Knapper til at kopiere notatet og en til at markere processen som afsluttet. -->
      <div style="text-align: center">
        <Button
          :label="copyText"
          icon="pi pi-copy"
          @click="copyToClipboard"
          size="small"
          class="frai-buttons"
          :disabled="!isVisible"
        ></Button>
        <Button
          label="Færdig"
          icon="pi pi-check"
          @click="checkIfCopied"
          size="small"
          class="frai-buttons"
          :disabled="!isVisible"
        ></Button>
        <Button
          label="Notat ikke benyttet"
          icon="pi pi-times"
          @click="markNotatNotUsed"
          size="small"
          class="frai-buttons not-used"
          :disabled="!isVisible || !notatUsed"
        ></Button>
      </div>

      <!-- Container til succes-besked om notat ikke benyttet -->
      <div class="success-message-container">
        <p v-if="showSuccessMessage" class="success-message">
          Notatet blev markeret som ikke benyttet.
        </p>
      </div>

      <!-- Feedbackboks -->
      <footer>
        <ScaleFeedback v-if="isVisible" @rating-given="ratingGiven = true" />
        <div class="feedback-container">
          <NotatFeedback v-if="isVisible" />
        </div>
      </footer>
    </div>
  </body>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, toRefs } from "vue";
import { useJournalStore } from "../stores/JNJournalnotatStore.js";
import StatusBar from "../components/JNStatusBar.vue";
import ScaleFeedback from "../components/JNScaleFeedback.vue";
import NotatFeedback from "../components/JNNotatFeedback.vue";

// Variabler
const journalStore = useJournalStore();
const copyText = ref<string>("Kopiér notat");
const showSuccessMessage = ref<boolean>(false);
const {
  icon,
  text,
  summarytext,
  isGenerating,
  isVisible,
  ratingGiven,
  notatUsed,
  checkIfCopied,
} = toRefs(journalStore);

const copyToClipboard = async () => {
  /**
   * Kopierer indholdet af `.summary-text` HTML-elementet til udklipsholderen.
   * Opdaterer knapteksten for at angive succes og nulstiller den.
   */

  // Hent elementet, der skal kopieres
  const elements = document.getElementsByClassName("summary-text");
  if (elements.length > 0) {
    const element = elements[0] as HTMLElement;
    await journalStore.copyToClipboard(element);
    copyText.value = "Kopieret!";
    setTimeout(() => {
      copyText.value = "Kopiér notat";
    }, 2000);
  } else {
    throw new Error("Journalnotat kunne ikke kopieres.");
  }
};

const markNotatNotUsed = async () => {
  /**
   * Marker notatet som "ikke benyttet" og vis succesbesked.
   */
  try {
    await journalStore.markNotatNotUsed();
    // Vis succesbesked
    showSuccessMessage.value = true;
    // Skjul succesbesked efter 5 sekunder
    setTimeout(() => {
      showSuccessMessage.value = false;
    }, 5000);
  } catch (error) {
    console.error("Fejl ved at markere notatet som ikke benyttet:", error);
  }
};

onMounted(async () => {
  /**
   * Henter journalnotatet kontinuerligt når siden mountes.
   */
  journalStore.updateStatusContinuously();
});

onBeforeUnmount(() => {
  /**
   * Rydder op og stopper intervallet, når komponenten unmountes.
   */
});
</script>

<style scoped>
.summary-textbox {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 2rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  background-color: #f9f9f9;
  margin: 1rem auto;
  max-width: 1000px;
  min-height: 300px;
}

.success-message-container {
  height: 0.9rem;
  display: flex;
  justify-content: center;
  align-items: center;
}

.success-message {
  color: var(--primary2-color);
  font-size: 0.9rem;
  text-align: center;
  animation: fadeOut 5s forwards;
}

@keyframes fadeOut {
  0% {
    opacity: 1;
  }
  80% {
    opacity: 1;
  }
  100% {
    opacity: 0;
  }
}

.working {
  background-image: url(../assets/loading-talk.gif);
  background-repeat: no-repeat;
  background-position: 6.5rem 5rem;
  background-size: 2rem;
  padding: 1rem;
  padding-left: 2.5rem;
}

.ready {
  padding: 1rem;
  padding-left: 2.5rem;
}

.listening {
  background-image: url(../assets/speaking-active.gif);
  background-repeat: no-repeat;
  background-position: 4.75rem 5.5rem;
  background-size: 2rem;
  padding: 1rem;
  padding-left: 2.5rem;
}

.container {
  padding: 1rem 0 2rem 0.1rem;
}

.spinner-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid var(--primary-color);
  border-radius: 50%;
  width: 50px;
  height: 50px;
  animation: spin 2s linear infinite;
  margin-bottom: 1rem;
}

.spinner-text {
  font-size: 1rem;
  color: var(--primary2-color);
  text-align: center;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}
</style>
