<template>
  <header class="frai-header">
    <div>
      <h1>{{ header }}</h1>
    </div>
    <div class="frai-user">{{ username || "Guest" }}</div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  header: string;
  username?: string;
}>();
</script>

<style scoped>
.frai-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  background: #02463a;
  color: #fff;
}

.frai-header h1 {
  margin: 0;
  font-size: 1.1rem;
}

.frai-user {
  font-size: 0.95rem;
  opacity: 0.9;
}
</style>
