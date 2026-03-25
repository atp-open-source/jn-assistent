<!--
JNScaleFeedback
________________________________________________________________________________________

Komponenten viser en ratingskala, hvor brugeren kan give feedback på kvaliteten af
det foreslåede journalnotat ved at vælge antal hjerter (mellem 1 og 5).
Den henter brugernavn og sender rating til backend (Leverance), når brugeren har
foretaget en vurdering.
________________________________________________________________________________________

Funktionaliteter:
- Vælg antal hjerter som vurdering for det foreslåede journalnotat.
- Gemmer feedback asynkront til backend (Leverance)

DataStore funktioner:
- UseApiStore - henter brugernavn og sender rating til backend.

-->

<template>
  <div id="jn" class="modal-overlay">
    <div class="modal">
      <h2>Feedback</h2>
      <span>Hvad synes du om kvaliteten af det foreslåede journalnotat?</span>
      <div v-if="visibleScale" class="scale" @mouseleave="resetSelection()">
        <!-- Vis valgte antal af hjerte ikoner -->
        <template v-for="n in 5" v-bind:key="n">
          <div
            class="heart-clickable"
            @click="changeSelection(n)"
            @mouseover="hoverSelect(n)"
          >
            <font-awesome-icon
              :icon="n < selectedValue ? 'heart' : 'fa-regular fa-heart'"
              class="heart-icon"
            />
          </div>
        </template>
      </div>
      <p class="hover-message">{{ hoverMessage }}</p>
      <p v-if="feedbackMessage" class="feedback-text">
        {{ feedbackMessage }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, toRefs } from "vue";
import { useApiStore } from "../stores/JNapi";
import { useJournalStore } from "../stores/JNJournalnotatStore";
import { RatingState } from "../stores/StorybookStore";

// Variabler og props
const selected = ref<number>(0);
const previousSelected = ref<number>(0);
const feedbackMessage = ref<string>("");
const hoverMessage = ref<string>("");
const selectedValue = computed(() => selected.value);
const visibleScale = ref<boolean>(true);
const api_store = useApiStore();
const journalStore = useJournalStore();
const emit = defineEmits(["rating-given"]);
const { call_id, notatUsed } = toRefs(journalStore);

const ratingDescriptions = {
  5: "Notatet er fejlfrit, præcist og dækkende.",
  4: "Notatet er præcist med få mindre fejl.",
  3: "Notatet er forståeligt, men mangler oplysninger eller har flere fejl.",
  2: "Notatet er unøjagtigt og kræver omformulering.",
  1: "Notatet er så fejlbehæftet, at det kræver omfattende redigering.",
};

const save = async () => {
  /**
   * Gemmer asynkront den feedback (antal hjerter), som brugeren har givet.
   */
  try {
    // Hent brugernavn
    const username = await api_store.fetchUsername();
    if (!username) {
      console.error("Brugernavn kunne ikke findes.");
      return;
    }

    // Gem rating af opkald
    await api_store.saveNotatFeedback(
      username,
      call_id.value,
      null,
      selected.value,
      notatUsed.value,
    );
  } catch (error) {
    console.error("Fejl ved at gemme rating af journalnotat", error);
  }
};

const changeSelection = async (n: number) => {
  /**
   * Opdaterer det valgte antal hjerter og giver en feedbackbesked til brugeren.
   * @param {number} n - Det nye hjertevurdering.
   */
  // Opdater valgte antal hjerter
  previousSelected.value = selected.value;
  selected.value = n;
  emit("rating-given");

  // Vis feedbackbesked til brugeren og skjul skalaen
  if (n === 1) {
    feedbackMessage.value = `Du har givet dette journalnotat ${n} hjerte.`;
  } else {
    feedbackMessage.value = `Du har givet dette journalnotat ${n} hjerter.`;
  }
  visibleScale.value = false;

  // Vis feedbackMessage i 5 sekunder og derefter nulstil antal hjerter og vis skala igen
  setTimeout(() => {
    hoverMessage.value = "";
    feedbackMessage.value = "";
    selected.value = 0;
    visibleScale.value = true;
  }, 5000);

  await save();
};

const hoverSelect = (n: number) => {
  /**
   * Opdaterer de valgte antal hjerter, når brugeren holder musen over et element.
   * @param {number} n - antal hjerter, der skal vises.
   */
  selected.value = n + 1;
  hoverMessage.value = ratingDescriptions[n] || ""; // Set hoverMessage based on the rating
};

const resetSelection = () => {
  /**
   * Nulstiller det valgte antal hjerter ved mouse leave og fjerner beskeden.
   */
  hoverMessage.value = "";
  feedbackMessage.value = "";
  selected.value = 0;
  visibleScale.value = true;
};

// ===== Storybook Probs =====
const props = defineProps({
  storybookState: {
    type: Object,
    default: () => null,
  },
});

// Håndterer Storybook state for rating
if (props.storybookState?.selectedRating) {
  RatingState(props.storybookState, {
    selected,
    feedbackMessage,
    hoverMessage,
    visibleScale,
    ratingDescriptions,
  });
}
</script>

<style scoped>
.modal {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: 30px;
}

.scale {
  margin-top: 20px;
  width: 25%;
  display: flex;
  flex-direction: row;
  justify-content: space-around;
  font-size: 28px;
}

.heart-clickable {
  cursor: pointer;
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
}

.heart-icon {
  color: var(--primary2-color);
}

.hover-message {
  height: 1em;
}
</style>
