<!-- 
JNNotatOverblikView
________________________________________________________________________________________

Denne komponent repræsenterer et overblik over notater med feedback. Brugeren kan se notater
fra ordningen personen sidder hos.
________________________________________________________________________________________

Funktionaliteter:
- Juster hvilke datoer der skal inkluderes
- Kopier tabellen med data eller downloade det i forskellige formater
- Filtrer tabellen med søgeord
-->

<template>
  <div id="jn">
    <JNNotatOverblikComponent />
  </div>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import JNNotatOverblikComponent from "../components/JNNotatOverblikComponent.vue";

export default defineComponent({
  name: "JNNotatOverblikView",
  components: {
    JNNotatOverblikComponent,
  },
});
</script>

<style scoped>
#jn {
  width: 100%;
  height: 100%;
}
</style>
