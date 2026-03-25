<template>
  <div class="sticky-header">
    <FRAIHeader :header="headerTitle" :username="$route.meta.username" />
  </div>
  <div>
    <router-view></router-view>
  </div>
</template>

<script>
import { useRoute } from "vue-router";
import { computed } from "vue";

export default {
  name: "BaseJN",
  setup() {
    const route = useRoute();

    // Definér overskriften baseret på route
    const headerTitle = computed(() => {
      switch (route.name) {
        case "JNconfig":
          return "JN | Konfigurationsside";
        case "JNnotatOverblik":
          return "JN | Notatoverblik";
        default:
          return "JN | Journalnotatsassistenten";
      }
    });

    return { headerTitle };
  },
};
</script>

<style>
@import "../assets/jn.css";

.sticky-header {
  position: sticky;
  top: 0;
  z-index: 100;
}
</style>
