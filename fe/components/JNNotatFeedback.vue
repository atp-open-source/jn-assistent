<!--
JNNotatFeedback
________________________________________________________________________________________

Komponenten giver brugeren mulighed for at indsende feedback til det foreslåede
journalnotat i form af et fritekstfelt. Feedbacken sendes til backend (Leverance).
________________________________________________________________________________________

Funktionaliteter:
- Indtastning af kommentarer til journalnotatet via en tekstboks.
- Sender feedback til backend, når brugeren klikker på "Send kommentar".

DataStore funktioner:
- useApiStore - henter brugernavn og sender feedback til backend.

-->

<template>
  <div id="jn" class="feedback-container">
    <!-- Tekstboks til feedback -->
    <textarea
      v-if="feedbackVisible"
      v-model="freeTextFeedback"
      rows="4"
      placeholder="Har du kommentarer til det foreslåede journalnotat, kan du skrive dem her."
      class="feedback-textarea"
    ></textarea>
    <!-- Send kommentar knap -->
    <Button
      v-if="feedbackVisible"
      label="Send kommentar"
      icon="pi pi-send"
      @click="save"
      size="small"
      class="frai-buttons"
    ></Button>
    <!-- Takkebesked -->
    <p v-if="thankYouMessage" class="feedback-text">Tak for din feedback!</p>
  </div>
</template>

<script setup lang="ts">
import { ref, defineEmits, toRefs } from "vue";
import { useApiStore } from "../stores/JNapi";
import { useJournalStore } from "../stores/JNJournalnotatStore";
import { TakState } from "../stores/StorybookStore";
// Variabler for feedback
const emit = defineEmits(["save", "close"]);
const freeTextFeedback = ref("");
const feedbackVisible = ref<boolean>(true);
const thankYouMessage = ref<boolean>(false);
const api_store = useApiStore();
const journalStore = useJournalStore();
const { call_id, notatUsed } = toRefs(journalStore);

const save = async () => {
  /**
   * Sender feedback for opkaldet til Leverance (/api/feedback).
   */
  try {
    // Hent brugernavn
    const username = await api_store.fetchUsername();
    if (!username) {
      console.error("Brugernavn kunne ikke findes.");
      return;
    }

    // Gem feedback for det foreslåede journalnotat
    await api_store.saveNotatFeedback(
      username,
      call_id.value,
      freeTextFeedback.value,
      null,
      notatUsed.value,
    );

    // Skjul feedbackfelt og vis takkebesked
    feedbackVisible.value = false;
    thankYouMessage.value = true;

    // Vent 5 sekunder og nulstil takkebesked
    setTimeout(() => {
      thankYouMessage.value = false;
      feedbackVisible.value = true;
    }, 5000);
  } catch (error) {
    console.error("Fejl ved at gemme feedback for journalnotat", error);
  }

  // Reset feedback text og emit save
  freeTextFeedback.value = "";
  emit("save");
};

// ===== Storybook Probs =====
const props = defineProps({
  storybookState: {
    type: String,
    default: "",
  },
});

// Takkebesked til Storybook
if (props.storybookState === "tak") {
  TakState(feedbackVisible, thankYouMessage);
}
</script>

<style scoped>
.feedback-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding-bottom: 20px;
  min-height: 150px;
}

.feedback-textarea {
  width: 25%;
  margin-top: 20px;
  margin-bottom: 10px;
  font-family: inherit;
}
</style>
