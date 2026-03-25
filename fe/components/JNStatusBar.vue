<!-- 
JNStatusBar
________________________________________________________________________________________

Komponenten viser et statusikon og en tilhørende statusbesked baseret på opkaldets status.
Disse opdateres dynamisk og kan vise forskellige ikoner og beskeder afhængigt af opkaldets 
status.
________________________________________________________________________________________

Funktionaliteter:
- Viser forskellige ikoner afhængigt af opkaldets status (inactive, listening, ready, 
  working, generated).
- Genererer en statusbesked, der forklarer den nuværende opkaldsstatus.

DataStore funktioner:
-->

<template>
  <div id="jn" class="status-bar">
    <!-- Ikonboks, der viser det relevante ikon baseret på props.icon -->
    <div class="icon-box">
      <IconJanInactive v-if="props.icon === 'inactive'" />
      <IconJanReady v-if="props.icon === 'ready'" />
      <IconJanListening v-if="props.icon === 'listening'" />
      <IconJanWorking v-if="props.icon === 'working'" />
      <IconJanGenerated v-if="props.icon === 'generated'" />
    </div>
    <!-- Indholdsboksen, der viser teksten og statusbeskeden -->
    <div class="content" :style="{ paddingTop: '1rem' }">
      <p>
        <span>{{ props.text }} </span>
      </p>
      <div
        class="status-message"
        :style="{ textAlign: 'left', fontSize: '1px' }"
      >
        <p>{{ getStatusMessage }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import IconJanInactive from "./icons/IconJanInactive.vue";
import IconJanReady from "./icons/IconJanReady.vue";
import IconJanListening from "./icons/IconJanListening.vue";
import IconJanWorking from "./icons/IconJanWorking.vue";
import IconJanGenerated from "./icons/IconJanGenerated.vue";
import { computed } from "vue";

var props = defineProps({
  /**
   * Props for ikonet, der viser opkaldets status.
   * Opkaldets status kan være følgende: "inactive", "listening", "ready", "working", "generated".
   */
  icon: {
    type: String,
    default: "inactive",
    validator: (value: string) => {
      return (
        value === "" ||
        ["inactive", "listening", "ready", "working", "generated"].includes(
          value,
        )
      );
    },
  },
  text: {
    type: String,
    required: true,
  },
});

const getStatusMessage = computed(() => {
  /**
   * Beregner statusbeskeden baseret på den nuværende ikonværdi.
   * Afhængigt af opkaldets status returneres en passende besked:
   *      - "inactive": Prøv igen
   *      - "ready": Venter på opkald
   *      - "listening": Opkald i gang
   *      - "working": Opkald afsluttet
   *      - "generated": Kopiér notat og tryk herefter på færdig
   *
   * @returns {string} Statusbeskeden baseret på ikonet.
   */
  switch (props.icon) {
    case "inactive":
      return "Prøv igen";
    case "ready":
      return "Venter på opkald";
    case "listening":
      return "Opkald i gang";
    case "working":
      return "Opkald afsluttet";
    case "generated":
      return "Kopiér notat og tryk herefter på færdig";
    default:
      return "";
  }
});
</script>

<style scoped>
.status-bar {
  display: flex;
  flex-direction: row;
  justify-content: left;
  max-height: 10rem;
}

.content p {
  padding: 0;
  margin: 0;
  font-size: 1rem;
}

.content p span {
  font-weight: bold;
  font-size: 1.5rem;
}
</style>
